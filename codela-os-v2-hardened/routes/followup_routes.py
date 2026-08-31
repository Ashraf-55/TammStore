"""
Follow-up Engine — Codela OS

A Sales Follow-up Sequence is a template: an ordered list of steps
("Follow-up #1, 2h later, WhatsApp", "Follow-up #2, next day, call"...).
Starting a sequence on a lead materializes those steps into concrete
`followups` rows with real due dates, so sales reps get a real queue of
what's due today / overdue instead of relying on memory.
"""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, pagination_params
from auth import login_required, log_action
from automation import fire_event

followup_bp = Blueprint("followups", __name__)

FOLLOWUP_STATUSES = ("pending", "done", "overdue", "skipped", "cancelled")


# ---------------- sequences (templates) ----------------

@followup_bp.route("/followups/sequences", methods=["GET"])
@login_required
def list_sequences():
    conn = get_db()
    seqs = rows_to_list(conn.execute(
        "SELECT * FROM followup_sequences WHERE tenant_id=? ORDER BY created_at DESC", (g.current_user["tenant_id"],)
    ).fetchall())
    for seq in seqs:
        seq["steps"] = rows_to_list(conn.execute(
            "SELECT * FROM followup_steps WHERE sequence_id=? AND tenant_id=? ORDER BY step_order", (seq["id"], g.current_user["tenant_id"])
        ).fetchall())
    conn.close()
    return jsonify(seqs)


