"""
Automation Engine routes — Codela OS

CRUD for automation_rules, a visibility log (automation_runs), and the
polling endpoints that turn time-based conditions (task overdue, followup
overdue) into events. There's no background scheduler in this build (no
long-running process management here), so these are exposed as endpoints
meant to be hit by an external cron / uptime pinger / task scheduler — the
same shape as most serverless cron setups.
"""
import json
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, pagination_params
from auth import login_required, roles_required, log_action
from automation import fire_event, ACTION_HANDLERS

automation_bp = Blueprint("automation", __name__)

VALID_EVENTS = (
    "lead.created", "lead.assigned", "deal.won", "deal.lost",
    "task.overdue", "followup.overdue", "request.created", "attendance.flagged",
)


@automation_bp.route("/automation/meta", methods=["GET"])
@login_required
def automation_meta():
    """Lets the frontend build a rule editor without hardcoding the vocabulary."""
    return jsonify({
        "trigger_events": VALID_EVENTS,
        "action_types": list(ACTION_HANDLERS.keys()),
        "condition_operators": ["==", "!=", ">", ">=", "<", "<=", "in", "not_in", "contains", "is_empty", "is_not_empty"],
    })


@automation_bp.route("/automation/rules", methods=["GET"])
@login_required
def list_rules():
    conn = get_db()
    limit, offset = pagination_params(request)
    rows = conn.execute(
        "SELECT * FROM automation_rules WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (g.current_user["tenant_id"], limit, offset)
    ).fetchall()
    conn.close()
    rules = rows_to_list(rows)
    for r in rules:
        r["conditions"] = json.loads(r["conditions"] or "[]")
        r["actions"] = json.loads(r["actions"] or "[]")
    return jsonify(rules)


