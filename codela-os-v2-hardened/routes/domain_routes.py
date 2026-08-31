import logging
from flask import Blueprint, request, jsonify, g
from auth import login_required, log_action

logger = logging.getLogger("codela")
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists, pagination_params
from policies.permissions import require_permission, has_permission
from services.project_service import record_project_activity, ensure_project_employee
from automation import fire_event


domain_bp = Blueprint("domain", __name__)

# ---------------- ORGANIZATION / EMPLOYEES ----------------

@domain_bp.route("/departments", methods=["GET"])
@login_required
def list_departments():
    conn=get_db(); rows=conn.execute("SELECT * FROM departments WHERE tenant_id=? ORDER BY name",(g.current_user["tenant_id"],)).fetchall(); conn.close()
    return jsonify(rows_to_list(rows))

@domain_bp.route("/departments", methods=["POST"])
@login_required
@require_permission("employees.manage")
def create_department():
    data=request.get_json(force=True) or {}; name=(data.get("name") or "").strip()
    if not name: return jsonify({"error":"name is required"}),400
    conn=get_db()
    try:
        cur=conn.execute("INSERT INTO departments (tenant_id,name,code) VALUES (?,?,?)",(g.current_user["tenant_id"],name,data.get("code")))
        conn.commit(); row=conn.execute("SELECT * FROM departments WHERE id=?",(cur.lastrowid,)).fetchone()
    except Exception as exc:
        conn.rollback(); conn.close(); logger.exception("department create failed request_id=%s", g.get("request_id")); return jsonify({"error":"department could not be created","request_id":g.get("request_id")}),400
    conn.close(); return jsonify(row_to_dict(row)),201

@domain_bp.route("/positions", methods=["GET"])
@login_required
def list_positions():
    conn=get_db(); rows=conn.execute("SELECT * FROM positions WHERE tenant_id=? ORDER BY title",(g.current_user["tenant_id"],)).fetchall(); conn.close()
    return jsonify(rows_to_list(rows))

@domain_bp.route("/positions", methods=["POST"])
@login_required
@require_permission("employees.manage")
def create_position():
    data=request.get_json(force=True) or {}; title=(data.get("title") or "").strip()
    if not title: return jsonify({"error":"title is required"}),400
    conn=get_db()
    try:
        cur=conn.execute("INSERT INTO positions (tenant_id,title,code,description) VALUES (?,?,?,?)",(g.current_user["tenant_id"],title,data.get("code"),data.get("description")))
        conn.commit(); row=conn.execute("SELECT * FROM positions WHERE id=?",(cur.lastrowid,)).fetchone()
    except Exception as exc:
        conn.rollback(); conn.close(); logger.exception("position create failed request_id=%s", g.get("request_id")); return jsonify({"error":"position could not be created","request_id":g.get("request_id")}),400
    conn.close(); return jsonify(row_to_dict(row)),201

@domain_bp.route("/workspace/users", methods=["GET"])
@login_required
def workspace_users():
    conn=get_db(); rows=conn.execute("SELECT id,name,email,role,department,is_active FROM users WHERE tenant_id=? AND is_active=1 ORDER BY name",(g.current_user["tenant_id"],)).fetchall(); conn.close()
    return jsonify(rows_to_list(rows))

@domain_bp.route("/employees", methods=["GET"])
@login_required
def list_employees():
    conn=get_db(); limit,offset=pagination_params(request); rows=conn.execute("""SELECT e.*,u.name,u.email,u.role,d.name AS department_name,p.title AS position_title
        FROM employees e JOIN users u ON u.id=e.user_id AND u.tenant_id=e.tenant_id
        LEFT JOIN departments d ON d.id=e.department_id AND d.tenant_id=e.tenant_id
        LEFT JOIN positions p ON p.id=e.position_id AND p.tenant_id=e.tenant_id
        WHERE e.tenant_id=? ORDER BY u.name LIMIT ? OFFSET ?""",(g.current_user["tenant_id"],limit,offset)).fetchall(); conn.close()
    return jsonify(rows_to_list(rows))

