from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists, pagination_params
from auth import login_required, log_action
from policies.permissions import require_permission
from automation import fire_event

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/projects", methods=["GET"])
@login_required
def list_projects():
    tenant_id = g.current_user["tenant_id"]
    status = request.args.get("status")
    client_id = request.args.get("client_id")
    conn = get_db()
    query = "SELECT * FROM projects WHERE tenant_id = ?"
    params = [tenant_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    if client_id:
        query += " AND client_id = ?"
        params.append(client_id)
    query += " ORDER BY created_at DESC"
    limit, offset = pagination_params(request)
    query += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@projects_bp.route("/projects/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    project = conn.execute("SELECT * FROM projects WHERE id=? AND tenant_id=?", (project_id, tenant_id)).fetchone()
    if project is None:
        conn.close()
        return jsonify({"error": "Project not found"}), 404
    tasks = conn.execute("SELECT * FROM tasks WHERE project_id=? AND tenant_id=? ORDER BY order_index, deadline", (project_id, tenant_id)).fetchall()
    conn.close()
    result = row_to_dict(project)
    result["tasks"] = rows_to_list(tasks)
    return jsonify(result)


@projects_bp.route("/projects", methods=["POST"])
@login_required
@require_permission("projects.create")
def create_project():
    data = request.get_json(force=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    for fk,table in (("client_id","clients"),("project_manager_id","users")):
        if data.get(fk) and not tenant_resource_exists(conn,table,data[fk],tenant_id): conn.close(); return jsonify({"error":f"{fk} must belong to this workspace"}),400
    cur = conn.execute(
        "INSERT INTO projects (tenant_id, client_id, name, description, project_manager_id, status, start_date, end_date) VALUES (?,?,?,?,?,?,?,?)",
        (tenant_id, data.get("client_id"), data.get("name"), data.get("description"),
         data.get("project_manager_id"), data.get("status", "active"),
         data.get("start_date"), data.get("end_date")),
    )
    project_id = cur.lastrowid
    # New domain model: keep the legacy project_manager_id for compatibility,
    # but also materialize the manager as a project member when an Employee
    # profile exists for that user.
    if data.get("project_manager_id"):
        employee = conn.execute("SELECT id FROM employees WHERE tenant_id=? AND user_id=?", (tenant_id, data["project_manager_id"])).fetchone()
        if employee:
            conn.execute("INSERT INTO project_members (tenant_id,project_id,employee_id,role) VALUES (?,?,?,?) ON CONFLICT(tenant_id,project_id,employee_id) DO NOTHING", (tenant_id, project_id, employee["id"], "project_manager"))
    conn.execute("INSERT INTO project_activities (tenant_id,project_id,actor_user_id,event_type,entity_type,entity_id,payload) VALUES (?,?,?,?,?,?,?)", (tenant_id,project_id,g.current_user["user_id"],"project.created","project",project_id,"{}"))
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=? AND tenant_id=?", (project_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "project", project_id)
    fire_event("project.created", tenant_id, {"project": row_to_dict(row)})
    return jsonify(row_to_dict(row)), 201


@projects_bp.route("/projects/<int:project_id>", methods=["PATCH"])
@login_required
@require_permission("projects.update")
def update_project(project_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    fields, values = [], []
    for key in ("name", "description", "project_manager_id", "status", "start_date", "end_date"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    values += [project_id, tenant_id]
    conn = get_db()
    if data.get("project_manager_id") and not tenant_resource_exists(conn,"users",data["project_manager_id"],tenant_id):
        conn.close(); return jsonify({"error":"project_manager_id must belong to this workspace"}),400
    conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)
    if data.get("project_manager_id"):
        employee = conn.execute("SELECT id FROM employees WHERE tenant_id=? AND user_id=?", (tenant_id, data["project_manager_id"])).fetchone()
        if employee:
            conn.execute("INSERT INTO project_members (tenant_id,project_id,employee_id,role) VALUES (?,?,?,?) ON CONFLICT(tenant_id,project_id,employee_id) DO NOTHING", (tenant_id, project_id, employee["id"], "project_manager"))
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=? AND tenant_id=?", (project_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "project", project_id)
    return jsonify(row_to_dict(row))


# ---------------- TASKS ----------------

@projects_bp.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    tenant_id = g.current_user["tenant_id"]
    assignee_id = request.args.get("assignee_id")
    status = request.args.get("status")
    project_id = request.args.get("project_id")
    conn = get_db()
    query = "SELECT * FROM tasks WHERE tenant_id = ?"
    params = [tenant_id]
    if assignee_id:
        query += " AND assignee_id = ?"
        params.append(assignee_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    query += " ORDER BY order_index, deadline"
    limit, offset = pagination_params(request)
    query += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@projects_bp.route("/tasks", methods=["POST"])
@login_required
@require_permission("tasks.create")
def create_task():
    data = request.get_json(force=True) or {}
    if not data.get("title") or not data.get("project_id"):
        return jsonify({"error": "title and project_id are required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    if not tenant_resource_exists(conn, "projects", data["project_id"], tenant_id):
        conn.close()
        return jsonify({"error": "project_id must belong to this workspace"}), 400
    if data.get("assignee_id") and not tenant_resource_exists(conn, "users", data["assignee_id"], tenant_id):
        conn.close()
        return jsonify({"error": "assignee_id must belong to this workspace"}), 400
    if data.get("assignee_id"):
        member = conn.execute("SELECT 1 FROM project_members pm JOIN employees e ON e.id=pm.employee_id AND e.tenant_id=pm.tenant_id WHERE pm.tenant_id=? AND pm.project_id=? AND e.user_id=?",(tenant_id,data["project_id"],data["assignee_id"])).fetchone()
        if not member:
            conn.close(); return jsonify({"error":"assignee_id must be a member of this project"}),400
    milestone_id = data.get("milestone_id")
    if milestone_id:
        if not tenant_resource_exists(conn, "project_milestones", milestone_id, tenant_id):
            conn.close(); return jsonify({"error":"milestone_id must belong to this workspace"}),400
        ms = conn.execute("SELECT project_id FROM project_milestones WHERE id=? AND tenant_id=?", (milestone_id, tenant_id)).fetchone()
        if not ms or ms["project_id"] != data["project_id"]:
            conn.close(); return jsonify({"error":"milestone_id must belong to the same project"}),400
    cur = conn.execute(
        "INSERT INTO tasks (tenant_id, project_id, title, description, assignee_id, priority, status, deadline, milestone_id, created_by, task_type, estimated_hours) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (tenant_id, data.get("project_id"), data.get("title"), data.get("description"),
         data.get("assignee_id"), data.get("priority", "medium"),
         data.get("status", "todo"), data.get("deadline"), milestone_id, g.current_user["user_id"], data.get("task_type", "work"), data.get("estimated_hours", 0)),
    )
    conn.commit()
    task_id = cur.lastrowid
    if data.get("assignee_id"):
        conn.execute(
            "INSERT INTO notifications (tenant_id, user_id, type, message, link) VALUES (?,?,?,?,?)",
            (tenant_id, data["assignee_id"], "new_task", f"New task assigned: {data.get('title')}", f"/tasks/{task_id}"),
        )
        conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id=? AND tenant_id=?", (task_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "task", task_id)
    return jsonify(row_to_dict(row)), 201


@projects_bp.route("/tasks/<int:task_id>", methods=["PATCH"])
@login_required
@require_permission("tasks.update")
def update_task(task_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    fields, values = [], []
    for key in ("title", "description", "assignee_id", "priority", "status", "deadline", "order_index", "project_id"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    values += [task_id, tenant_id]
    conn = get_db()
    if data.get("assignee_id") and not tenant_resource_exists(conn,"users",data["assignee_id"],tenant_id):
        conn.close(); return jsonify({"error":"assignee_id must belong to this workspace"}),400
    current_task = conn.execute("SELECT project_id, assignee_id, milestone_id FROM tasks WHERE id=? AND tenant_id=?",(task_id,tenant_id)).fetchone()
    target_project = data.get("project_id", current_task["project_id"] if current_task else None)
    target_assignee = data.get("assignee_id", current_task["assignee_id"] if current_task else None)
    if data.get("project_id") and not tenant_resource_exists(conn,"projects",data["project_id"],tenant_id):
        conn.close(); return jsonify({"error":"project_id must belong to this workspace"}),400
    if target_assignee and target_project and (data.get("assignee_id") or data.get("project_id")):
        member = conn.execute("SELECT 1 FROM project_members pm JOIN employees e ON e.id=pm.employee_id AND e.tenant_id=pm.tenant_id WHERE pm.tenant_id=? AND pm.project_id=? AND e.user_id=?",(tenant_id,target_project,target_assignee)).fetchone()
        if not member:
            conn.close(); return jsonify({"error":"assignee_id must be a member of this project"}),400
    if data.get("project_id") and current_task and current_task["milestone_id"]:
        ms = conn.execute("SELECT project_id FROM project_milestones WHERE id=? AND tenant_id=?", (current_task["milestone_id"], tenant_id)).fetchone()
        if not ms or ms["project_id"] != data["project_id"]:
            conn.close(); return jsonify({"error":"task's existing milestone does not belong to the new project; clear milestone_id first"}),400
    conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id=? AND tenant_id=?", (task_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "task", task_id)
    if row and row["status"] == "done":
        fire_event("task.completed", tenant_id, {"task": row_to_dict(row)})
    elif row and row["assignee_id"]:
        fire_event("task.assigned", tenant_id, {"task": row_to_dict(row)})
    return jsonify(row_to_dict(row))


@projects_bp.route("/tasks/reorder", methods=["POST"])
@login_required
def reorder_tasks():
    """Bulk-update task status/order_index in one call — used by the Kanban
    drag-and-drop board so a single drag results in a single request."""
    data = request.get_json(force=True) or {}
    updates = data.get("updates", [])  # [{id, status, order_index}, ...]
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    for u in updates:
        conn.execute(
            "UPDATE tasks SET status=?, order_index=? WHERE id=? AND tenant_id=?",
            (u.get("status"), u.get("order_index", 0), u["id"], tenant_id),
        )
    conn.commit()
    conn.close()
    return jsonify({"message": "Reordered", "count": len(updates)})


@projects_bp.route("/tasks/<int:task_id>/comments", methods=["POST"])
@login_required
def add_task_comment(task_id):
    data = request.get_json(force=True) or {}
    if not data.get("comment"):
        return jsonify({"error": "comment is required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    if not tenant_resource_exists(conn,"tasks",task_id,tenant_id):
        conn.close(); return jsonify({"error":"Task not found"}),404
    cur = conn.execute(
        "INSERT INTO task_comments (tenant_id, task_id, user_id, comment) VALUES (?,?,?,?)",
        (tenant_id, task_id, g.current_user["user_id"], data["comment"]),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM task_comments WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@projects_bp.route("/tasks/<int:task_id>/comments", methods=["GET"])
@login_required
def get_task_comments(task_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM task_comments WHERE task_id=? AND tenant_id=? ORDER BY created_at", (task_id, g.current_user["tenant_id"])
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))