@automation_bp.route("/automation/rules/<int:rule_id>", methods=["GET"])
@login_required
def get_rule(rule_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM automation_rules WHERE id=? AND tenant_id=?", (rule_id, g.current_user["tenant_id"])).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "Rule not found"}), 404
    rule = row_to_dict(row)
    rule["conditions"] = json.loads(rule["conditions"] or "[]")
    rule["actions"] = json.loads(rule["actions"] or "[]")
    return jsonify(rule)


@automation_bp.route("/automation/rules", methods=["POST"])
@login_required
@roles_required("sales_manager", "project_manager", "accountant")
def create_rule():
    data = request.get_json(force=True) or {}
    name = data.get("name")
    trigger_event = data.get("trigger_event")
    if not name or trigger_event not in VALID_EVENTS:
        return jsonify({"error": f"name is required and trigger_event must be one of {VALID_EVENTS}"}), 400
    for action in data.get("actions", []):
        if action.get("type") not in ACTION_HANDLERS:
            return jsonify({"error": f"Unknown action type: {action.get('type')}"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO automation_rules (tenant_id, name, trigger_event, conditions, actions, is_active, created_by) VALUES (?,?,?,?,?,?,?)",
        (tenant_id, name, trigger_event, json.dumps(data.get("conditions", [])), json.dumps(data.get("actions", [])),
         1 if data.get("is_active", True) else 0, g.current_user["user_id"]),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM automation_rules WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "automation_rule", cur.lastrowid, details=trigger_event)
    result = row_to_dict(row)
    result["conditions"] = json.loads(result["conditions"] or "[]")
    result["actions"] = json.loads(result["actions"] or "[]")
    return jsonify(result), 201


@automation_bp.route("/automation/rules/<int:rule_id>", methods=["PATCH"])
@login_required
@roles_required("sales_manager", "project_manager", "accountant")
def update_rule(rule_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    existing = conn.execute("SELECT * FROM automation_rules WHERE id=? AND tenant_id=?", (rule_id, tenant_id)).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Rule not found"}), 404

    fields, values = [], []
    if "name" in data:
        fields.append("name = ?"); values.append(data["name"])
    if "trigger_event" in data:
        if data["trigger_event"] not in VALID_EVENTS:
            conn.close()
            return jsonify({"error": f"trigger_event must be one of {VALID_EVENTS}"}), 400
        fields.append("trigger_event = ?"); values.append(data["trigger_event"])
    if "conditions" in data:
        fields.append("conditions = ?"); values.append(json.dumps(data["conditions"]))
    if "actions" in data:
        for action in data["actions"]:
            if action.get("type") not in ACTION_HANDLERS:
                conn.close()
                return jsonify({"error": f"Unknown action type: {action.get('type')}"}), 400
        fields.append("actions = ?"); values.append(json.dumps(data["actions"]))
    if "is_active" in data:
        fields.append("is_active = ?"); values.append(1 if data["is_active"] else 0)
    if not fields:
        conn.close()
        return jsonify({"error": "No valid fields"}), 400
    values += [rule_id, tenant_id]
    conn.execute(f"UPDATE automation_rules SET {', '.join(fields)} WHERE id=? AND tenant_id=?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM automation_rules WHERE id=? AND tenant_id=?", (rule_id, g.current_user["tenant_id"])).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "automation_rule", rule_id)
    result = row_to_dict(row)
    result["conditions"] = json.loads(result["conditions"] or "[]")
    result["actions"] = json.loads(result["actions"] or "[]")
    return jsonify(result)


@automation_bp.route("/automation/rules/<int:rule_id>", methods=["DELETE"])
@login_required
@roles_required("sales_manager", "project_manager", "accountant")
def delete_rule(rule_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    conn.execute("DELETE FROM automation_rules WHERE id=? AND tenant_id=?", (rule_id, tenant_id))
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "delete", "automation_rule", rule_id)
    return jsonify({"message": "Rule deleted"})


@automation_bp.route("/automation/runs", methods=["GET"])
@login_required
def list_runs():
    tenant_id = g.current_user["tenant_id"]
    rule_id = request.args.get("rule_id")
    conn = get_db()
    if rule_id:
        rows = conn.execute(
            "SELECT * FROM automation_runs WHERE tenant_id=? AND rule_id=? ORDER BY created_at DESC LIMIT 100",
            (tenant_id, rule_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM automation_runs WHERE tenant_id=? ORDER BY created_at DESC LIMIT 100", (tenant_id,)
        ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@automation_bp.route("/automation/rules/<int:rule_id>/test", methods=["POST"])
@login_required
@roles_required("sales_manager", "project_manager", "accountant")
def test_rule(rule_id):
    """Fires a single rule against a sample context without needing the real
    trigger to happen — lets someone validate a rule from the UI before enabling it."""
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    rule = conn.execute("SELECT * FROM automation_rules WHERE id=? AND tenant_id=?", (rule_id, tenant_id)).fetchone()
    conn.close()
    if rule is None:
        return jsonify({"error": "Rule not found"}), 404
    fire_event(rule["trigger_event"], tenant_id, data.get("context", {}))
    return jsonify({"message": "Rule test fired — check /api/automation/runs for the result"})


# ---------------- polling endpoints (call from an external cron) ----------------

@automation_bp.route("/automation/scan/overdue-tasks", methods=["POST"])
@login_required
@roles_required("project_manager", "sales_manager")
def scan_overdue_tasks():
    """Marks tasks past their deadline (and not done) and fires task.overdue for each."""
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    overdue = conn.execute(
        """SELECT * FROM tasks WHERE tenant_id=? AND status NOT IN ('done')
           AND deadline IS NOT NULL AND deadline < date('now')""",
        (tenant_id,),
    ).fetchall()
    conn.close()
    for task in rows_to_list(overdue):
        fire_event("task.overdue", tenant_id, {"task": task})
    return jsonify({"scanned": len(overdue), "message": f"{len(overdue)} overdue task(s) processed"})


@automation_bp.route("/automation/scan/overdue-followups", methods=["POST"])
@login_required
@roles_required("sales_manager", "project_manager")
def scan_overdue_followups_route():
    from routes.followup_routes import scan_overdue_followups
    count = scan_overdue_followups(g.current_user["tenant_id"])
    return jsonify({"scanned": count, "message": f"{count} overdue follow-up(s) processed"})
