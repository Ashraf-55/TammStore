from flask import Blueprint, request, jsonify, g
import json
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists, pagination_params
from auth import login_required, log_action
from policies.permissions import require_permission
from automation import fire_event

crm_bp = Blueprint("crm", __name__)

LEAD_STATUSES = ("new", "contacted", "qualified", "meeting", "proposal", "negotiation", "won", "lost")


def compute_lead_score(lead):
    """Simple weighted lead scoring 0-100 based on budget, status progress, industry presence."""
    score = 0
    budget = lead.get("budget") or 0
    if budget >= 100000:
        score += 35
    elif budget >= 30000:
        score += 25
    elif budget > 0:
        score += 10

    status_weight = {
        "new": 5, "contacted": 15, "qualified": 30, "meeting": 45,
        "proposal": 60, "negotiation": 75, "won": 100, "lost": 0,
    }
    score += status_weight.get(lead.get("status", "new"), 5) * 0.5

    if lead.get("industry"):
        score += 5
    if lead.get("service_interested"):
        score += 5
    if lead.get("source") in ("referral", "website"):
        score += 5

    score = min(int(score), 100)
    tier = "hot" if score >= 70 else "warm" if score >= 40 else "cold"
    return score, tier


# ---------------- LEADS ----------------

@crm_bp.route("/leads", methods=["GET"])
@login_required
def list_leads():
    tenant_id = g.current_user["tenant_id"]
    status = request.args.get("status")
    tier = request.args.get("tier")
    assigned = request.args.get("assigned_sales_id")
    conn = get_db()
    query = "SELECT * FROM leads WHERE tenant_id = ?"
    params = [tenant_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    if tier:
        query += " AND score_tier = ?"
        params.append(tier)
    if assigned:
        query += " AND assigned_sales_id = ?"
        params.append(assigned)
    query += " ORDER BY score DESC, created_at DESC"
    limit, offset = pagination_params(request)
    query += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@crm_bp.route("/leads/<int:lead_id>", methods=["GET"])
@login_required
def get_lead(lead_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id=? AND tenant_id=?", (lead_id, tenant_id)).fetchone()
    if lead is None:
        conn.close()
        return jsonify({"error": "Lead not found"}), 404
    activities = conn.execute(
        "SELECT * FROM lead_activities WHERE lead_id=? AND tenant_id=? ORDER BY created_at DESC", (lead_id, tenant_id)
    ).fetchall()
    conn.close()
    result = row_to_dict(lead)
    result["activities"] = rows_to_list(activities)
    return jsonify(result)


@crm_bp.route("/leads", methods=["POST"])
@login_required
@require_permission("crm.manage")
def create_lead():
    from routes.billing_routes import check_usage_limit
    _probe_conn = get_db()
    allowed, used, limit = check_usage_limit(_probe_conn, g.current_user["tenant_id"], "leads")
    _probe_conn.close()
    if not allowed:
        return jsonify({"error": f"Plan limit reached: {used}/{limit} leads used. Upgrade your plan to add more.",
                         "code": "plan_limit_reached"}), 402
    data = request.get_json(force=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    tenant_id = g.current_user["tenant_id"]

    score, tier = compute_lead_score(data)
    conn = get_db()
    if data.get("assigned_sales_id") and not tenant_resource_exists(conn, "users", data["assigned_sales_id"], tenant_id):
        conn.close()
        return jsonify({"error": "assigned_sales_id must belong to this workspace"}), 400
    cur = conn.execute(
        """INSERT INTO leads (tenant_id, name, company, phone, whatsapp, email, industry, source,
           assigned_sales_id, service_interested, budget, status, score, score_tier, notes, next_followup)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            tenant_id, data.get("name"), data.get("company"), data.get("phone"), data.get("whatsapp"),
            data.get("email"), data.get("industry"), data.get("source"),
            data.get("assigned_sales_id"), data.get("service_interested"), data.get("budget"),
            data.get("status", "new"), score, tier, data.get("notes"), data.get("next_followup"),
        ),
    )
    conn.commit()
    lead_id = cur.lastrowid

    if data.get("assigned_sales_id"):
        conn.execute(
            "INSERT INTO notifications (tenant_id, user_id, type, message, link) VALUES (?,?,?,?,?)",
            (tenant_id, data["assigned_sales_id"], "new_lead", f"New lead assigned: {data.get('name')}", f"/leads/{lead_id}"),
        )
        conn.commit()

    row = conn.execute("SELECT * FROM leads WHERE id=? AND tenant_id=?", (lead_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "lead", lead_id)
    lead_dict = row_to_dict(row)
    fire_event("lead.created", tenant_id, {"lead": lead_dict})
    if lead_dict.get("assigned_sales_id"):
        fire_event("lead.assigned", tenant_id, {"lead": lead_dict})
    return jsonify(lead_dict), 201


@crm_bp.route("/leads/<int:lead_id>", methods=["PATCH"])
@login_required
@require_permission("crm.manage")
def update_lead(lead_id):
    data = request.get_json(force=True) or {}
    if "status" in data and data["status"] not in LEAD_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of {LEAD_STATUSES}"}), 400
    tenant_id = g.current_user["tenant_id"]

    conn = get_db()
    if "assigned_sales_id" in data and data["assigned_sales_id"] and not tenant_resource_exists(conn, "users", data["assigned_sales_id"], tenant_id):
        conn.close()
        return jsonify({"error": "assigned_sales_id must belong to this workspace"}), 400
    existing = conn.execute("SELECT * FROM leads WHERE id=? AND tenant_id=?", (lead_id, tenant_id)).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Lead not found"}), 404

    merged = dict(existing)
    merged.update(data)
    score, tier = compute_lead_score(merged)

    fields, values = [], []
    updatable = ("name", "company", "phone", "whatsapp", "email", "industry", "source",
                 "assigned_sales_id", "service_interested", "budget", "status", "notes", "next_followup")
    for key in updatable:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    fields += ["score = ?", "score_tier = ?", "updated_at = datetime('now')"]
    values += [score, tier, lead_id, tenant_id]

    conn.execute(f"UPDATE leads SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM leads WHERE id=? AND tenant_id=?", (lead_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "lead", lead_id, details=str(data))
    lead_dict = row_to_dict(row)
    if "assigned_sales_id" in data and data["assigned_sales_id"] and data["assigned_sales_id"] != existing["assigned_sales_id"]:
        fire_event("lead.assigned", tenant_id, {"lead": lead_dict})
    return jsonify(lead_dict)


@crm_bp.route("/leads/<int:lead_id>/activities", methods=["POST"])
@login_required
def add_lead_activity(lead_id):
    data = request.get_json(force=True) or {}
    activity_type = data.get("type", "note")
    if activity_type not in ("call", "message", "meeting", "note", "followup"):
        return jsonify({"error": "Invalid activity type"}), 400
    tenant_id = g.current_user["tenant_id"]

    conn = get_db()
    if not tenant_resource_exists(conn,"leads",lead_id,tenant_id): conn.close(); return jsonify({"error":"Lead not found"}),404
    cur = conn.execute(
        "INSERT INTO lead_activities (tenant_id, lead_id, user_id, type, content) VALUES (?,?,?,?,?)",
        (tenant_id, lead_id, g.current_user["user_id"], activity_type, data.get("content")),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM lead_activities WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@crm_bp.route("/leads/<int:lead_id>/convert", methods=["POST"])
@login_required
@require_permission("crm.manage")
def convert_lead_to_client(lead_id):
    """Convert a won lead into a client record."""
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id=? AND tenant_id=?", (lead_id, tenant_id)).fetchone()
    if lead is None:
        conn.close()
        return jsonify({"error": "Lead not found"}), 404

    data = request.get_json(force=True) or {}
    if data.get("account_manager_id") and not tenant_resource_exists(conn,"users",data["account_manager_id"],tenant_id):
        conn.close(); return jsonify({"error":"account_manager_id must belong to this workspace"}),400
    cur = conn.execute(
        "INSERT INTO clients (tenant_id, lead_id, name, company, phone, email, account_manager_id, industry) VALUES (?,?,?,?,?,?,?,?)",
        (tenant_id, lead_id, lead["name"], lead["company"], lead["phone"], lead["email"],
         data.get("account_manager_id", lead["assigned_sales_id"]), lead["industry"]),
    )
    conn.execute("UPDATE leads SET status='won', updated_at=datetime('now') WHERE id=? AND tenant_id=?", (lead_id, tenant_id))
    conn.commit()
    client_id = cur.lastrowid
    row = conn.execute("SELECT * FROM clients WHERE id=? AND tenant_id=?", (client_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "convert", "lead_to_client", lead_id)
    return jsonify(row_to_dict(row)), 201


# ---------------- CLIENTS ----------------

@crm_bp.route("/clients", methods=["GET"])
@login_required
def list_clients():
    conn = get_db()
    limit, offset = pagination_params(request)
    rows = conn.execute("SELECT * FROM clients WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (g.current_user["tenant_id"], limit, offset)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@crm_bp.route("/clients/<int:client_id>", methods=["GET"])
@login_required
def get_client(client_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id=? AND tenant_id=?", (client_id, tenant_id)).fetchone()
    if client is None:
        conn.close()
        return jsonify({"error": "Client not found"}), 404
    projects = conn.execute("SELECT * FROM projects WHERE client_id=? AND tenant_id=?", (client_id, tenant_id)).fetchall()
    deals = conn.execute("SELECT * FROM deals WHERE client_id=? AND tenant_id=?", (client_id, tenant_id)).fetchall()
    invoices = conn.execute("SELECT * FROM finance_transactions WHERE client_id=? AND tenant_id=?", (client_id, tenant_id)).fetchall()
    conn.close()
    result = row_to_dict(client)
    result["projects"] = rows_to_list(projects)
    result["deals"] = rows_to_list(deals)
    result["transactions"] = rows_to_list(invoices)
    return jsonify(result)


@crm_bp.route("/clients", methods=["POST"])
@login_required
@require_permission("crm.manage")
def create_client():
    data = request.get_json(force=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    for fk,table in (("lead_id","leads"),("account_manager_id","users")):
        if data.get(fk) and not tenant_resource_exists(conn,table,data[fk],tenant_id): conn.close(); return jsonify({"error":f"{fk} must belong to this workspace"}),400
    cur = conn.execute(
        "INSERT INTO clients (tenant_id, lead_id, name, company, phone, email, account_manager_id, industry, notes) VALUES (?,?,?,?,?,?,?,?,?)",
        (tenant_id, data.get("lead_id"), data.get("name"), data.get("company"), data.get("phone"),
         data.get("email"), data.get("account_manager_id"), data.get("industry"), data.get("notes")),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM clients WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "client", cur.lastrowid)
    return jsonify(row_to_dict(row)), 201


# ---------------- DEALS ----------------

@crm_bp.route("/deals", methods=["GET"])
@login_required
def list_deals():
    tenant_id = g.current_user["tenant_id"]
    status = request.args.get("status")
    conn = get_db()
    limit, offset = pagination_params(request)
    if status:
        rows = conn.execute("SELECT * FROM deals WHERE tenant_id=? AND status=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (tenant_id, status, limit, offset)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM deals WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (tenant_id, limit, offset)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@crm_bp.route("/deals", methods=["POST"])
@login_required
@require_permission("crm.manage")
def create_deal():
    data = request.get_json(force=True) or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    for fk, table in (("lead_id", "leads"), ("client_id", "clients"), ("sales_id", "users")):
        if data.get(fk) and not tenant_resource_exists(conn, table, data[fk], tenant_id):
            conn.close()
            return jsonify({"error": f"{fk} must belong to this workspace"}), 400
    cur = conn.execute(
        "INSERT INTO deals (tenant_id, lead_id, client_id, title, value, status, sales_id) VALUES (?,?,?,?,?,?,?)",
        (tenant_id, data.get("lead_id"), data.get("client_id"), data.get("title"),
         data.get("value", 0), data.get("status", "open"), data.get("sales_id")),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM deals WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "deal", cur.lastrowid)
    return jsonify(row_to_dict(row)), 201


@crm_bp.route("/deals/<int:deal_id>", methods=["PATCH"])
@login_required
@require_permission("crm.manage")
def update_deal(deal_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    fields, values = [], []
    for key in ("title", "value", "status", "sales_id"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if data.get("status") in ("won", "lost"):
        fields.append("closed_at = datetime('now')")
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    values += [deal_id, tenant_id]

    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM deals WHERE id=? AND tenant_id=?", (deal_id, tenant_id)).fetchone()
        if existing is None:
            return jsonify({"error": "Deal not found"}), 404
        if data.get("sales_id") and not tenant_resource_exists(conn, "users", data["sales_id"], tenant_id):
            return jsonify({"error": "sales_id must belong to this workspace"}), 400
        conn.execute(f"UPDATE deals SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)

        commission_amount = 0
        created_project_id = None
        team_assigned_count = 0
        if data.get("status") == "won":
            from routes.finance_routes import calculate_and_record_commission
            deal = row_to_dict(conn.execute("SELECT * FROM deals WHERE id=? AND tenant_id=?", (deal_id, tenant_id)).fetchone())
            # A won deal is a sales commitment, not cash received. Do not book it
            # as finance income here; actual cash is recorded by invoice payments.
            commission_amount = calculate_and_record_commission(conn, tenant_id, deal)
            # Operational handoff: a won deal must have a delivery project. Reuse an
            # existing project linked to this deal when possible; otherwise create a
            # kickoff project without inventing invoice terms.
            #
            # NOTE (scope): the fuller "Client confirmed -> Contract -> Kickoff"
            # workflow described in the original audit needs a Contracts entity
            # that does not exist yet in this codebase (tracked as a separate,
            # larger P3 module). This handler covers everything achievable
            # without that module: PM assignment, team assignment, and an
            # all-or-nothing DB transaction (see try/except around this whole
            # block) so a failure partway through never leaves a deal marked
            # 'won' without its project, or a project without its PM/team.
            existing_project = conn.execute("SELECT id FROM projects WHERE tenant_id=? AND client_id=? AND name=? LIMIT 1",(tenant_id,deal.get("client_id"),deal["title"])).fetchone() if deal.get("client_id") else None
            if existing_project:
                created_project_id = existing_project["id"]
            elif deal.get("client_id"):
                # Operational handoff: default the new project's manager to the deal
                # owner (sales_id) so a won deal never hands off to an unowned
                # project. Callers may override via project_manager_id.
                pm_user_id = data.get("project_manager_id") or deal.get("sales_id")
                if pm_user_id and not tenant_resource_exists(conn, "users", pm_user_id, tenant_id):
                    pm_user_id = None
                cur_project = conn.execute("INSERT INTO projects (tenant_id,client_id,name,description,project_manager_id,status,start_date) VALUES (?,?,?,?,?,?,date('now'))",(tenant_id,deal["client_id"],deal["title"],f"Delivery project created from won deal #{deal['id']}",pm_user_id,"active"))
                created_project_id = cur_project.lastrowid
                if pm_user_id:
                    employee = conn.execute("SELECT id FROM employees WHERE tenant_id=? AND user_id=?", (tenant_id, pm_user_id)).fetchone()
                    if employee:
                        conn.execute("INSERT INTO project_members (tenant_id,project_id,employee_id,role) VALUES (?,?,?,?) ON CONFLICT(tenant_id,project_id,employee_id) DO NOTHING", (tenant_id, created_project_id, employee["id"], "project_manager"))
                # Operational handoff, part 2: auto-assign a delivery team.
                # Callers may pass team_member_ids (a list of user_ids) explicitly;
                # any id that isn't a valid, tenant-scoped employee is silently
                # skipped rather than failing the whole won-deal transition.
                for team_user_id in (data.get("team_member_ids") or []):
                    if not tenant_resource_exists(conn, "users", team_user_id, tenant_id):
                        continue
                    team_employee = conn.execute("SELECT id FROM employees WHERE tenant_id=? AND user_id=?", (tenant_id, team_user_id)).fetchone()
                    if team_employee:
                        conn.execute("INSERT INTO project_members (tenant_id,project_id,employee_id,role) VALUES (?,?,?,?) ON CONFLICT(tenant_id,project_id,employee_id) DO NOTHING", (tenant_id, created_project_id, team_employee["id"], "member"))
                        team_assigned_count += 1
                conn.execute(
                    "INSERT INTO project_activities (tenant_id,project_id,actor_user_id,event_type,entity_type,entity_id,payload) VALUES (?,?,?,?,?,?,?)",
                    (tenant_id, created_project_id, g.current_user["user_id"], "project.kickoff_from_won_deal", "deal", deal_id,
                     json.dumps({"project_manager_id": pm_user_id, "team_members_assigned": team_assigned_count})),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    conn = get_db()
    row = conn.execute("SELECT * FROM deals WHERE id=? AND tenant_id=?", (deal_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "deal", deal_id)
    deal_dict = row_to_dict(row)
    if data.get("status") == "won":
        deal_dict["commission_calculated"] = commission_amount
        deal_dict["created_project_id"] = created_project_id
        fire_event("deal.won", tenant_id, {"deal": deal_dict, "project_id": created_project_id})
        if created_project_id:
            fire_event("project.created", tenant_id, {"project_id": created_project_id, "source": "deal.won", "deal_id": deal_id})
    elif data.get("status") == "lost":
        fire_event("deal.lost", tenant_id, {"deal": deal_dict})
    return jsonify(deal_dict)
