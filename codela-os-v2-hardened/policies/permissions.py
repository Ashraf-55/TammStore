from functools import wraps
from flask import g, jsonify
from database import get_db

LEGACY_ROLE_PERMISSIONS = {
    "founder": {"*"},
    "admin": {"*"},
    "project_manager": {"projects.view","projects.create","projects.update","projects.assign","tasks.view","tasks.create","tasks.update","tasks.assign","requests.view","requests.assign","requests.resolve","clients.view","clients.update","deliverables.approve"},
    "sales": {"clients.view","clients.create","clients.update","crm.view","crm.manage","requests.view"},
    "sales_manager": {"clients.view","clients.create","clients.update","crm.view","crm.manage","requests.view"},
    "accountant": {"finance.view","finance.invoice.create","finance.payment.create","clients.view","projects.view"},
    "content_manager": {"content.view","content.manage","projects.view","tasks.view","tasks.create","tasks.update","publishing.manage","deliverables.approve","content.workflow"},
    "content_creator": {"content.view","content.manage","tasks.view","tasks.update"},
    "designer": {"projects.view","tasks.view","tasks.update","content.view","content.manage"},
    "video_editor": {"projects.view","tasks.view","tasks.update","content.view","content.manage"},
    "developer": {"projects.view","tasks.view","tasks.update"},
    "moderator": {"projects.view","tasks.view","requests.view","requests.update"},
    "model": {"content.view","content.manage","tasks.view","tasks.update"},
}

def has_permission(user, permission):
    if not user:
        return False
    if user.get("role") in ("founder", "admin"):
        return True
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT 1 FROM user_roles ur
            JOIN role_permissions rp ON rp.role_id=ur.role_id
            JOIN permissions p ON p.id=rp.permission_id
            WHERE ur.tenant_id=? AND ur.user_id=? AND p.code=? LIMIT 1
        """, (user["tenant_id"], user["user_id"], permission)).fetchone()
    finally:
        conn.close()
    if row:
        return True
    return permission in LEGACY_ROLE_PERMISSIONS.get(user.get("role"), set()) or "*" in LEGACY_ROLE_PERMISSIONS.get(user.get("role"), set())

def require_permission(permission):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not has_permission(g.current_user, permission):
                return jsonify({"error":"Permission denied","code":"permission_denied","permission":permission}), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorator
