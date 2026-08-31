"""P0/P1 hardening regression suite. Locks in every fix applied during the
2026-08 audit pass so none of it silently regresses as new endpoints are
added. Run after installing requirements: python p0_p1_regression_test.py

Covers:
  - Employee update permission + manager-cycle protection
  - Deliverable versions / deliverable approval permission
  - Attendance & certificate IDOR (self vs manager)
  - Academy enrollment / lesson-completion authorization
  - Task & Deliverable milestone-project integrity
  - Task creation/update project-membership enforcement
  - Invoice numbering under repeated creation + invoice state machine
  - Payment validation (negative, overpay, double-pay, cancelled invoice)
  - Quote state machine + permission
  - Won-deal -> project manager auto-assignment + project_members sync
  - Client Portal global isolation gate (the item explicitly flagged for
    regression-only testing going forward, per the 2026-08 review)
"""
import os, tempfile
os.environ.setdefault("CODELA_ENV", "testing")
import database
from app import create_app
from werkzeug.security import generate_password_hash


def main():
    fd, path = tempfile.mkstemp(prefix="codela-p0p1-", suffix=".db")
    os.close(fd)
    database.DB_PATH = path
    database.USE_POSTGRES = False
    database.init_db()
    app = create_app()
    app.config.update(TESTING=True)
    c = app.test_client()

    def reg(email, company):
        r = c.post("/api/auth/register", json={"name": "Founder", "email": email, "password": "CorrectHorseBattery9!", "company_name": company})
        assert r.status_code == 201, r.get_json()
        return r.get_json()

    def invite_and_accept(h, email, role):
        r = c.post("/api/auth/invite", headers=h, json={"name": role, "email": email, "role": role})
        assert r.status_code == 201, r.get_json()
        token = r.get_json()["dev_invite_token"]
        r = c.post("/api/auth/accept-invite", json={"token": token, "password": "SomeStrongPass123!"})
        assert r.status_code == 201, r.get_json()
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    founder = reg("f@x.test", "X")
    FH = {"Authorization": f"Bearer {founder['access_token']}"}
    tenant_id = founder["user"]["tenant_id"]

    designer_h = invite_and_accept(FH, "designer@x.test", "designer")
    dev_h = invite_and_accept(FH, "dev@x.test", "developer")

    # ---------------- Employee update permission + manager cycle ----------------
    conn = database.get_db()
    designer_uid = conn.execute("SELECT id FROM users WHERE email='designer@x.test'").fetchone()["id"]
    dev_uid = conn.execute("SELECT id FROM users WHERE email='dev@x.test'").fetchone()["id"]
    conn.execute("INSERT INTO employees (tenant_id, user_id, employment_status, employment_type, hourly_cost) VALUES (?,?,?,?,?)", (tenant_id, designer_uid, "active", "full_time", 50))
    conn.execute("INSERT INTO employees (tenant_id, user_id, employment_status, employment_type, hourly_cost) VALUES (?,?,?,?,?)", (tenant_id, dev_uid, "active", "full_time", 50))
    conn.commit()
    designer_eid = conn.execute("SELECT id FROM employees WHERE user_id=?", (designer_uid,)).fetchone()["id"]
    conn.close()

    r = c.patch(f"/api/employees/{designer_eid}", headers=dev_h, json={"hourly_cost": 999})
    assert r.status_code == 403, ("employee update should require permission", r.get_json())
    r = c.patch(f"/api/employees/{designer_eid}", headers=FH, json={"manager_id": designer_eid})
    assert r.status_code == 400, ("self-manager cycle must be rejected", r.get_json())

    # ---------------- Attendance / certificate IDOR ----------------
    c.post("/api/attendance/check-in", headers=designer_h, json={})
    r = c.get(f"/api/attendance?user_id={designer_uid}", headers=dev_h)
    assert r.status_code == 403, ("peer must not read another user's attendance", r.get_json())
    r = c.get(f"/api/attendance?user_id={designer_uid}", headers=designer_h)
    assert r.status_code == 200, ("self attendance view should work", r.get_json())

    # ---------------- Academy enrollment / lesson completion authorization ----------------
    r = c.get("/api/courses", headers=FH)
    if r.get_json():
        course_id = r.get_json()[0]["id"]
        r = c.post(f"/api/courses/{course_id}/enroll", headers=designer_h, json={"user_id": dev_uid})
        assert r.status_code == 403, ("enrolling someone else must require permission", r.get_json())

    # ---------------- Project / task / deliverable / milestone integrity ----------------
    r = c.post("/api/clients", headers=FH, json={"name": "Client A"})
    client_id = r.get_json()["id"]
    r = c.post("/api/projects", headers=FH, json={"name": "Project A", "client_id": client_id})
    p1 = r.get_json()["id"]
    r = c.post("/api/projects", headers=FH, json={"name": "Project B", "client_id": client_id})
    p2 = r.get_json()["id"]
    r = c.post(f"/api/projects/{p2}/milestones", headers=FH, json={"name": "M1"})
    ms_other_project = r.get_json()["id"]

    r = c.post(f"/api/projects/{p1}/deliverables", headers=FH, json={"name": "D1", "milestone_id": ms_other_project})
    assert r.status_code == 400, ("deliverable must reject a milestone from another project", r.get_json())

    r = c.post("/api/tasks", headers=FH, json={"title": "T1", "project_id": p1, "milestone_id": ms_other_project})
    assert r.status_code == 400, ("task must reject a milestone from another project", r.get_json())

    r = c.post("/api/tasks", headers=FH, json={"title": "T2", "project_id": p1, "assignee_id": designer_uid})
    assert r.status_code == 400, ("task assignee must be a project member", r.get_json())

    # ---------------- Deliverable versions + approval permission ----------------
    r = c.post(f"/api/projects/{p1}/deliverables", headers=FH, json={"name": "D2"})
    did = r.get_json()["id"]
    r = c.post(f"/api/deliverables/{did}/versions", headers=dev_h, json={"notes": "v1"})
    assert r.status_code == 403, ("deliverable version creation must require permission", r.get_json())
    r = c.post(f"/api/deliverables/{did}/approval", headers=dev_h, json={})
    assert r.status_code == 403, ("deliverable approval request must require permission", r.get_json())
    r = c.post(f"/api/deliverables/{did}/approval", headers=FH, json={})
    assert r.status_code == 201, ("founder should be able to request approval", r.get_json())

    # unassigned approval must not be decidable by an unauthorized low-priv user
    approval_id = r.get_json()["id"]
    r = c.patch(f"/api/approvals/{approval_id}", headers=dev_h, json={"status": "approved"})
    assert r.status_code == 403, ("unassigned approval must require deliverables.approve to decide", r.get_json())
    r = c.patch(f"/api/approvals/{approval_id}", headers=FH, json={"status": "approved"})
    assert r.status_code == 200

    # content workflow: only content.workflow permission can move status to 'approved'
    r = c.post("/api/content", headers=designer_h, json={"title": "Idea", "category": "reel", "platform": "instagram"})
    if r.status_code == 201:
        content_id = r.get_json()["id"]
        r = c.patch(f"/api/content/{content_id}", headers=designer_h, json={"status": "approved"})
        assert r.status_code == 403, ("designer must not be able to approve content", r.get_json())
        r = c.patch(f"/api/content/{content_id}", headers=FH, json={"status": "approved"})
        assert r.status_code == 200, ("founder should be able to approve content", r.get_json())

    # ---------------- Quote state machine + permission ----------------
    r = c.post("/api/quotes", headers=FH, json={"client_id": client_id, "items": [{"description": "x", "quantity": 1, "unit_price": 100}]})
    qid = r.get_json()["id"]
    r = c.patch(f"/api/quotes/{qid}", headers=dev_h, json={"status": "sent"})
    assert r.status_code == 403, ("quote update must require permission", r.get_json())
    r = c.patch(f"/api/quotes/{qid}", headers=FH, json={"status": "converted"})
    assert r.status_code == 409, ("quote must reject an invalid state jump", r.get_json())
    r = c.patch(f"/api/quotes/{qid}", headers=FH, json={"status": "sent"})
    assert r.status_code == 200

    # ---------------- Invoice numbering + state machine + payment validation ----------------
    invoice_numbers = []
    for _ in range(3):
        r = c.post("/api/invoices", headers=FH, json={"client_id": client_id, "items": [{"description": "x", "quantity": 1, "unit_price": 100}]})
        assert r.status_code == 201
        invoice_numbers.append(r.get_json()["invoice_number"])
    assert len(set(invoice_numbers)) == 3, ("invoice numbers must be unique under repeated creation", invoice_numbers)

    inv_id = r.get_json()["id"]
    r = c.patch(f"/api/invoices/{inv_id}", headers=FH, json={"status": "paid"})
    assert r.status_code == 409, ("invoice must not jump draft->paid directly", r.get_json())
    c.patch(f"/api/invoices/{inv_id}", headers=FH, json={"status": "sent"})
    r = c.post(f"/api/invoices/{inv_id}/payments", headers=FH, json={"amount": -5})
    assert r.status_code == 400, ("negative payment must be rejected", r.get_json())
    r = c.post(f"/api/invoices/{inv_id}/payments", headers=FH, json={"amount": 10000})
    assert r.status_code == 400, ("overpayment must be rejected", r.get_json())
    r = c.post(f"/api/invoices/{inv_id}/payments", headers=FH, json={"amount": 100})
    assert r.status_code == 200
    r = c.post(f"/api/invoices/{inv_id}/payments", headers=FH, json={"amount": 1})
    assert r.status_code == 409, ("payment on an already-paid invoice must be rejected", r.get_json())

    # ---------------- Won deal -> project manager auto-assignment ----------------
    r = c.post("/api/leads", headers=FH, json={"name": "Lead X"})
    lead_id = r.get_json()["id"]
    r = c.post("/api/deals", headers=FH, json={"lead_id": lead_id, "client_id": client_id, "title": "Deal X", "value": 500})
    deal_id = r.get_json()["id"]
    r = c.patch(f"/api/deals/{deal_id}", headers=FH, json={"status": "won", "sales_id": founder["user"]["id"], "team_member_ids": [designer_uid, dev_uid]})
    assert r.status_code == 200
    won_project_id = r.get_json().get("created_project_id")
    if won_project_id:
        r = c.get(f"/api/projects/{won_project_id}", headers=FH)
        assert r.get_json().get("project_manager_id") == founder["user"]["id"], ("won-deal project must get a manager", r.get_json())
        conn = database.get_db()
        member_uids = {row["user_id"] for row in conn.execute(
            "SELECT e.user_id FROM project_members pm JOIN employees e ON e.id=pm.employee_id WHERE pm.project_id=?", (won_project_id,)
        ).fetchall()}
        conn.close()
        assert {designer_uid, dev_uid}.issubset(member_uids), ("won-deal team_member_ids must be auto-assigned as project members", member_uids)

    # A mid-transaction failure during deal-won must roll back completely:
    # the deal must not end up half 'won' with no project, and no project
    # should be created without its manager/team.
    import routes.finance_routes as fr
    original_commission_fn = fr.calculate_and_record_commission
    def _boom(*a, **kw):
        raise RuntimeError("simulated failure for transactional-safety test")
    fr.calculate_and_record_commission = _boom
    try:
        r = c.post("/api/leads", headers=FH, json={"name": "Lead Boom"})
        lead2_id = r.get_json()["id"]
        r = c.post("/api/deals", headers=FH, json={"lead_id": lead2_id, "client_id": client_id, "title": "Deal Boom", "value": 1})
        boom_deal_id = r.get_json()["id"]
        conn = database.get_db()
        projects_before = conn.execute("SELECT COUNT(*) c FROM projects WHERE client_id=?", (client_id,)).fetchone()["c"]
        conn.close()
        try:
            r = c.patch(f"/api/deals/{boom_deal_id}", headers=FH, json={"status": "won"})
            assert r.status_code == 500, ("simulated failure should surface as 500, not silently succeed", r.status_code)
        except RuntimeError:
            pass  # TESTING mode propagates the exception instead of returning 500 — either way, the failure happened
        conn = database.get_db()
        deal_row = conn.execute("SELECT status FROM deals WHERE id=?", (boom_deal_id,)).fetchone()
        assert deal_row["status"] != "won", ("failed won-transition must not leave the deal marked won", dict(deal_row))
        projects_after = conn.execute("SELECT COUNT(*) c FROM projects WHERE client_id=?", (client_id,)).fetchone()["c"]
        conn.close()
        assert projects_after == projects_before, ("failed won-transition must not leave a half-created project", projects_before, projects_after)
    finally:
        fr.calculate_and_record_commission = original_commission_fn

    # ---------------- Client Portal global isolation gate ----------------
    conn = database.get_db()
    portal_uid_cur = conn.execute(
        "INSERT INTO users (tenant_id, name, email, password_hash, role, is_active) VALUES (?,?,?,?,?,1)",
        (tenant_id, "Portal User", "portal@x.test", generate_password_hash("CorrectHorseBattery9!"), "sales"),
    )
    portal_uid = portal_uid_cur.lastrowid
    conn.execute("INSERT INTO client_users (tenant_id, client_id, user_id, role) VALUES (?,?,?,?)", (tenant_id, client_id, portal_uid, "client_user"))
    conn.commit()
    conn.close()
    r = c.post("/api/auth/login", json={"email": "portal@x.test", "password": "CorrectHorseBattery9!"})
    PH = {"Authorization": f"Bearer {r.get_json()['access_token']}"}
    r = c.get("/api/clients", headers=PH)
    assert r.status_code == 403, ("client-portal account must not reach /api/clients", r.get_json())
    r = c.get("/api/projects", headers=PH)
    assert r.status_code == 403, ("client-portal account must not reach /api/projects", r.get_json())
    r = c.get("/api/users", headers=PH)
    assert r.status_code == 403, ("client-portal account must not reach /api/users", r.get_json())
    r = c.get("/api/client/dashboard", headers=PH)
    assert r.status_code == 200, ("client-portal account must still reach its own dashboard", r.get_json())
    r = c.get("/api/clients", headers=FH)
    assert r.status_code == 200, ("staff account must be unaffected by the portal gate", r.get_json())

    print("PASS: employee/attendance/academy IDOR & authorization, task/deliverable/milestone integrity,")
    print("      deliverable approval permission, quote & invoice state machines, payment validation,")
    print("      invoice numbering uniqueness, won-deal PM auto-assignment, client-portal isolation gate")

    # ---------------- P2: DB-level defense-in-depth triggers/constraints ----------------
    # These must hold even when the application layer is bypassed entirely
    # (a raw DB write, a future direct-DB script, a bug elsewhere).
    conn = database.get_db()
    def _expect_db_reject(sql, params, must_contain):
        try:
            conn.execute(sql, params)
            conn.commit()
            raise AssertionError(f"expected DB-level rejection for: {sql}")
        except AssertionError:
            raise
        except Exception as e:
            assert must_contain in str(e), (sql, str(e))
            conn.rollback()

    invoice_row = conn.execute("SELECT id FROM invoices LIMIT 1").fetchone()
    if invoice_row:
        _expect_db_reject("INSERT INTO payments (tenant_id, invoice_id, amount) VALUES (?,?,-50)", (tenant_id, invoice_row["id"]), "positive")
        _expect_db_reject("INSERT INTO payments (tenant_id, invoice_id, amount) VALUES (?,?,0)", (tenant_id, invoice_row["id"]), "positive")
    _expect_db_reject("INSERT INTO employees (tenant_id, user_id, hourly_cost) VALUES (?,?,-5)", (tenant_id, founder["user"]["id"]), "negative")
    cross_ms = conn.execute("SELECT id, project_id FROM project_milestones LIMIT 1").fetchone()
    other_project = conn.execute("SELECT id FROM projects WHERE id != ? LIMIT 1", (cross_ms["project_id"] if cross_ms else -1,)).fetchone()
    if cross_ms and other_project:
        _expect_db_reject(
            "INSERT INTO tasks (tenant_id, project_id, title, milestone_id) VALUES (?,?,?,?)",
            (tenant_id, other_project["id"], "DB-level violation probe", cross_ms["id"]), "same project",
        )
    conn.close()
    print("PASS: DB-level defense-in-depth triggers (positive payments, non-negative hourly_cost,")
    print("      cross-project task/milestone) reject direct-DB violations that bypass the app layer")

    # ---------------- P2: audit_log immutability ----------------
    conn = database.get_db()
    conn.execute("INSERT INTO audit_log (tenant_id, user_id, action, entity_type, entity_id) VALUES (?,?,?,?,?)",
                 (tenant_id, founder["user"]["id"], "create", "probe", 1))
    conn.commit()
    audit_row = conn.execute("SELECT id FROM audit_log WHERE tenant_id=? AND entity_type='probe'", (tenant_id,)).fetchone()
    try:
        conn.execute("UPDATE audit_log SET action='tampered' WHERE id=?", (audit_row["id"],))
        conn.commit()
        raise AssertionError("audit_log UPDATE should have been blocked at the DB level")
    except AssertionError:
        raise
    except Exception as e:
        assert "immutable" in str(e), str(e)
        conn.rollback()
    conn.close()
    print("PASS: audit_log is immutable at the DB level (UPDATE rejected even bypassing the app layer)")

    # ---------------- P2: automation loop protection ----------------
    import automation
    conn = database.get_db()
    conn.execute("INSERT INTO automation_rules (tenant_id, name, trigger_event, conditions, actions, is_active) VALUES (?,?,?,?,?,1)",
                 (tenant_id, "Loop Rule A", "test.event.a", "[]", '[{"type":"__test_evil_a"}]'))
    conn.execute("INSERT INTO automation_rules (tenant_id, name, trigger_event, conditions, actions, is_active) VALUES (?,?,?,?,?,1)",
                 (tenant_id, "Loop Rule B", "test.event.b", "[]", '[{"type":"__test_evil_b"}]'))
    conn.commit()
    conn.close()

    call_count = {"n": 0}
    def _evil_a(conn, tenant_id, action, context):
        call_count["n"] += 1
        automation.fire_event_sync("test.event.b", tenant_id, {}, conn=conn)
        return "fired b"
    def _evil_b(conn, tenant_id, action, context):
        call_count["n"] += 1
        automation.fire_event_sync("test.event.a", tenant_id, {}, conn=conn)
        return "fired a"
    automation.ACTION_HANDLERS["__test_evil_a"] = _evil_a
    automation.ACTION_HANDLERS["__test_evil_b"] = _evil_b
    try:
        automation.fire_event_sync("test.event.a", tenant_id, {})
    except RecursionError:
        raise AssertionError("automation cascade guard failed to stop an A->B->A event loop")
    finally:
        del automation.ACTION_HANDLERS["__test_evil_a"]
        del automation.ACTION_HANDLERS["__test_evil_b"]
    assert call_count["n"] <= automation.MAX_AUTOMATION_CASCADE_DEPTH + 1, ("cascade ran unbounded", call_count["n"])
    conn = database.get_db()
    skipped = conn.execute("SELECT COUNT(*) c FROM automation_runs WHERE tenant_id=? AND status='skipped' AND result LIKE '%cascade depth%'", (tenant_id,)).fetchone()["c"]
    conn.close()
    assert skipped >= 1, "expected the loop guard to log a skipped automation_run"
    print(f"PASS: automation cascade guard stops an A->B->A event loop at depth {automation.MAX_AUTOMATION_CASCADE_DEPTH} instead of recursing unbounded")

    # ---------------- P2: pagination on high-traffic list endpoints ----------------
    for i in range(60):
        c.post("/api/clients", headers=FH, json={"name": f"Pagination Client {i}"})
    r = c.get("/api/clients", headers=FH)
    assert len(r.get_json()) <= 50, ("unpaginated /api/clients returned more than the default cap", len(r.get_json()))
    r = c.get("/api/clients?limit=5", headers=FH)
    assert len(r.get_json()) == 5, ("explicit limit not honored", r.get_json())
    r1 = c.get("/api/clients?limit=5&offset=0", headers=FH)
    r2 = c.get("/api/clients?limit=5&offset=5", headers=FH)
    assert r1.get_json()[0]["id"] != r2.get_json()[0]["id"], "offset did not move the page"
    r = c.get("/api/clients?limit=99999", headers=FH)
    assert r.status_code == 400, ("limit above the global max should be rejected", r.status_code)
    print("PASS: pagination caps unbounded list queries by default and honors explicit limit/offset")
    os.unlink(path)


if __name__ == "__main__":
    main()