@domain_bp.route("/employees", methods=["POST"])
@login_required
@require_permission("employees.manage")
def create_employee():
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]
    if not data.get("user_id"): return jsonify({"error":"user_id is required"}),400
    conn=get_db()
    user=conn.execute("SELECT id FROM users WHERE id=? AND tenant_id=?",(data["user_id"],tenant_id)).fetchone()
    if not user: conn.close(); return jsonify({"error":"user_id must belong to this workspace"}),400
    for field,table in (("department_id","departments"),("position_id","positions")):
        if data.get(field) and not tenant_resource_exists(conn,table,data[field],tenant_id):
            conn.close(); return jsonify({"error":f"{field} must belong to this workspace"}),400
    if data.get("manager_id") and not tenant_resource_exists(conn,"employees",data["manager_id"],tenant_id):
        conn.close(); return jsonify({"error":"manager_id must belong to this workspace"}),400
    try:
        cur=conn.execute("""INSERT INTO employees (tenant_id,user_id,employee_code,department_id,position_id,manager_id,hire_date,employment_type,employment_status,hourly_cost,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",(tenant_id,data["user_id"],data.get("employee_code"),data.get("department_id"),data.get("position_id"),data.get("manager_id"),data.get("hire_date"),data.get("employment_type","full_time"),data.get("employment_status","active"),data.get("hourly_cost",0),data.get("notes")))
        conn.commit(); row=conn.execute("SELECT * FROM employees WHERE id=?",(cur.lastrowid,)).fetchone()
    except Exception as exc:
        conn.rollback(); conn.close(); logger.exception("employee create failed request_id=%s", g.get("request_id")); return jsonify({"error":"employee could not be created","request_id":g.get("request_id")}),400
    conn.close(); log_action(g.current_user["user_id"],"create","employee",row["id"]); return jsonify(row_to_dict(row)),201

# ---------------- CLIENT DOMAIN ----------------

@domain_bp.route("/clients/<int:client_id>/contacts", methods=["GET"])
@login_required
def list_client_contacts(client_id):
    tenant_id=g.current_user["tenant_id"]; conn=get_db()
    if not tenant_resource_exists(conn,"clients",client_id,tenant_id): conn.close(); return jsonify({"error":"Client not found"}),404
    rows=conn.execute("SELECT * FROM client_contacts WHERE tenant_id=? AND client_id=? ORDER BY is_primary DESC,name",(tenant_id,client_id)).fetchall(); conn.close(); return jsonify(rows_to_list(rows))

@domain_bp.route("/clients/<int:client_id>/contacts", methods=["POST"])
@login_required
@require_permission("clients.update")
def create_client_contact(client_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]
    if not data.get("name"): return jsonify({"error":"name is required"}),400
    conn=get_db()
    if not tenant_resource_exists(conn,"clients",client_id,tenant_id): conn.close(); return jsonify({"error":"Client not found"}),404
    cur=conn.execute("INSERT INTO client_contacts (tenant_id,client_id,name,email,phone,job_title,is_primary,notes) VALUES (?,?,?,?,?,?,?,?)",
                     (tenant_id,client_id,data["name"],data.get("email"),data.get("phone"),data.get("job_title"),int(bool(data.get("is_primary"))),data.get("notes")))
    conn.commit(); row=conn.execute("SELECT * FROM client_contacts WHERE id=?",(cur.lastrowid,)).fetchone(); conn.close(); return jsonify(row_to_dict(row)),201

@domain_bp.route("/clients/<int:client_id>/users", methods=["POST"])
@login_required
@require_permission("clients.update")
def attach_client_user(client_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]
    if not data.get("user_id"): return jsonify({"error":"user_id is required"}),400
    conn=get_db()
    if not tenant_resource_exists(conn,"clients",client_id,tenant_id) or not tenant_resource_exists(conn,"users",data["user_id"],tenant_id):
        conn.close(); return jsonify({"error":"client_id and user_id must belong to this workspace"}),400
    try:
        conn.execute("INSERT INTO client_users (tenant_id,client_id,user_id,role) VALUES (?,?,?,?)",(tenant_id,client_id,data["user_id"],data.get("role","client_user"))); conn.commit()
    except Exception as exc:
        conn.rollback(); conn.close(); logger.exception("client user link failed request_id=%s", g.get("request_id")); return jsonify({"error":"user is already linked to a client or invalid","request_id":g.get("request_id")}),400
    row=conn.execute("SELECT * FROM client_users WHERE tenant_id=? AND client_id=? AND user_id=?",(tenant_id,client_id,data["user_id"])).fetchone(); conn.close(); return jsonify(row_to_dict(row)),201

# ---------------- PROJECT DELIVERY ----------------

@domain_bp.route("/projects/<int:project_id>/workspace", methods=["GET"])
@login_required
def project_workspace(project_id):
    tenant_id=g.current_user["tenant_id"]; conn=get_db()
    project=conn.execute("SELECT p.*,c.name AS client_name,c.company AS client_company FROM projects p LEFT JOIN clients c ON c.id=p.client_id AND c.tenant_id=p.tenant_id WHERE p.id=? AND p.tenant_id=?",(project_id,tenant_id)).fetchone()
    if not project: conn.close(); return jsonify({"error":"Project not found"}),404
    result=row_to_dict(project)
    result["members"]=rows_to_list(conn.execute("""SELECT pm.*,e.employee_code,u.id AS user_id,u.name,u.email FROM project_members pm JOIN employees e ON e.id=pm.employee_id AND e.tenant_id=pm.tenant_id JOIN users u ON u.id=e.user_id AND u.tenant_id=e.tenant_id WHERE pm.tenant_id=? AND pm.project_id=? ORDER BY u.name""",(tenant_id,project_id)).fetchall())
    result["milestones"]=rows_to_list(conn.execute("SELECT * FROM project_milestones WHERE tenant_id=? AND project_id=? ORDER BY sort_order,due_date",(tenant_id,project_id)).fetchall())
    result["deliverables"]=rows_to_list(conn.execute("SELECT * FROM project_deliverables WHERE tenant_id=? AND project_id=? ORDER BY created_at DESC",(tenant_id,project_id)).fetchall())
    result["tasks"]=rows_to_list(conn.execute("SELECT * FROM tasks WHERE tenant_id=? AND project_id=? ORDER BY order_index,deadline",(tenant_id,project_id)).fetchall())
    result["requests"]=rows_to_list(conn.execute("SELECT * FROM requests WHERE tenant_id=? AND project_id=? ORDER BY created_at DESC",(tenant_id,project_id)).fetchall())
    result["approvals"]=rows_to_list(conn.execute("SELECT * FROM project_approvals WHERE tenant_id=? AND project_id=? ORDER BY requested_at DESC",(tenant_id,project_id)).fetchall())
    revenue=conn.execute("SELECT COALESCE(SUM(total),0) AS v FROM invoices WHERE tenant_id=? AND project_id=? AND status IN ('sent','paid','overdue')",(tenant_id,project_id)).fetchone()["v"]
    expenses=conn.execute("SELECT COALESCE(SUM(amount),0) AS v FROM expenses WHERE tenant_id=? AND project_id=?",(tenant_id,project_id)).fetchone()["v"]
    costs=conn.execute("SELECT COALESCE(SUM(amount),0) AS v FROM project_costs WHERE tenant_id=? AND project_id=?",(tenant_id,project_id)).fetchone()["v"]
    labor=conn.execute("SELECT COALESCE(SUM(tte.hours*tte.hourly_cost),0) AS v FROM task_time_entries tte JOIN tasks t ON t.id=tte.task_id AND t.tenant_id=tte.tenant_id WHERE tte.tenant_id=? AND t.project_id=?",(tenant_id,project_id)).fetchone()["v"]
    total_cost=float(expenses or 0)+float(costs or 0)+float(labor or 0); profit=float(revenue or 0)-total_cost
    budget=conn.execute("SELECT budget_amount,currency FROM project_budgets WHERE tenant_id=? AND project_id=?",(tenant_id,project_id)).fetchone()
    result["financials"]={"revenue":float(revenue or 0),"expenses":float(expenses or 0),"other_costs":float(costs or 0),"labor_cost":float(labor or 0),"total_cost":total_cost,"profit":profit,"margin":(profit/float(revenue)*100) if revenue else 0,"budget":row_to_dict(budget) if budget else None}
    conn.close(); return jsonify(result)

@domain_bp.route("/projects/<int:project_id>/members", methods=["GET"])
@login_required
def list_project_members(project_id):
    tenant_id=g.current_user["tenant_id"]; conn=get_db()
    if not tenant_resource_exists(conn,"projects",project_id,tenant_id): conn.close(); return jsonify({"error":"Project not found"}),404
    rows=conn.execute("""SELECT pm.*,e.employee_code,u.name,u.email,e.department_id FROM project_members pm
        JOIN employees e ON e.id=pm.employee_id AND e.tenant_id=pm.tenant_id JOIN users u ON u.id=e.user_id AND u.tenant_id=e.tenant_id
        WHERE pm.tenant_id=? AND pm.project_id=? ORDER BY u.name""",(tenant_id,project_id)).fetchall(); conn.close(); return jsonify(rows_to_list(rows))

@domain_bp.route("/projects/<int:project_id>/members", methods=["POST"])
@login_required
@require_permission("projects.assign")
def add_project_member(project_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]
    if not data.get("employee_id"): return jsonify({"error":"employee_id is required"}),400
    conn=get_db()
    try:
        ensure_project_employee(conn,tenant_id,project_id,data["employee_id"],data.get("role","member"))
        record_project_activity(conn,tenant_id,project_id,g.current_user["user_id"],"project.member_added","employee",data["employee_id"],{"role":data.get("role","member")})
        conn.commit()
    except ValueError as exc: conn.rollback(); conn.close(); return jsonify({"error":str(exc)}),400
    row=conn.execute("SELECT * FROM project_members WHERE tenant_id=? AND project_id=? AND employee_id=?",(tenant_id,project_id,data["employee_id"])).fetchone(); conn.close()
    fire_event("project.member_added",tenant_id,{"project_id":project_id,"employee_id":data["employee_id"]})
    return jsonify(row_to_dict(row)),201

@domain_bp.route("/projects/<int:project_id>/milestones", methods=["GET"])
@login_required
def list_milestones(project_id):
    conn=get_db(); rows=conn.execute("SELECT * FROM project_milestones WHERE tenant_id=? AND project_id=? ORDER BY sort_order,due_date",(g.current_user["tenant_id"],project_id)).fetchall(); conn.close(); return jsonify(rows_to_list(rows))

@domain_bp.route("/projects/<int:project_id>/milestones", methods=["POST"])
@login_required
@require_permission("projects.update")
def create_milestone(project_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]
    if not data.get("name"): return jsonify({"error":"name is required"}),400
    conn=get_db()
    if not tenant_resource_exists(conn,"projects",project_id,tenant_id): conn.close(); return jsonify({"error":"Project not found"}),404
    cur=conn.execute("INSERT INTO project_milestones (tenant_id,project_id,name,description,start_date,due_date,status,sort_order) VALUES (?,?,?,?,?,?,?,?)",(tenant_id,project_id,data["name"],data.get("description"),data.get("start_date"),data.get("due_date"),data.get("status","pending"),data.get("sort_order",0)))
    record_project_activity(conn,tenant_id,project_id,g.current_user["user_id"],"milestone.created","milestone",cur.lastrowid); conn.commit(); row=conn.execute("SELECT * FROM project_milestones WHERE id=?",(cur.lastrowid,)).fetchone(); conn.close(); return jsonify(row_to_dict(row)),201

@domain_bp.route("/projects/<int:project_id>/deliverables", methods=["GET"])
@login_required
def list_deliverables(project_id):
    conn=get_db(); rows=conn.execute("SELECT * FROM project_deliverables WHERE tenant_id=? AND project_id=? ORDER BY created_at DESC",(g.current_user["tenant_id"],project_id)).fetchall(); conn.close(); return jsonify(rows_to_list(rows))

@domain_bp.route("/projects/<int:project_id>/deliverables", methods=["POST"])
@login_required
@require_permission("projects.update")
def create_deliverable(project_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]
    if not data.get("name"): return jsonify({"error":"name is required"}),400
    conn=get_db()
    if not tenant_resource_exists(conn,"projects",project_id,tenant_id): conn.close(); return jsonify({"error":"Project not found"}),404
    if data.get("milestone_id"):
        if not tenant_resource_exists(conn,"project_milestones",data["milestone_id"],tenant_id): conn.close(); return jsonify({"error":"milestone_id must belong to this workspace"}),400
        ms=conn.execute("SELECT project_id FROM project_milestones WHERE id=? AND tenant_id=?",(data["milestone_id"],tenant_id)).fetchone()
        if not ms or ms["project_id"]!=project_id: conn.close(); return jsonify({"error":"milestone_id must belong to the same project"}),400
    cur=conn.execute("INSERT INTO project_deliverables (tenant_id,project_id,milestone_id,name,description,status,version,submitted_by,due_date) VALUES (?,?,?,?,?,?,?,?,?)",(tenant_id,project_id,data.get("milestone_id"),data["name"],data.get("description"),data.get("status","draft"),data.get("version",1),g.current_user["user_id"],data.get("due_date")))
    record_project_activity(conn,tenant_id,project_id,g.current_user["user_id"],"deliverable.created","deliverable",cur.lastrowid); conn.commit(); row=conn.execute("SELECT * FROM project_deliverables WHERE id=?",(cur.lastrowid,)).fetchone(); conn.close(); return jsonify(row_to_dict(row)),201

@domain_bp.route("/deliverables/<int:deliverable_id>/approval", methods=["GET"])
@login_required
def get_deliverable_approval(deliverable_id):
    tenant_id=g.current_user["tenant_id"]; conn=get_db()
    d=conn.execute("SELECT id,project_id FROM project_deliverables WHERE id=? AND tenant_id=?",(deliverable_id,tenant_id)).fetchone()
    if not d: conn.close(); return jsonify({"error":"Deliverable not found"}),404
    row=conn.execute("SELECT * FROM project_approvals WHERE tenant_id=? AND deliverable_id=? ORDER BY requested_at DESC LIMIT 1",(tenant_id,deliverable_id)).fetchone(); conn.close()
    if not row: return jsonify({"error":"No approval exists for this deliverable"}),404
    return jsonify(row_to_dict(row))

@domain_bp.route("/deliverables/<int:deliverable_id>/approval", methods=["POST"])
@login_required
def request_deliverable_approval(deliverable_id):
    if not has_permission(g.current_user, "deliverables.approve"):
        return jsonify({"error":"Permission denied","code":"permission_denied","permission":"deliverables.approve"}),403
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]; conn=get_db()
    d=conn.execute("SELECT * FROM project_deliverables WHERE id=? AND tenant_id=?",(deliverable_id,tenant_id)).fetchone()
    if not d: conn.close(); return jsonify({"error":"Deliverable not found"}),404
    approver_id=data.get("approver_id")
    if approver_id and not tenant_resource_exists(conn,"users",approver_id,tenant_id): conn.close(); return jsonify({"error":"approver_id must belong to this workspace"}),400
    cur=conn.execute("INSERT INTO project_approvals (tenant_id,project_id,deliverable_id,requested_by,approver_id,status) VALUES (?,?,?,?,?, 'pending')",(tenant_id,d["project_id"],deliverable_id,g.current_user["user_id"],approver_id))
    conn.execute("UPDATE project_deliverables SET status='submitted',submitted_at=datetime('now'),updated_at=datetime('now') WHERE id=? AND tenant_id=?",(deliverable_id,tenant_id))
    record_project_activity(conn,tenant_id,d["project_id"],g.current_user["user_id"],"approval.requested","deliverable",deliverable_id); conn.commit(); row=conn.execute("SELECT * FROM project_approvals WHERE id=?",(cur.lastrowid,)).fetchone(); conn.close()
    if approver_id: fire_event("approval.requested",tenant_id,{"approval":row_to_dict(row)})
    return jsonify(row_to_dict(row)),201

@domain_bp.route("/approvals/<int:approval_id>", methods=["PATCH"])
@login_required
def decide_approval(approval_id):
    data=request.get_json(force=True) or {}; status=data.get("status")
    if status not in ("approved","rejected","changes_requested"): return jsonify({"error":"status must be approved, rejected, or changes_requested"}),400
    tenant_id=g.current_user["tenant_id"]; conn=get_db(); approval=conn.execute("SELECT * FROM project_approvals WHERE id=? AND tenant_id=?",(approval_id,tenant_id)).fetchone()
    if not approval: conn.close(); return jsonify({"error":"Approval not found"}),404
    is_assigned_approver = approval["approver_id"] == g.current_user["user_id"]
    if not is_assigned_approver and not has_permission(g.current_user, "deliverables.approve"):
        conn.close()
        return jsonify({"error":"Permission denied","code":"permission_denied","permission":"deliverables.approve"}),403
    conn.execute("UPDATE project_approvals SET status=?,feedback=?,decided_at=datetime('now') WHERE id=? AND tenant_id=?",(status,data.get("feedback"),approval_id,tenant_id))
    dstatus="approved" if status=="approved" else "changes_requested" if status=="changes_requested" else "rejected"
    conn.execute("UPDATE project_deliverables SET status=?,updated_at=datetime('now') WHERE id=? AND tenant_id=?",(dstatus,approval["deliverable_id"],tenant_id))
    record_project_activity(conn,tenant_id,approval["project_id"],g.current_user["user_id"],"approval.completed","approval",approval_id,{"status":status})
    conn.commit(); row=conn.execute("SELECT * FROM project_approvals WHERE id=?",(approval_id,)).fetchone(); conn.close(); fire_event("approval.completed",tenant_id,{"approval":row_to_dict(row)}); return jsonify(row_to_dict(row))

# ---------------- PROJECT FINANCIAL SUMMARY ----------------

@domain_bp.route("/projects/<int:project_id>/budget", methods=["PUT"])
@login_required
@require_permission("projects.update")
def set_project_budget(project_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]
    try: amount=float(data.get("budget_amount",0) or 0)
    except (TypeError,ValueError): return jsonify({"error":"budget_amount must be numeric"}),400
    if amount < 0: return jsonify({"error":"budget_amount cannot be negative"}),400
    conn=get_db()
    if not tenant_resource_exists(conn,"projects",project_id,tenant_id): conn.close(); return jsonify({"error":"Project not found"}),404
    conn.execute("INSERT INTO project_budgets (tenant_id,project_id,budget_amount,currency) VALUES (?,?,?,?) ON CONFLICT(tenant_id,project_id) DO UPDATE SET budget_amount=excluded.budget_amount,currency=excluded.currency",(tenant_id,project_id,amount,data.get("currency","USD")))
    conn.commit(); row=conn.execute("SELECT * FROM project_budgets WHERE tenant_id=? AND project_id=?",(tenant_id,project_id)).fetchone(); conn.close(); return jsonify(row_to_dict(row))

@domain_bp.route("/projects/<int:project_id>/expenses", methods=["POST"])
@login_required
@require_permission("finance.view")
def add_project_expense(project_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]
    try: amount=float(data.get("amount",0) or 0)
    except (TypeError,ValueError): return jsonify({"error":"amount must be numeric"}),400
    if amount <= 0 or not data.get("category"): return jsonify({"error":"positive amount and category are required"}),400
    conn=get_db()
    if not tenant_resource_exists(conn,"projects",project_id,tenant_id): conn.close(); return jsonify({"error":"Project not found"}),404
    employee_id=data.get("employee_id")
    if employee_id and not tenant_resource_exists(conn,"employees",employee_id,tenant_id): conn.close(); return jsonify({"error":"employee_id must belong to this workspace"}),400
    cur=conn.execute("INSERT INTO expenses (tenant_id,project_id,employee_id,amount,category,description,expense_date) VALUES (?,?,?,?,?,?,COALESCE(?,date('now')))",(tenant_id,project_id,employee_id,amount,data["category"],data.get("description"),data.get("expense_date")))
    conn.execute("INSERT INTO project_costs (tenant_id,project_id,source_type,source_id,amount,description) VALUES (?,?,?,?,?,?)",(tenant_id,project_id,"expense",cur.lastrowid,amount,data.get("description") or data["category"]))
    conn.commit(); row=conn.execute("SELECT * FROM expenses WHERE id=?",(cur.lastrowid,)).fetchone(); conn.close(); fire_event("project.expense.created",tenant_id,{"expense":row_to_dict(row)}); return jsonify(row_to_dict(row)),201

@domain_bp.route("/projects/<int:project_id>/financials", methods=["GET"])
@login_required
def project_financials(project_id):
    tenant_id=g.current_user["tenant_id"]; conn=get_db()
    if not tenant_resource_exists(conn,"projects",project_id,tenant_id): conn.close(); return jsonify({"error":"Project not found"}),404
    revenue=conn.execute("SELECT COALESCE(SUM(total),0) AS v FROM invoices WHERE tenant_id=? AND project_id=? AND status IN ('sent','paid','overdue')",(tenant_id,project_id)).fetchone()["v"]
    expenses=conn.execute("SELECT COALESCE(SUM(amount),0) AS v FROM expenses WHERE tenant_id=? AND project_id=?",(tenant_id,project_id)).fetchone()["v"]
    costs=conn.execute("SELECT COALESCE(SUM(amount),0) AS v FROM project_costs WHERE tenant_id=? AND project_id=?",(tenant_id,project_id)).fetchone()["v"]
    labor=conn.execute("SELECT COALESCE(SUM(tte.hours*tte.hourly_cost),0) AS v FROM task_time_entries tte JOIN tasks t ON t.id=tte.task_id AND t.tenant_id=tte.tenant_id WHERE tte.tenant_id=? AND t.project_id=?",(tenant_id,project_id)).fetchone()["v"]
    total_cost=float(expenses or 0)+float(costs or 0)+float(labor or 0); profit=float(revenue or 0)-total_cost; margin=(profit/float(revenue)*100) if revenue else 0
    budget=conn.execute("SELECT budget_amount,currency FROM project_budgets WHERE tenant_id=? AND project_id=?",(tenant_id,project_id)).fetchone(); conn.close()
    return jsonify({"revenue":float(revenue or 0),"expenses":float(expenses or 0),"other_costs":float(costs or 0),"labor_cost":float(labor or 0),"total_cost":total_cost,"profit":profit,"margin":margin,"budget":row_to_dict(budget) if budget else None})

# ---------------- REQUEST WORKFLOW EXTENSION ----------------

@domain_bp.route("/requests/<int:request_id>/assign", methods=["POST"])
@login_required
@require_permission("requests.assign")
def assign_request(request_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]; conn=get_db()
    req=conn.execute("SELECT * FROM requests WHERE id=? AND tenant_id=?",(request_id,tenant_id)).fetchone()
    if not req: conn.close(); return jsonify({"error":"Request not found"}),404
    project_id=data.get("project_id", req["project_id"])
    assigned_to=data.get("assigned_to", req["assigned_to"])
    if project_id and not tenant_resource_exists(conn,"projects",project_id,tenant_id): conn.close(); return jsonify({"error":"project_id must belong to this workspace"}),400
    if project_id and req["client_id"]:
        p=conn.execute("SELECT id FROM projects WHERE id=? AND tenant_id=? AND client_id=?",(project_id,tenant_id,req["client_id"])).fetchone()
        if not p: conn.close(); return jsonify({"error":"project_id is not owned by the request client"}),403
    if assigned_to and not tenant_resource_exists(conn,"users",assigned_to,tenant_id): conn.close(); return jsonify({"error":"assigned_to must belong to this workspace"}),400
    task_id=req["created_task_id"]
    if project_id and task_id:
        conn.execute("UPDATE tasks SET project_id=? WHERE id=? AND tenant_id=?",(project_id,task_id,tenant_id))
    elif project_id and not task_id:
        cur=conn.execute("INSERT INTO tasks (tenant_id,project_id,title,description,assignee_id,priority,status,created_by) VALUES (?,?,?,?,?,?,?,?)",(tenant_id,project_id,f"[Request] {req['title']}",req["description"],assigned_to,req["priority"],"todo",g.current_user["user_id"]))
        task_id=cur.lastrowid
    if assigned_to and project_id:
        emp=conn.execute("SELECT id FROM employees WHERE tenant_id=? AND user_id=?",(tenant_id,assigned_to)).fetchone()
        if emp:
            conn.execute("INSERT INTO project_members (tenant_id,project_id,employee_id,role) VALUES (?,?,?,?) ON CONFLICT(tenant_id,project_id,employee_id) DO NOTHING",(tenant_id,project_id,emp["id"],"request_assignee"))
    if assigned_to and task_id:
        conn.execute("UPDATE tasks SET assignee_id=? WHERE id=? AND tenant_id=?",(assigned_to,task_id,tenant_id))
    conn.execute("UPDATE requests SET assigned_to=?,assigned_team=?,project_id=?,created_task_id=?,status='in_progress' WHERE id=? AND tenant_id=?",(assigned_to,data.get("assigned_team",req["assigned_team"]),project_id,task_id,request_id,tenant_id))
    if assigned_to:
        conn.execute("INSERT INTO notifications (tenant_id,user_id,type,message,link) VALUES (?,?,?,?,?)",(tenant_id,assigned_to,"request_assigned",f"Request assigned: {req['title']}",f"/requests/{request_id}"))
    conn.commit(); row=conn.execute("SELECT * FROM requests WHERE id=? AND tenant_id=?",(request_id,tenant_id)).fetchone(); conn.close(); fire_event("request.assigned",tenant_id,{"request":row_to_dict(row)}); return jsonify(row_to_dict(row))

@domain_bp.route("/requests/<int:request_id>/resolve", methods=["POST"])
@login_required
@require_permission("requests.resolve")
def resolve_request(request_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]; conn=get_db()
    req=conn.execute("SELECT * FROM requests WHERE id=? AND tenant_id=?",(request_id,tenant_id)).fetchone()
    if not req: conn.close(); return jsonify({"error":"Request not found"}),404
    conn.execute("UPDATE requests SET status='resolved',resolved_at=datetime('now'),resolution=? WHERE id=? AND tenant_id=?",(data.get("resolution"),request_id,tenant_id))
    if req["created_task_id"]: conn.execute("UPDATE tasks SET status='done',completed_at=datetime('now') WHERE id=? AND tenant_id=?",(req["created_task_id"],tenant_id))
    conn.commit(); row=conn.execute("SELECT * FROM requests WHERE id=? AND tenant_id=?",(request_id,tenant_id)).fetchone(); conn.close(); fire_event("request.resolved",tenant_id,{"request":row_to_dict(row)}); return jsonify(row_to_dict(row))

# ---------------- CLIENT PORTAL READ MODEL ----------------

def _client_for_user(conn, tenant_id, user_id):
    return conn.execute("SELECT c.* FROM clients c JOIN client_users cu ON cu.client_id=c.id AND cu.tenant_id=c.tenant_id WHERE cu.tenant_id=? AND cu.user_id=? AND cu.is_active=1",(tenant_id,user_id)).fetchone()

@domain_bp.route("/client/me", methods=["GET"])
@login_required
def client_me():
    conn=get_db(); client=_client_for_user(conn,g.current_user["tenant_id"],g.current_user["user_id"]); conn.close()
    if not client: return jsonify({"error":"Client portal access is not configured for this user"}),403
    return jsonify(row_to_dict(client))

@domain_bp.route("/client/projects", methods=["GET"])
@login_required
def client_projects():
    tenant_id=g.current_user["tenant_id"]; conn=get_db(); client=_client_for_user(conn,tenant_id,g.current_user["user_id"])
    if not client: conn.close(); return jsonify({"error":"Client portal access is not configured for this user"}),403
    rows=conn.execute("SELECT * FROM projects WHERE tenant_id=? AND client_id=? ORDER BY created_at DESC",(tenant_id,client["id"])).fetchall(); conn.close(); return jsonify(rows_to_list(rows))

@domain_bp.route("/client/requests", methods=["POST"])
@login_required
def client_create_request():
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]; conn=get_db(); client=_client_for_user(conn,tenant_id,g.current_user["user_id"])
    if not client: conn.close(); return jsonify({"error":"Client portal access is not configured for this user"}),403
    if not data.get("title"): conn.close(); return jsonify({"error":"title is required"}),400
    project_id=data.get("project_id")
    if project_id and not tenant_resource_exists(conn,"projects",project_id,tenant_id): conn.close(); return jsonify({"error":"project_id must belong to this workspace"}),400
    if project_id:
        p=conn.execute("SELECT id FROM projects WHERE id=? AND tenant_id=? AND client_id=?",(project_id,tenant_id,client["id"])).fetchone()
        if not p: conn.close(); return jsonify({"error":"project_id is not one of your projects"}),403
    cur=conn.execute("INSERT INTO requests (tenant_id,requester_name,requester_contact,client_id,request_type,title,description,priority,status,requester_user_id,requester_type,project_id) VALUES (?,?,?,?,?,?,?,?, 'new',?,?,?)",(tenant_id,g.current_user.get("name","Client"),g.current_user.get("email"),client["id"],data.get("request_type","general"),data["title"],data.get("description"),data.get("priority","medium"),g.current_user["user_id"],"client",project_id))
    request_id=cur.lastrowid
    task_id=None
    if project_id:
        task_cur=conn.execute("INSERT INTO tasks (tenant_id,project_id,title,description,priority,status,created_by,task_type) VALUES (?,?,?,?,?,?,?,?)",(tenant_id,project_id,f"[Client Request] {data['title']}",data.get("description"),data.get("priority","medium"),"todo",g.current_user["user_id"],"client_request"))
        task_id=task_cur.lastrowid
        conn.execute("UPDATE requests SET created_task_id=?,status='triaged' WHERE id=? AND tenant_id=?",(task_id,request_id,tenant_id))
    conn.commit(); row=conn.execute("SELECT * FROM requests WHERE id=?",(request_id,)).fetchone(); conn.close(); fire_event("request.created",tenant_id,{"request":row_to_dict(row)}); return jsonify(row_to_dict(row)),201

@domain_bp.route("/tasks/<int:task_id>/time", methods=["GET"])
@login_required
def list_task_time(task_id):
    tenant_id=g.current_user["tenant_id"]; conn=get_db()
    task=conn.execute("SELECT id FROM tasks WHERE id=? AND tenant_id=?",(task_id,tenant_id)).fetchone()
    if not task: conn.close(); return jsonify({"error":"Task not found"}),404
    rows=conn.execute("""SELECT tte.*,e.employee_code,u.name FROM task_time_entries tte
        JOIN employees e ON e.id=tte.employee_id AND e.tenant_id=tte.tenant_id
        JOIN users u ON u.id=e.user_id AND u.tenant_id=e.tenant_id
        WHERE tte.tenant_id=? AND tte.task_id=? ORDER BY tte.work_date DESC,tte.id DESC""",(tenant_id,task_id)).fetchall(); conn.close(); return jsonify(rows_to_list(rows))

@domain_bp.route("/tasks/<int:task_id>/time", methods=["POST"])
@login_required
@require_permission("tasks.update")
def add_task_time(task_id):
    data=request.get_json(force=True) or {}; tenant_id=g.current_user["tenant_id"]
    hours=float(data.get("hours",0) or 0)
    if hours <= 0: return jsonify({"error":"hours must be greater than 0"}),400
    conn=get_db(); task=conn.execute("SELECT id,project_id FROM tasks WHERE id=? AND tenant_id=?",(task_id,tenant_id)).fetchone()
    if not task: conn.close(); return jsonify({"error":"Task not found"}),404
    employee_id=data.get("employee_id")
    if employee_id:
        emp=conn.execute("SELECT id,hourly_cost FROM employees WHERE id=? AND tenant_id=?",(employee_id,tenant_id)).fetchone()
    else:
        emp=conn.execute("SELECT e.id,e.hourly_cost FROM employees e WHERE e.tenant_id=? AND e.user_id=?",(tenant_id,g.current_user["user_id"])).fetchone()
    if not emp: conn.close(); return jsonify({"error":"employee_id is required for a user without an Employee profile"}),400
    hourly_cost=float(data.get("hourly_cost",emp["hourly_cost"] or 0) or 0)
    cur=conn.execute("INSERT INTO task_time_entries (tenant_id,task_id,employee_id,work_date,hours,hourly_cost,notes) VALUES (?,?,?,?,?,?,?)",(tenant_id,task_id,emp["id"],data.get("work_date") or __import__("datetime").date.today().isoformat(),hours,hourly_cost,data.get("notes")))
    conn.execute("UPDATE tasks SET actual_hours=COALESCE(actual_hours,0)+? WHERE id=? AND tenant_id=?",(hours,task_id,tenant_id))
    conn.execute("INSERT INTO project_costs (tenant_id,project_id,source_type,source_id,amount,description) VALUES (?,?,?,?,?,?)",(tenant_id,task["project_id"],"task_time",cur.lastrowid,hours*hourly_cost,f"Task #{task_id} labor"))
    conn.commit(); row=conn.execute("SELECT * FROM task_time_entries WHERE id=?",(cur.lastrowid,)).fetchone(); conn.close(); return jsonify(row_to_dict(row)),201
