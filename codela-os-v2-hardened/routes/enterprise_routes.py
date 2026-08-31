"""
Enterprise layer — Codela OS

Cross-cutting endpoints that don't belong to a single domain module:
  * global search across the main entities (clients, projects, tasks,
    requests, invoices)
  * KPI/reports overview + per-project profitability, consumed by the Ops
    dashboard in frontend/app.js
  * client-portal read model for /client/dashboard, /client/deliverables,
    /client/invoices (client-portal messaging itself lives in
    routes/completion_routes.py's /client/messages, reused here as-is)
"""
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list
from auth import login_required, log_action
from automation import fire_event

enterprise_bp = Blueprint("enterprise", __name__)


def _client_for_user(conn, tenant_id, user_id):
    return conn.execute(
        """SELECT c.* FROM clients c JOIN client_users cu ON cu.client_id=c.id AND cu.tenant_id=c.tenant_id
           WHERE cu.tenant_id=? AND cu.user_id=? AND cu.is_active=1""",
        (tenant_id, user_id),
    ).fetchone()


# ---------------- GLOBAL SEARCH ----------------

@enterprise_bp.route("/search", methods=["GET"])
@login_required
def global_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])
    tenant_id = g.current_user["tenant_id"]
    like = f"%{q}%"
    conn = get_db()
    results = []

    for row in conn.execute(
        "SELECT id, name, company FROM clients WHERE tenant_id=? AND (name LIKE ? OR company LIKE ?) LIMIT 10",
        (tenant_id, like, like),
    ).fetchall():
        results.append({"type": "client", "label": row["name"] + (f" ({row['company']})" if row["company"] else ""),
                         "status": None, "url": f"/clients/{row['id']}"})

    for row in conn.execute(
        "SELECT id, name, status FROM projects WHERE tenant_id=? AND name LIKE ? LIMIT 10",
        (tenant_id, like),
    ).fetchall():
        results.append({"type": "project", "label": row["name"], "status": row["status"], "url": f"/projects/{row['id']}"})

    for row in conn.execute(
        "SELECT id, title, status FROM tasks WHERE tenant_id=? AND title LIKE ? LIMIT 10",
        (tenant_id, like),
    ).fetchall():
        results.append({"type": "task", "label": row["title"], "status": row["status"], "url": f"/tasks/{row['id']}"})

    for row in conn.execute(
        "SELECT id, title, status FROM requests WHERE tenant_id=? AND title LIKE ? LIMIT 10",
        (tenant_id, like),
    ).fetchall():
        results.append({"type": "request", "label": row["title"], "status": row["status"], "url": f"/requests/{row['id']}"})

    for row in conn.execute(
        "SELECT id, invoice_number, status FROM invoices WHERE tenant_id=? AND invoice_number LIKE ? LIMIT 10",
        (tenant_id, like),
    ).fetchall():
        results.append({"type": "invoice", "label": row["invoice_number"], "status": row["status"], "url": f"/invoices/{row['id']}"})

    conn.close()
    return jsonify(results)


# ---------------- REPORTS / KPI OVERVIEW ----------------