@followup_bp.route("/followups/sequences", methods=["POST"])
@login_required
def create_sequence():
    """Body: {name, applies_to?, is_default?, steps: [{step_order, delay_hours, channel, title, message_template}]}"""
    data = request.get_json(force=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()

    if data.get("is_default"):
        conn.execute("UPDATE followup_sequences SET is_default=0 WHERE tenant_id=?", (tenant_id,))

    cur = conn.execute(
        "INSERT INTO followup_sequences (tenant_id, name, applies_to, is_default, is_active) VALUES (?,?,?,?,?)",
        (tenant_id, data["name"], data.get("applies_to", "lead"), 1 if data.get("is_default") else 0,
         1 if data.get("is_active", True) else 0),
    )
    sequence_id = cur.lastrowid
    for i, step in enumerate(data.get("steps", []), start=1):
        conn.execute(
            "INSERT INTO followup_steps (tenant_id, sequence_id, step_order, delay_hours, channel, title, message_template) VALUES (?,?,?,?,?,?,?)",
            (tenant_id, sequence_id, step.get("step_order", i), step.get("delay_hours", 24 * i),
             step.get("channel", "whatsapp"), step.get("title", f"Follow-up #{i}"), step.get("message_template")),
        )
    conn.commit()
    row = conn.execute("SELECT * FROM followup_sequences WHERE id=? AND tenant_id=?", (sequence_id, tenant_id)).fetchone()
    steps = rows_to_list(conn.execute("SELECT * FROM followup_steps WHERE sequence_id=? AND tenant_id=? ORDER BY step_order", (sequence_id, tenant_id)).fetchall())
    conn.close()
    log_action(g.current_user["user_id"], "create", "followup_sequence", sequence_id)
    result = row_to_dict(row)
    result["steps"] = steps
    return jsonify(result), 201


# ---------------- starting / advancing a lead's follow-up track ----------------

def _create_followups_for_sequence(conn, tenant_id, lead_id, sequence_id, assigned_to):
    steps = conn.execute("SELECT * FROM followup_steps WHERE sequence_id=? AND tenant_id=? ORDER BY step_order", (sequence_id, tenant_id)).fetchall()
    created = []
    now = datetime.utcnow()
    for step in steps:
        due_at = (now + timedelta(hours=step["delay_hours"])).isoformat(timespec="seconds")
        cur = conn.execute(
            """INSERT INTO followups (tenant_id, lead_id, sequence_id, step_id, assigned_to, channel, title, message, due_at, status)
               VALUES (?,?,?,?,?,?,?,?,?, 'pending')""",
            (tenant_id, lead_id, sequence_id, step["id"], assigned_to, step["channel"], step["title"],
             step["message_template"], due_at),
        )
        created.append(cur.lastrowid)
    return created


@followup_bp.route("/leads/<int:lead_id>/followups/start", methods=["POST"])
@login_required
def start_followup_sequence(lead_id):
    """Body: {sequence_id?} — omit to use the tenant's default sequence."""
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id=? AND tenant_id=?", (lead_id, tenant_id)).fetchone()
    if lead is None:
        conn.close()
        return jsonify({"error": "Lead not found"}), 404

    sequence_id = data.get("sequence_id")
    if sequence_id:
        owned = conn.execute("SELECT id FROM followup_sequences WHERE id=? AND tenant_id=? AND is_active=1", (sequence_id, tenant_id)).fetchone()
        if owned is None:
            conn.close()
            return jsonify({"error": "Sequence not found"}), 404
    if not sequence_id:
        default = conn.execute("SELECT id FROM followup_sequences WHERE tenant_id=? AND is_default=1 AND is_active=1", (tenant_id,)).fetchone()
        if not default:
            conn.close()
            return jsonify({"error": "No sequence_id given and no default sequence configured"}), 400
        sequence_id = default["id"]

    ids = _create_followups_for_sequence(conn, tenant_id, lead_id, sequence_id, lead["assigned_sales_id"])
    conn.commit()
    rows = rows_to_list(conn.execute(f"SELECT * FROM followups WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall()) if ids else []
    conn.close()
    log_action(g.current_user["user_id"], "start", "followup_sequence", sequence_id, details=f"lead #{lead_id}, {len(ids)} step(s)")
    return jsonify({"message": f"{len(ids)} follow-up(s) scheduled", "followups": rows}), 201


# ---------------- the follow-up queue itself ----------------

@followup_bp.route("/followups", methods=["GET"])
@login_required
def list_followups():
    tenant_id = g.current_user["tenant_id"]
    status = request.args.get("status")
    assigned_to = request.args.get("assigned_to")
    mine = request.args.get("mine")
    conn = get_db()
    query = """SELECT f.*, l.name AS lead_name, l.company AS lead_company
               FROM followups f JOIN leads l ON l.id = f.lead_id WHERE f.tenant_id=?"""
    params = [tenant_id]
    if status:
        query += " AND f.status=?"
        params.append(status)
    if assigned_to:
        query += " AND f.assigned_to=?"
        params.append(assigned_to)
    if mine == "true":
        query += " AND f.assigned_to=?"
        params.append(g.current_user["user_id"])
    query += " ORDER BY f.due_at ASC"
    limit, offset = pagination_params(request)
    query += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@followup_bp.route("/followups/<int:followup_id>/complete", methods=["POST"])
@login_required
def complete_followup(followup_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    fu = conn.execute("SELECT * FROM followups WHERE id=? AND tenant_id=?", (followup_id, tenant_id)).fetchone()
    if fu is None:
        conn.close()
        return jsonify({"error": "Follow-up not found"}), 404
    conn.execute(
        "UPDATE followups SET status='done', completed_at=datetime('now'), completed_by=?, notes=? WHERE id=? AND tenant_id=?",
        (g.current_user["user_id"], data.get("notes"), followup_id, tenant_id),
    )
    conn.execute(
        "INSERT INTO lead_activities (tenant_id, lead_id, user_id, type, content) VALUES (?,?,?,'followup',?)",
        (tenant_id, fu["lead_id"], g.current_user["user_id"], data.get("notes") or f"Completed: {fu['title']}"),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM followups WHERE id=? AND tenant_id=?", (followup_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "complete", "followup", followup_id)
    return jsonify(row_to_dict(row))


@followup_bp.route("/followups/<int:followup_id>/skip", methods=["POST"])
@login_required
def skip_followup(followup_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    conn.execute("UPDATE followups SET status='skipped' WHERE id=? AND tenant_id=?", (followup_id, tenant_id))
    conn.commit()
    row = conn.execute("SELECT * FROM followups WHERE id=? AND tenant_id=?", (followup_id, tenant_id)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "Follow-up not found"}), 404
    return jsonify(row_to_dict(row))


@followup_bp.route("/followups/overdue", methods=["GET"])
@login_required
def overdue_followups():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    rows = conn.execute(
        """SELECT f.*, l.name AS lead_name FROM followups f JOIN leads l ON l.id = f.lead_id
           WHERE f.tenant_id=? AND f.status IN ('pending','overdue') AND f.due_at < ? ORDER BY f.due_at""",
        (tenant_id, datetime.utcnow().isoformat(timespec="seconds")),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


def scan_overdue_followups(tenant_id):
    """Marks pending follow-ups whose due_at has passed as 'overdue' and fires
    followup.overdue for each (so an automation rule can escalate/notify).
    Shared by the /followups/scan endpoint and the automation polling routes."""
    conn = get_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT * FROM followups WHERE tenant_id=? AND status='pending' AND due_at < ?", (tenant_id, now)
    ).fetchall()
    rows = rows_to_list(rows)
    if rows:
        ids = [r["id"] for r in rows]
        conn.execute(f"UPDATE followups SET status='overdue' WHERE id IN ({','.join('?' * len(ids))})", ids)
        conn.commit()
    conn.close()
    for fu in rows:
        fire_event("followup.overdue", tenant_id, {"followup": fu})
    return len(rows)


@followup_bp.route("/followups/scan", methods=["POST"])
@login_required
def scan_followups_route():
    count = scan_overdue_followups(g.current_user["tenant_id"])
    return jsonify({"scanned": count, "message": f"{count} follow-up(s) marked overdue"})
