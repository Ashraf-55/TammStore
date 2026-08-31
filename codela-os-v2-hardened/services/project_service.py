from database import get_db, tenant_resource_exists

def record_project_activity(conn, tenant_id, project_id, actor_user_id, event_type, entity_type=None, entity_id=None, payload=None):
    import json
    conn.execute("""INSERT INTO project_activities
        (tenant_id, project_id, actor_user_id, event_type, entity_type, entity_id, payload)
        VALUES (?,?,?,?,?,?,?)""", (tenant_id, project_id, actor_user_id, event_type, entity_type, entity_id,
                                       json.dumps(payload or {}, default=str)))

def ensure_project_employee(conn, tenant_id, project_id, employee_id, role="member"):
    employee = conn.execute("SELECT id FROM employees WHERE id=? AND tenant_id=?", (employee_id, tenant_id)).fetchone()
    if not employee:
        raise ValueError("employee_id must belong to this workspace")
    project = conn.execute("SELECT id FROM projects WHERE id=? AND tenant_id=?", (project_id, tenant_id)).fetchone()
    if not project:
        raise ValueError("project_id must belong to this workspace")
    conn.execute("INSERT INTO project_members (tenant_id,project_id,employee_id,role) VALUES (?,?,?,?) ON CONFLICT(tenant_id,project_id,employee_id) DO NOTHING",
                 (tenant_id, project_id, employee_id, role))