@enterprise_bp.route("/reports/overview", methods=["GET"])
@login_required
def reports_overview():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()

    invoiced = conn.execute(
        "SELECT COALESCE(SUM(total),0) v FROM invoices WHERE tenant_id=? AND status IN ('sent','paid','overdue')",
        (tenant_id,),
    ).fetchone()["v"]
    cash_collected = conn.execute(
        "SELECT COALESCE(SUM(amount),0) v FROM payments p JOIN invoices i ON i.id=p.invoice_id AND i.tenant_id=? WHERE p.tenant_id=?",
        (tenant_id, tenant_id),
    ).fetchone()["v"]
    labor_cost = conn.execute(
        "SELECT COALESCE(SUM(hours*hourly_cost),0) v FROM task_time_entries WHERE tenant_id=?", (tenant_id,)
    ).fetchone()["v"]
    other_costs = conn.execute(
        "SELECT COALESCE(SUM(amount),0) v FROM project_costs WHERE tenant_id=?", (tenant_id,)
    ).fetchone()["v"]
    expenses = conn.execute(
        "SELECT COALESCE(SUM(amount),0) v FROM expenses WHERE tenant_id=?", (tenant_id,)
    ).fetchone()["v"]

    active_projects = conn.execute(
        "SELECT COUNT(*) c FROM projects WHERE tenant_id=? AND status='active'", (tenant_id,)
    ).fetchone()["c"]
    overdue_tasks = conn.execute(
        "SELECT COUNT(*) c FROM tasks WHERE tenant_id=? AND status!='done' AND deadline IS NOT NULL AND deadline < datetime('now')",
        (tenant_id,),
    ).fetchone()["c"]

    clients_count = conn.execute("SELECT COUNT(*) c FROM clients WHERE tenant_id=?", (tenant_id,)).fetchone()["c"]

    open_pipeline = conn.execute(
        "SELECT COALESCE(SUM(value),0) v FROM deals WHERE tenant_id=? AND status='open'", (tenant_id,)
    ).fetchone()["v"]

    conn.close()

    total_cost = float(labor_cost or 0) + float(other_costs or 0) + float(expenses or 0)
    profit = float(cash_collected or 0) - total_cost

    return jsonify({
        "finance": {
            "invoiced": float(invoiced or 0),
            "cash_collected": float(cash_collected or 0),
            "labor_cost": float(labor_cost or 0),
            "other_costs": float(other_costs or 0),
            "expenses": float(expenses or 0),
            "profit": profit,
        },
        "operations": {
            "active_projects": active_projects,
            "overdue_tasks": overdue_tasks,
        },
        "people": {
            "clients": clients_count,
        },
        "sales": {
            "open_pipeline": float(open_pipeline or 0),
        },
    })


@enterprise_bp.route("/reports/projects", methods=["GET"])
@login_required
def reports_projects():
    """Per-project profitability — collected, cost, profit, and task-based progress."""
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    projects = conn.execute(
        "SELECT p.*, c.name AS client_name FROM projects p LEFT JOIN clients c ON c.id=p.client_id AND c.tenant_id=p.tenant_id WHERE p.tenant_id=? ORDER BY p.created_at DESC",
        (tenant_id,),
    ).fetchall()

    result = []
    for p in projects:
        collected = conn.execute(
            "SELECT COALESCE(SUM(amount),0) v FROM payments pay JOIN invoices i ON i.id=pay.invoice_id WHERE pay.tenant_id=? AND i.project_id=?",
            (tenant_id, p["id"]),
        ).fetchone()["v"]
        labor = conn.execute(
            "SELECT COALESCE(SUM(tte.hours*tte.hourly_cost),0) v FROM task_time_entries tte JOIN tasks t ON t.id=tte.task_id AND t.tenant_id=tte.tenant_id WHERE tte.tenant_id=? AND t.project_id=?",
            (tenant_id, p["id"]),
        ).fetchone()["v"]
        other_costs = conn.execute(
            "SELECT COALESCE(SUM(amount),0) v FROM project_costs WHERE tenant_id=? AND project_id=?",
            (tenant_id, p["id"]),
        ).fetchone()["v"]
        costs = float(labor or 0) + float(other_costs or 0)

        task_stats = conn.execute(
            "SELECT COUNT(*) total, SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) done FROM tasks WHERE tenant_id=? AND project_id=?",
            (tenant_id, p["id"]),
        ).fetchone()
        total_tasks = task_stats["total"] or 0
        done_tasks = task_stats["done"] or 0
        progress_pct = round((done_tasks / total_tasks) * 100) if total_tasks else 0

        result.append({
            "id": p["id"],
            "name": p["name"],
            "client_name": p["client_name"],
            "status": p["status"],
            "progress_pct": progress_pct,
            "collected": float(collected or 0),
            "costs": round(costs, 2),
            "profit": round(float(collected or 0) - costs, 2),
        })

    conn.close()
    return jsonify(result)


# ---------------- CLIENT PORTAL READ MODEL ----------------

