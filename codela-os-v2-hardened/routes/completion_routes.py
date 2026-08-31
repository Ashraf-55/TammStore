from flask import Blueprint, request, jsonify, g
import json, os, hashlib, datetime
from auth import login_required, log_action
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists
from policies.permissions import require_permission, has_permission
from automation import fire_event

completion_bp=Blueprint('completion',__name__)

def t(): return g.current_user['tenant_id']
def uid(): return g.current_user['user_id']
def ok(x,code=200): return jsonify(x),code

def scalar(c,sql,p):
    r=c.execute(sql,p).fetchone(); return r[0] if r else 0

def employee_for_user(c,user_id): return c.execute('SELECT * FROM employees WHERE tenant_id=? AND user_id=?',(t(),user_id)).fetchone()

# ---------- Employee lifecycle ----------
@completion_bp.route('/employees/<int:eid>',methods=['GET','PATCH'])
@login_required
def employee_detail(eid):
    c=get_db(); row=c.execute('SELECT e.*,u.name,u.email,u.role,d.name department_name,p.title position_title FROM employees e JOIN users u ON u.id=e.user_id AND u.tenant_id=e.tenant_id LEFT JOIN departments d ON d.id=e.department_id AND d.tenant_id=e.tenant_id LEFT JOIN positions p ON p.id=e.position_id AND p.tenant_id=e.tenant_id WHERE e.id=? AND e.tenant_id=?',(eid,t())).fetchone()
    if not row: c.close(); return ok({'error':'Employee not found'},404)
    if request.method=='GET':
        contracts=c.execute('SELECT * FROM employee_contracts WHERE tenant_id=? AND employee_id=? ORDER BY created_at DESC',(t(),eid)).fetchall(); docs=c.execute('SELECT * FROM employee_documents WHERE tenant_id=? AND employee_id=? ORDER BY created_at DESC',(t(),eid)).fetchall(); hist=c.execute('SELECT * FROM employee_status_history WHERE tenant_id=? AND employee_id=? ORDER BY effective_at DESC',(t(),eid)).fetchall(); c.close(); d=row_to_dict(row); d.update({'contracts':rows_to_list(contracts),'documents':rows_to_list(docs),'status_history':rows_to_list(hist)}); return ok(d)
    if not has_permission(g.current_user,'employees.update'): c.close(); return ok({'error':'Permission denied','code':'permission_denied','permission':'employees.update'},403)
    data=request.get_json(force=True) or {}; allowed={'department_id','position_id','manager_id','hire_date','employment_type','employment_status','hourly_cost','notes'}
    sets=[]; vals=[]
    for k in allowed:
        if k in data:
            if k in ('department_id','position_id','manager_id') and data[k] is not None:
                table={'department_id':'departments','position_id':'positions','manager_id':'employees'}[k]
                if not tenant_resource_exists(c,table,data[k],t()): c.close(); return ok({'error':f'{k} must belong to this workspace'},400)
            sets.append(k+'=?'); vals.append(data[k])
    if not sets: c.close(); return ok({'error':'No fields to update'},400)
    if 'manager_id' in data:
        new_manager=data['manager_id']
        if new_manager==eid: c.close(); return ok({'error':'An employee cannot be their own manager'},400)
        if new_manager is not None:
            seen={eid}; cursor_id=new_manager
            for _ in range(1000):
                if cursor_id is None: break
                if cursor_id in seen: c.close(); return ok({'error':'manager_id would create a reporting cycle'},400)
                seen.add(cursor_id)
                nxt=c.execute('SELECT manager_id FROM employees WHERE id=? AND tenant_id=?',(cursor_id,t())).fetchone()
                cursor_id=nxt['manager_id'] if nxt else None
    old=row['employment_status']; vals += [eid,t()]; c.execute('UPDATE employees SET '+','.join(sets)+",updated_at=datetime('now') WHERE id=? AND tenant_id=?",vals)
    if 'employment_status' in data and data['employment_status']!=old: c.execute('INSERT INTO employee_status_history (tenant_id,employee_id,status,notes) VALUES (?,?,?,?)',(t(),eid,data['employment_status'],data.get('reason')))
    if 'manager_id' in data:
        c.execute("UPDATE employee_reporting_history SET effective_to=date('now') WHERE tenant_id=? AND employee_id=? AND effective_to IS NULL",(t(),eid)); c.execute('INSERT INTO employee_reporting_history (tenant_id,employee_id,manager_id,effective_from,reason) VALUES (?,?,?,date(\'now\'),?)',(t(),eid,data.get('manager_id'),data.get('reason')))
    c.commit(); row=c.execute('SELECT * FROM employees WHERE id=? AND tenant_id=?',(eid,t())).fetchone(); c.close(); log_action(uid(),'update','employee',eid); return ok(row_to_dict(row))

