from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists, pagination_params
from auth import login_required, log_action
from automation import fire_event

requests_bp = Blueprint("requests", __name__)

REQUEST_STATUSES = ("new", "triaged", "in_progress", "resolved", "rejected")


def get_or_create_inbox_project(conn, tenant_id):
    """All auto-generated tasks from Requests land in a single standing project
    (per tenant) so they show up in the normal Projects/Tasks board."""
    row = conn.execute("SELECT id FROM projects WHERE name = 'Requests Inbox' AND tenant_id=?", (tenant_id,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO projects (tenant_id, name, description, status) VALUES (?, 'Requests Inbox', 'Auto-created tasks from submitted requests', 'active')",
        (tenant_id,),
    )
    conn.commit()
    return cur.lastrowid


@requests_bp.route("/requests", methods=["GET"])
@login_required
def list_requests():
    tenant_id = g.current_user["tenant_id"]
    status = request.args.get("status")
    conn = get_db()
    limit, offset = pagination_params(request)
    if status:
        rows = conn.execute("SELECT * FROM requests WHERE tenant_id=? AND status=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (tenant_id, status, limit, offset)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM requests WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (tenant_id, limit, offset)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@requests_bp.route("/requests/<int:request_id>", methods=["GET"])
@login_required
def get_request(request_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM requests WHERE id=? AND tenant_id=?", (request_id, g.current_user["tenant_id"])).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "Request not found"}), 404
    return jsonify(row_to_dict(row))


@requests_bp.route("/requests", methods=["POST"])
@login_required
def create_request():
    """Submitting a request automatically creates a linked Task — this is the
    'model that registers and escalates to a task' automation."""
    data = request.get_json(force=True) or {}
    if not data.get("requester_name") or not data.get("title"):
        return jsonify({"error": "requester_name and title are required"}), 400
    tenant_id = g.current_user["tenant_id"]

    conn = get_db()
    if data.get("client_id") and not tenant_resource_exists(conn, "clients", data["client_id"], tenant_id):
        conn.close()
        return jsonify({"error": "client_id must belong to this workspace"}), 400
    project_id = get_or_create_inbox_project(conn, tenant_id)

    task_cur = conn.execute(
        "INSERT INTO tasks (tenant_id, project_id, title, description, priority, status) VALUES (?,?,?,?,?, 'todo')",
        (tenant_id, project_id, f"[Request] {data['title']}", data.get("description"), data.get("priority", "medium")),
    )
    task_id = task_cur.lastrowid

    req_cur = conn.execute(
        """INSERT INTO requests (tenant_id, requester_name, requester_contact, client_id, request_type, title,
           description, priority, status, created_task_id)
           VALUES (?,?,?,?,?,?,?,?, 'triaged', ?)""",
        (tenant_id, data["requester_name"], data.get("requester_contact"), data.get("client_id"),
         data.get("request_type", "general"), data["title"], data.get("description"),
         data.get("priority", "medium"), task_id),
    )
    conn.commit()
    request_id = req_cur.lastrowid

    conn.execute(
        "INSERT INTO notifications (tenant_id, user_id, type, message, link) VALUES (?,?,?,?,?)",
        (tenant_id, g.current_user["user_id"], "new_request", f"New request → Task created: {data['title']}", f"/tasks/{task_id}"),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM requests WHERE id=? AND tenant_id=?", (request_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "request", request_id, details=f"auto task #{task_id}")
    req_dict = row_to_dict(row)
    fire_event("request.created", tenant_id, {"request": req_dict})
    return jsonify(req_dict), 201


@requests_bp.route("/requests/<int:request_id>", methods=["PATCH"])
@login_required
def update_request(request_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    if "status" in data and data["status"] not in REQUEST_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of {REQUEST_STATUSES}"}), 400
    fields, values = [], []
    for key in ("status", "priority"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    values += [request_id, tenant_id]

    conn = get_db()
    conn.execute(f"UPDATE requests SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)

    # Keep the linked task's status roughly in sync
    req = conn.execute("SELECT * FROM requests WHERE id=? AND tenant_id=?", (request_id, tenant_id)).fetchone()
    if req and req["created_task_id"] and "status" in data:
        task_status_map = {"resolved": "done", "in_progress": "in_progress", "rejected": "done"}
        mapped = task_status_map.get(data["status"])
        if mapped:
            conn.execute("UPDATE tasks SET status=? WHERE id=? AND tenant_id=?", (mapped, req["created_task_id"], tenant_id))
    conn.commit()
    row = conn.execute("SELECT * FROM requests WHERE id=? AND tenant_id=?", (request_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "request", request_id)
    return jsonify(row_to_dict(row))