@enterprise_bp.route("/client/dashboard", methods=["GET"])
@login_required
def client_dashboard():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    client = _client_for_user(conn, tenant_id, g.current_user["user_id"])
    if not client:
        conn.close()
        return jsonify({"error": "Client portal access is not configured for this user"}), 403

    projects = rows_to_list(conn.execute(
        "SELECT id, name, status FROM projects WHERE tenant_id=? AND client_id=?", (tenant_id, client["id"])
    ).fetchall())
    project_ids = [p["id"] for p in projects]

    if project_ids:
        placeholders = ",".join("?" * len(project_ids))
        task_stats = conn.execute(
            f"SELECT COUNT(*) total, SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) done FROM tasks WHERE tenant_id=? AND project_id IN ({placeholders})",
            (tenant_id, *project_ids),
        ).fetchone()
    else:
        task_stats = {"total": 0, "done": 0}

    invoice_stats = conn.execute(
        "SELECT COUNT(*) total, COALESCE(SUM(amount_paid),0) paid FROM invoices WHERE tenant_id=? AND client_id=?",
        (tenant_id, client["id"]),
    ).fetchone()

    requests_count = conn.execute(
        "SELECT COUNT(*) c FROM requests WHERE tenant_id=? AND client_id=?", (tenant_id, client["id"])
    ).fetchone()["c"]

    conn.close()
    return jsonify({
        "projects": projects,
        "tasks": {"total": task_stats["total"] or 0, "done": task_stats["done"] or 0},
        "invoices": {"total": invoice_stats["total"] or 0, "paid": float(invoice_stats["paid"] or 0)},
        "requests": requests_count,
    })


@enterprise_bp.route("/client/deliverables", methods=["GET"])
@login_required
def client_deliverables():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    client = _client_for_user(conn, tenant_id, g.current_user["user_id"])
    if not client:
        conn.close()
        return jsonify({"error": "Client portal access is not configured for this user"}), 403
    rows = conn.execute(
        """SELECT d.*, p.name AS project_name FROM project_deliverables d
           JOIN projects p ON p.id = d.project_id AND p.tenant_id = d.tenant_id
           WHERE d.tenant_id=? AND p.client_id=? ORDER BY d.created_at DESC""",
        (tenant_id, client["id"]),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@enterprise_bp.route("/client/deliverables/<int:deliverable_id>/approval", methods=["POST"])
@login_required
def client_deliverable_approval(deliverable_id):
    data = request.get_json(force=True) or {}
    status = data.get("status")
    if status not in ("approved", "changes_requested"):
        return jsonify({"error": "status must be 'approved' or 'changes_requested'"}), 400

    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    client = _client_for_user(conn, tenant_id, g.current_user["user_id"])
    if not client:
        conn.close()
        return jsonify({"error": "Client portal access is not configured for this user"}), 403

    deliverable = conn.execute(
        """SELECT d.* FROM project_deliverables d JOIN projects p ON p.id=d.project_id AND p.tenant_id=d.tenant_id
           WHERE d.id=? AND d.tenant_id=? AND p.client_id=?""",
        (deliverable_id, tenant_id, client["id"]),
    ).fetchone()
    if not deliverable:
        conn.close()
        return jsonify({"error": "Deliverable not found"}), 404
    if deliverable["status"] != "submitted":
        conn.close()
        return jsonify({"error": "Only submitted deliverables can be reviewed"}), 400

    new_status = "approved" if status == "approved" else "changes_requested"
    conn.execute(
        "UPDATE project_deliverables SET status=?, updated_at=datetime('now') WHERE id=? AND tenant_id=?",
        (new_status, deliverable_id, tenant_id),
    )
    conn.execute(
        """INSERT INTO project_approvals (tenant_id, project_id, deliverable_id, requested_by, approver_id, status, feedback, decided_at)
           VALUES (?,?,?,?,?,?,?,datetime('now'))""",
        (tenant_id, deliverable["project_id"], deliverable_id, deliverable["submitted_by"], g.current_user["user_id"],
         new_status, data.get("feedback")),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM project_deliverables WHERE id=?", (deliverable_id,)).fetchone()
    conn.close()
    fire_event("deliverable.reviewed", tenant_id, {"deliverable_id": deliverable_id, "status": new_status})
    log_action(g.current_user["user_id"], "client_deliverable_review", "project_deliverable", deliverable_id, details=status)
    return jsonify(row_to_dict(row))


@enterprise_bp.route("/client/invoices", methods=["GET"])
@login_required
def client_invoices():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    client = _client_for_user(conn, tenant_id, g.current_user["user_id"])
    if not client:
        conn.close()
        return jsonify({"error": "Client portal access is not configured for this user"}), 403
    rows = conn.execute(
        "SELECT id, invoice_number, status, total, amount_paid, due_date, issue_date FROM invoices WHERE tenant_id=? AND client_id=? ORDER BY issue_date DESC",
        (tenant_id, client["id"]),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))
