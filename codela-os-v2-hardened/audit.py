import json,re
from flask import request,g
from database import get_db
SECRET=re.compile(r"password|token|secret|authorization|api[_-]?key|refresh[_-]?token",re.I)
def sanitize(v):
    if isinstance(v,dict): return {k:("[REDACTED]" if SECRET.search(str(k)) else sanitize(x)) for k,x in v.items()}
    if isinstance(v,list): return [sanitize(x) for x in v[:100]]
    if isinstance(v,str): return v[:4000]+("…" if len(v)>4000 else "")
    return v
def write_audit(user_id,tenant_id,action,entity_type,entity_id=None,details=None):
    if isinstance(details,(dict,list)): details=json.dumps(sanitize(details),ensure_ascii=False,separators=(",",":"))
    elif isinstance(details,str): details=sanitize(details)
    c=get_db(); c.execute("INSERT INTO audit_log (tenant_id,user_id,action,entity_type,entity_id,details,ip_address,user_agent,request_id) VALUES (?,?,?,?,?,?,?,?,?)",(tenant_id,user_id,action,entity_type,entity_id,details,request.remote_addr,request.headers.get("User-Agent","")[:500],getattr(g,"request_id",None))); c.commit(); c.close()