@completion_bp.route('/employees/<int:eid>/contracts',methods=['GET','POST'])
@login_required
@require_permission('employees.contracts')
def employee_contracts(eid):
    c=get_db();
    if not tenant_resource_exists(c,'employees',eid,t()): c.close(); return ok({'error':'Employee not found'},404)
    if request.method=='POST':
        d=request.get_json(force=True) or {}; start=d.get('start_date')
        if not start: c.close(); return ok({'error':'start_date is required'},400)
        cur=c.execute('INSERT INTO employee_contracts (tenant_id,employee_id,contract_type,start_date,end_date,salary,currency,status,notes,created_by) VALUES (?,?,?,?,?,?,?,?,?,?)',(t(),eid,d.get('contract_type','employment'),start,d.get('end_date'),d.get('salary',0),d.get('currency','EGP'),d.get('status','active'),d.get('notes'),uid())); c.commit(); row=c.execute('SELECT * FROM employee_contracts WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); return ok(row_to_dict(row),201)
    rows=c.execute('SELECT * FROM employee_contracts WHERE tenant_id=? AND employee_id=? ORDER BY created_at DESC',(t(),eid)).fetchall(); c.close(); return ok(rows_to_list(rows))

@completion_bp.route('/employees/<int:eid>/documents',methods=['GET','POST'])
@login_required
@require_permission('employees.documents')
def employee_documents(eid):
    c=get_db();
    if not tenant_resource_exists(c,'employees',eid,t()): c.close(); return ok({'error':'Employee not found'},404)
    if request.method=='POST':
        d=request.get_json(force=True) or {}; file_id=d.get('file_id')
        if file_id and not tenant_resource_exists(c,'files',file_id,t()): c.close(); return ok({'error':'file_id must belong to this workspace'},400)
        if not d.get('title') or not d.get('document_type'): c.close(); return ok({'error':'title and document_type are required'},400)
        cur=c.execute('INSERT INTO employee_documents (tenant_id,employee_id,file_id,document_type,title,expires_at,status,created_by) VALUES (?,?,?,?,?,?,?,?)',(t(),eid,file_id,d['document_type'],d['title'],d.get('expires_at'),d.get('status','active'),uid())); c.commit(); row=c.execute('SELECT * FROM employee_documents WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); return ok(row_to_dict(row),201)
    rows=c.execute('SELECT * FROM employee_documents WHERE tenant_id=? AND employee_id=? ORDER BY created_at DESC',(t(),eid)).fetchall(); c.close(); return ok(rows_to_list(rows))

# ---------- Task lifecycle ----------
@completion_bp.route('/tasks/<int:task_id>/assign',methods=['POST'])
@login_required
@require_permission('tasks.assign')
def assign_task(task_id):
    d=request.get_json(force=True) or {}; assignee=d.get('assignee_id') or d.get('user_id'); c=get_db(); task=c.execute('SELECT * FROM tasks WHERE id=? AND tenant_id=?',(task_id,t())).fetchone()
    if not task: c.close(); return ok({'error':'Task not found'},404)
    if not assignee or not tenant_resource_exists(c,'users',assignee,t()): c.close(); return ok({'error':'assignee_id must belong to this workspace'},400)
    member=c.execute('SELECT 1 FROM project_members pm JOIN employees e ON e.id=pm.employee_id AND e.tenant_id=pm.tenant_id WHERE pm.tenant_id=? AND pm.project_id=? AND e.user_id=?',(t(),task['project_id'],assignee)).fetchone()
    if not member: c.close(); return ok({'error':'Employee must be a member of the project before assignment'},409)
    c.execute('UPDATE tasks SET assignee_id=? WHERE id=? AND tenant_id=?',(assignee,task_id,t())); c.execute('INSERT INTO task_events (tenant_id,task_id,event_type,user_id,payload) VALUES (?,?,?,?,?)',(t(),task_id,'assigned',uid(),json.dumps({'assignee_id':assignee}))); c.commit(); row=c.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone(); c.close(); fire_event('task.assigned',t(),{'task':row_to_dict(row)}); return ok(row_to_dict(row))

@completion_bp.route('/tasks/<int:task_id>/status',methods=['POST'])
@login_required
@require_permission('tasks.manage')
def task_status(task_id):
    d=request.get_json(force=True) or {}; status=d.get('status'); allowed={'todo','in_progress','review','approved','done'}
    if status not in allowed: return ok({'error':'Invalid task status'},400)
    c=get_db(); task=c.execute('SELECT * FROM tasks WHERE id=? AND tenant_id=?',(task_id,t())).fetchone();
    if not task: c.close(); return ok({'error':'Task not found'},404)
    c.execute('UPDATE tasks SET status=? WHERE id=? AND tenant_id=?',(status,task_id,t())); c.execute('INSERT INTO task_events (tenant_id,task_id,from_status,to_status,event_type,user_id) VALUES (?,?,?,?,?,?)',(t(),task_id,task['status'],status,'status_changed',uid())); c.commit(); row=c.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone(); c.close(); fire_event('task.status_changed',t(),{'task':row_to_dict(row),'from':task['status'],'to':status}); return ok(row_to_dict(row))

@completion_bp.route('/tasks/<int:task_id>/events',methods=['GET'])
@login_required
def task_events(task_id):
    c=get_db(); rows=c.execute('SELECT te.*,u.name user_name FROM task_events te LEFT JOIN users u ON u.id=te.user_id AND u.tenant_id=te.tenant_id WHERE te.tenant_id=? AND te.task_id=? ORDER BY te.created_at DESC',(t(),task_id)).fetchall(); c.close(); return ok(rows_to_list(rows))

# ---------- Deliverable version workflow ----------
@completion_bp.route('/deliverables/<int:did>/versions',methods=['GET','POST'])
@login_required
def deliverable_versions(did):
    c=get_db(); d=c.execute('SELECT * FROM project_deliverables WHERE id=? AND tenant_id=?',(did,t())).fetchone()
    if not d: c.close(); return ok({'error':'Deliverable not found'},404)
    if request.method=='POST':
        if not has_permission(g.current_user,'deliverables.versions'): c.close(); return ok({'error':'Permission denied','code':'permission_denied','permission':'deliverables.versions'},403)
        data=request.get_json(force=True) or {}; fid=data.get('file_id')
        if fid and not tenant_resource_exists(c,'files',fid,t()): c.close(); return ok({'error':'file_id must belong to this workspace'},400)
        last=c.execute('SELECT COALESCE(MAX(version),0) v FROM deliverable_versions WHERE tenant_id=? AND deliverable_id=?',(t(),did)).fetchone()['v']; ver=int(data.get('version') or last+1)
        if ver<=last: c.close(); return ok({'error':'version must be greater than current version'},409)
        cur=c.execute('INSERT INTO deliverable_versions (tenant_id,deliverable_id,version,file_id,notes,created_by) VALUES (?,?,?,?,?,?)',(t(),did,ver,fid,data.get('notes'),uid())); c.execute('UPDATE project_deliverables SET version=?,status=\'submitted\',updated_at=datetime(\'now\') WHERE id=? AND tenant_id=?',(ver,did,t())); c.commit(); row=c.execute('SELECT * FROM deliverable_versions WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); fire_event('deliverable.version_created',t(),{'version':row_to_dict(row)}); return ok(row_to_dict(row),201)
    rows=c.execute('SELECT * FROM deliverable_versions WHERE tenant_id=? AND deliverable_id=? ORDER BY version DESC',(t(),did)).fetchall(); c.close(); return ok(rows_to_list(rows))

# ---------- Quotes / receivables ----------
@completion_bp.route('/quotes',methods=['GET','POST'])
@login_required
@require_permission('quotes.manage')
def quotes():
    c=get_db()
    if request.method=='POST':
        d=request.get_json(force=True) or {}; client_id=d.get('client_id');
        if client_id and not tenant_resource_exists(c,'clients',client_id,t()): c.close(); return ok({'error':'client_id must belong to this workspace'},400)
        if d.get('deal_id') and not tenant_resource_exists(c,'deals',d['deal_id'],t()): c.close(); return ok({'error':'deal_id must belong to this workspace'},400)
        if d.get('project_id') and not tenant_resource_exists(c,'projects',d['project_id'],t()): c.close(); return ok({'error':'project_id must belong to this workspace'},400)
        number=d.get('quote_number') or ('Q-'+datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S'))
        items=d.get('items') or []; subtotal=0
        for i in items: subtotal += float(i.get('quantity',1))*float(i.get('unit_price',0))
        tax=float(d.get('tax_pct',0)); total=subtotal*(1+tax/100)
        cur=c.execute('INSERT INTO quotes (tenant_id,client_id,deal_id,project_id,quote_number,status,subtotal,tax_pct,total,valid_until,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)',(t(),client_id,d.get('deal_id'),d.get('project_id'),number,'draft',subtotal,tax,total,d.get('valid_until'),d.get('notes'))); qid=cur.lastrowid
        for i in items:
            qty=float(i.get('quantity',1)); price=float(i.get('unit_price',0)); c.execute('INSERT INTO quote_items (tenant_id,quote_id,description,quantity,unit_price,tax_pct,total) VALUES (?,?,?,?,?,?,?)',(t(),qid,i.get('description','Item'),qty,price,float(i.get('tax_pct',tax)),qty*price*(1+float(i.get('tax_pct',tax))/100)))
        c.execute('INSERT INTO quote_events (tenant_id,quote_id,to_status,changed_by,note) VALUES (?,?,?,?,?)',(t(),qid,'draft',uid(),'Created')); c.commit(); row=c.execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone(); c.close(); return ok(row_to_dict(row),201)
    rows=c.execute('SELECT q.*,c.name client_name FROM quotes q LEFT JOIN clients c ON c.id=q.client_id AND c.tenant_id=q.tenant_id WHERE q.tenant_id=? ORDER BY q.id DESC',(t(),)).fetchall(); c.close(); return ok(rows_to_list(rows))

@completion_bp.route('/quotes/<int:qid>',methods=['GET','PATCH'])
@login_required
def quote_detail(qid):
    c=get_db(); q=c.execute('SELECT * FROM quotes WHERE id=? AND tenant_id=?',(qid,t())).fetchone();
    if not q: c.close(); return ok({'error':'Quote not found'},404)
    if request.method=='GET': items=c.execute('SELECT * FROM quote_items WHERE tenant_id=? AND quote_id=? ORDER BY id',(t(),qid)).fetchall(); events=c.execute('SELECT * FROM quote_events WHERE tenant_id=? AND quote_id=? ORDER BY created_at DESC',(t(),qid)).fetchall(); c.close(); d=row_to_dict(q); d.update({'items':rows_to_list(items),'events':rows_to_list(events)}); return ok(d)
    if not has_permission(g.current_user,'quotes.manage'): c.close(); return ok({'error':'Permission denied','code':'permission_denied','permission':'quotes.manage'},403)
    data=request.get_json(force=True) or {}; status=data.get('status'); allowed={'draft','sent','approved','rejected','expired','converted'}
    if status not in allowed: c.close(); return ok({'error':'Invalid quote status'},400)
    QUOTE_TRANSITIONS={'draft':{'sent','expired'},'sent':{'approved','rejected','expired'},'approved':{'converted','expired'},'rejected':set(),'expired':set(),'converted':set()}
    if status!=q['status'] and status not in QUOTE_TRANSITIONS.get(q['status'],set()):
        c.close(); return ok({'error':f"Cannot transition quote from '{q['status']}' to '{status}'"},409)
    c.execute('UPDATE quotes SET status=? WHERE id=? AND tenant_id=?',(status,qid,t())); c.execute('INSERT INTO quote_events (tenant_id,quote_id,from_status,to_status,changed_by,note) VALUES (?,?,?,?,?,?)',(t(),qid,q['status'],status,uid(),data.get('note'))); c.commit(); row=c.execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone(); c.close(); fire_event('quote.status_changed',t(),{'quote':row_to_dict(row)}); return ok(row_to_dict(row))

@completion_bp.route('/payments/<int:payment_id>/allocate',methods=['POST'])
@login_required
@require_permission('finance.reconcile')
def allocate_payment(payment_id):
    d=request.get_json(force=True) or {}; invoice_id=d.get('invoice_id'); amount=float(d.get('amount',0) or 0); c=get_db(); p=c.execute('SELECT * FROM payments WHERE id=? AND tenant_id=?',(payment_id,t())).fetchone(); inv=c.execute('SELECT * FROM invoices WHERE id=? AND tenant_id=?',(invoice_id,t())).fetchone() if invoice_id else None
    if not p or not inv: c.close(); return ok({'error':'Payment or invoice not found'},404)
    if amount<=0 or amount>float(p['amount']): c.close(); return ok({'error':'Invalid allocation amount'},400)
    if p['invoice_id']==invoice_id: pass
    allocated=scalar(c,'SELECT COALESCE(SUM(amount),0) FROM payment_allocations WHERE tenant_id=? AND payment_id=?',(t(),payment_id))
    if allocated+amount>float(p['amount'])+1e-9: c.close(); return ok({'error':'Allocation exceeds payment amount'},409)
    cur=c.execute('INSERT INTO payment_allocations (tenant_id,payment_id,invoice_id,amount) VALUES (?,?,?,?)',(t(),payment_id,invoice_id,amount)); c.execute('UPDATE invoices SET amount_paid=COALESCE(amount_paid,0)+? WHERE id=? AND tenant_id=?',(amount,invoice_id,t())); c.commit(); row=c.execute('SELECT * FROM payment_allocations WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); fire_event('payment.allocated',t(),{'allocation':row_to_dict(row)}); return ok(row_to_dict(row),201)

@completion_bp.route('/refunds',methods=['POST'])
@login_required
@require_permission('finance.refund')
def create_refund():
    d=request.get_json(force=True) or {}; amount=float(d.get('amount',0) or 0); c=get_db();
    if amount<=0: c.close(); return ok({'error':'amount must be positive'},400)
    if d.get('payment_id') and not tenant_resource_exists(c,'payments',d['payment_id'],t()): c.close(); return ok({'error':'payment_id must belong to this workspace'},400)
    if d.get('invoice_id') and not tenant_resource_exists(c,'invoices',d['invoice_id'],t()): c.close(); return ok({'error':'invoice_id must belong to this workspace'},400)
    cur=c.execute('INSERT INTO refunds (tenant_id,payment_id,invoice_id,amount,reason,status,created_by) VALUES (?,?,?,?,?,?,?)',(t(),d.get('payment_id'),d.get('invoice_id'),amount,d.get('reason'),'pending',uid())); c.commit(); row=c.execute('SELECT * FROM refunds WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); return ok(row_to_dict(row),201)

@completion_bp.route('/credit-notes',methods=['POST'])
@login_required
@require_permission('finance.credit_note')
def credit_note():
    d=request.get_json(force=True) or {}; amount=float(d.get('amount',0) or 0); c=get_db()
    if amount<=0: c.close(); return ok({'error':'amount must be positive'},400)
    inv=d.get('invoice_id');
    if inv and not tenant_resource_exists(c,'invoices',inv,t()): c.close(); return ok({'error':'invoice_id must belong to this workspace'},400)
    number=d.get('note_number') or ('CN-'+datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')); cur=c.execute('INSERT INTO credit_notes (tenant_id,invoice_id,note_number,amount,reason,status,created_by) VALUES (?,?,?,?,?,?,?)',(t(),inv,number,amount,d.get('reason'),'draft',uid())); c.commit(); row=c.execute('SELECT * FROM credit_notes WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); return ok(row_to_dict(row),201)

# ---------- Audit/activity + search ----------
@completion_bp.route('/activity/<entity_type>/<int:entity_id>',methods=['GET'])
@login_required
@require_permission('audit.view')
def activity(entity_type,entity_id):
    allowed={'project':'projects','task':'tasks','client':'clients','request':'requests','employee':'employees','invoice':'invoices','quote':'quotes','deliverable':'project_deliverables'}
    if entity_type not in allowed: return ok({'error':'Unsupported entity type'},400)
    c=get_db();
    if not tenant_resource_exists(c,allowed[entity_type],entity_id,t()): c.close(); return ok({'error':'Entity not found'},404)
    rows=c.execute('SELECT a.*,u.name user_name FROM audit_log a LEFT JOIN users u ON u.id=a.user_id AND u.tenant_id=a.tenant_id WHERE a.tenant_id=? AND a.entity_type=? AND a.entity_id=? ORDER BY a.created_at DESC LIMIT 200',(t(),entity_type,entity_id)).fetchall(); c.close(); return ok(rows_to_list(rows))

@completion_bp.route('/files/<int:file_id>/access',methods=['POST'])
@login_required
@require_permission('files.access')
def file_access(file_id):
    c=get_db(); f=c.execute('SELECT * FROM files WHERE id=? AND tenant_id=?',(file_id,t())).fetchone();
    if not f: c.close(); return ok({'error':'File not found'},404)
    ip=request.headers.get('X-Forwarded-For',request.remote_addr); c.execute('INSERT INTO file_access_log (tenant_id,file_id,user_id,action,ip_address) VALUES (?,?,?,?,?)',(t(),file_id,uid(),request.json.get('action','access') if request.is_json else 'access',ip)); c.commit(); c.close(); return ok({'status':'logged','file':row_to_dict(f)})

@completion_bp.route('/health/components',methods=['GET'])
@login_required
@require_permission('system.health')
def health_components():
    c=get_db(); checks=[]
    for name,sql in [('database','SELECT 1'),('users','SELECT COUNT(*) FROM users WHERE tenant_id=?'),('jobs','SELECT COUNT(*) FROM jobs WHERE tenant_id=? AND status=\'failed\''),('notifications','SELECT COUNT(*) FROM notifications WHERE tenant_id=? AND is_read=0')]:
        started=datetime.datetime.utcnow();
        try:
            r=c.execute(sql,(t(),)).fetchone() if '?' in sql else c.execute(sql).fetchone(); ms=(datetime.datetime.utcnow()-started).total_seconds()*1000; status='ok'
            details={'value':r[0] if r else 0}; c.execute('INSERT INTO system_health_checks (tenant_id,component,status,latency_ms,details) VALUES (?,?,?,?,?)',(t(),name,status,ms,json.dumps(details))); checks.append({'component':name,'status':status,'latency_ms':round(ms,2),'details':details})
        except Exception as exc: checks.append({'component':name,'status':'error','details':str(exc)})
    c.commit(); c.close(); return ok(checks)

# ---------- Backup control plane (does not pretend to perform cloud backup) ----------
@completion_bp.route('/backups/runs',methods=['GET','POST'])
@login_required
@require_permission('backup.manage')
def backup_runs():
    c=get_db()
    if request.method=='POST':
        d=request.get_json(force=True) or {}; cur=c.execute('INSERT INTO backup_runs (tenant_id,backup_type,storage_key,status) VALUES (?,?,?,?)',(t(),d.get('backup_type','database'),d.get('storage_key'),'started')); c.commit(); row=c.execute('SELECT * FROM backup_runs WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); return ok(row_to_dict(row),202)
    rows=c.execute('SELECT * FROM backup_runs WHERE tenant_id=? ORDER BY started_at DESC LIMIT 100',(t(),)).fetchall(); c.close(); return ok(rows_to_list(rows))


@completion_bp.route('/notifications',methods=['GET'])
@login_required
def notifications():
    c=get_db(); rows=c.execute('SELECT * FROM notifications WHERE tenant_id=? AND user_id=? ORDER BY created_at DESC LIMIT 100',(t(),uid())).fetchall(); c.close(); return ok(rows_to_list(rows))

@completion_bp.route('/notifications/<int:nid>/read',methods=['POST'])
@login_required
def notification_read(nid):
    c=get_db(); cur=c.execute('UPDATE notifications SET is_read=1 WHERE id=? AND tenant_id=? AND user_id=?',(nid,t(),uid())); c.commit(); c.close(); return ok({'updated':cur.rowcount>0})

@completion_bp.route('/client/messages',methods=['GET','POST'])
@login_required
def client_messages():
    c=get_db(); client=c.execute('SELECT c.id FROM clients c JOIN client_users cu ON cu.client_id=c.id AND cu.tenant_id=c.tenant_id WHERE cu.tenant_id=? AND cu.user_id=? AND cu.is_active=1',(t(),uid())).fetchone()
    if not client: c.close(); return ok({'error':'Client portal access is not configured'},403)
    if request.method=='POST':
        d=request.get_json(force=True) or {}; project_id=d.get('project_id'); body=(d.get('body') or '').strip()
        if project_id and not c.execute('SELECT 1 FROM projects WHERE id=? AND tenant_id=? AND client_id=?',(project_id,t(),client['id'])).fetchone(): c.close(); return ok({'error':'Project is not accessible'},404)
        if not body: c.close(); return ok({'error':'body is required'},400)
        conv=c.execute('SELECT id FROM conversations WHERE tenant_id=? AND context_type=? AND context_id=? ORDER BY id DESC LIMIT 1',(t(),'project',project_id)).fetchone() if project_id else None
        if not conv:
            cur=c.execute('INSERT INTO conversations (tenant_id,subject,context_type,context_id,created_by) VALUES (?,?,?,?,?)',(t(),d.get('subject','Client message'),'project' if project_id else 'client',project_id or client['id'],uid())); cid=cur.lastrowid; c.execute('INSERT INTO conversation_participants (tenant_id,conversation_id,user_id) VALUES (?,?,?)',(t(),cid,uid()))
        else: cid=conv['id']
        cur=c.execute('INSERT INTO conversation_messages (tenant_id,conversation_id,user_id,body,message_type) VALUES (?,?,?,?,?)',(t(),cid,uid(),body,'text')); c.commit(); row=c.execute('SELECT * FROM conversation_messages WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); fire_event('message.created',t(),{'message':row_to_dict(row)}); return ok(row_to_dict(row),201)
    rows=c.execute('SELECT m.*,cv.subject,cv.context_type,cv.context_id FROM conversation_messages m JOIN conversations cv ON cv.id=m.conversation_id AND cv.tenant_id=m.tenant_id WHERE m.tenant_id=? AND (cv.context_id=? OR (cv.context_type=\'project\' AND cv.context_id IN (SELECT id FROM projects WHERE tenant_id=? AND client_id=?))) ORDER BY m.created_at DESC LIMIT 200',(t(),client['id'],t(),client['id'])).fetchall(); c.close(); return ok(rows_to_list(rows))

@completion_bp.route('/files/<int:file_id>/versions',methods=['GET','POST'])
@login_required
@require_permission('files.manage')
def file_versions(file_id):
    c=get_db(); f=c.execute('SELECT * FROM files WHERE id=? AND tenant_id=?',(file_id,t())).fetchone()
    if not f: c.close(); return ok({'error':'File not found'},404)
    if request.method=='POST':
        d=request.get_json(force=True) or {}; last=c.execute('SELECT COALESCE(MAX(version),0) v FROM file_versions WHERE tenant_id=? AND file_id=?',(t(),file_id)).fetchone()['v']; ver=int(d.get('version') or last+1); key=d.get('storage_key') or f['storage_key']
        cur=c.execute('INSERT INTO file_versions (tenant_id,file_id,version,storage_key,size_bytes,checksum,uploaded_by) VALUES (?,?,?,?,?,?,?)',(t(),file_id,ver,key,d.get('size_bytes',f['size_bytes']),d.get('checksum',f['checksum']),uid())); c.execute('UPDATE files SET storage_key=?,size_bytes=?,checksum=? WHERE id=? AND tenant_id=?',(key,d.get('size_bytes',f['size_bytes']),d.get('checksum',f['checksum']),file_id,t())); c.commit(); row=c.execute('SELECT * FROM file_versions WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); return ok(row_to_dict(row),201)
    rows=c.execute('SELECT * FROM file_versions WHERE tenant_id=? AND file_id=? ORDER BY version DESC',(t(),file_id)).fetchall(); c.close(); return ok(rows_to_list(rows))

@completion_bp.route('/workflows',methods=['GET','POST'])
@login_required
@require_permission('workflows.manage')
def workflows():
    c=get_db()
    if request.method=='POST':
        d=request.get_json(force=True) or {}; entity=d.get('entity_type'); name=d.get('name')
        if not entity or not name: c.close(); return ok({'error':'entity_type and name are required'},400)
        cur=c.execute('INSERT INTO workflow_definitions (tenant_id,entity_type,name,config_json,is_active) VALUES (?,?,?,?,?)',(t(),entity,name,json.dumps(d.get('config',{})),int(bool(d.get('is_active',1))))); wid=cur.lastrowid
        for tr in d.get('transitions',[]): c.execute('INSERT INTO workflow_transitions (tenant_id,workflow_id,from_status,to_status,permission_code,sort_order) VALUES (?,?,?,?,?,?)',(t(),wid,tr.get('from_status'),tr.get('to_status'),tr.get('permission_code'),tr.get('sort_order',0)))
        c.commit(); row=c.execute('SELECT * FROM workflow_definitions WHERE id=?',(wid,)).fetchone(); c.close(); return ok(row_to_dict(row),201)
    rows=c.execute('SELECT * FROM workflow_definitions WHERE tenant_id=? ORDER BY entity_type,name',(t(),)).fetchall(); c.close(); return ok(rows_to_list(rows))

@completion_bp.route('/academy/assessments/<int:assessment_id>/attempts',methods=['POST'])
@login_required
@require_permission('academy.assessments')
def assessment_attempt(assessment_id):
    d=request.get_json(force=True) or {}; student_id=d.get('student_id'); score=float(d.get('score',0) or 0); c=get_db()
    if not tenant_resource_exists(c,'assessments',assessment_id,t()): c.close(); return ok({'error':'Assessment not found'},404)
    if not tenant_resource_exists(c,'students',student_id,t()): c.close(); return ok({'error':'Student not found'},404)
    if 'passed' in d: passed=int(bool(d.get('passed')))
    else:
        pass_score=c.execute('SELECT pass_score FROM assessments WHERE id=? AND tenant_id=?',(assessment_id,t())).fetchone()
        passed=int(score>=float(pass_score['pass_score'])) if pass_score and pass_score['pass_score'] is not None else 0
    cur=c.execute('INSERT INTO assessment_attempts (tenant_id,assessment_id,student_id,score,passed,attempted_at) VALUES (?,?,?,?,?,datetime(\'now\'))',(t(),assessment_id,student_id,score,passed)); c.commit(); row=c.execute('SELECT * FROM assessment_attempts WHERE id=?',(cur.lastrowid,)).fetchone(); c.close(); fire_event('academy.assessment_submitted',t(),{'attempt':row_to_dict(row)}); return ok(row_to_dict(row),201)
