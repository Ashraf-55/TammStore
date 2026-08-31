from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash
from database import get_db, row_to_dict, rows_to_list, pagination_params
from auth import login_required, roles_required, log_action

users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["GET"])
@login_required
@roles_required("sales_manager", "project_manager")
def list_users():
    tenant_id = g.current_user["tenant_id"]
    role = request.args.get("role")
    conn = get_db()
    limit, offset = pagination_params(request)
    if role:
        rows = conn.execute(
            "SELECT id, name, email, role, department, is_active, created_at FROM users WHERE tenant_id=? AND role=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (tenant_id, role, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, email, role, department, is_active, created_at FROM users WHERE tenant_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (tenant_id, limit, offset),
        ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@users_bp.route("/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, role, department, is_active, created_at FROM users WHERE id=? AND tenant_id=?",
        (user_id, g.current_user["tenant_id"]),
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(row_to_dict(row))


@users_bp.route("/<int:user_id>", methods=["PATCH"])
@login_required
@roles_required()
def update_user(user_id):
    data = request.get_json(force=True) or {}
    fields, values = [], []
    for key in ("name", "role", "department", "is_active"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if "password" in data and data["password"]:
        fields.append("password_hash = ?")
        values.append(generate_password_hash(data["password"]))
    if not fields:
        return jsonify({"error": "No valid fields to update"}), 400
    values += [user_id, g.current_user["tenant_id"]]

    conn = get_db()
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)
    conn.commit()
    row = conn.execute(
        "SELECT id, name, email, role, department, is_active, created_at FROM users WHERE id=? AND tenant_id=?",
        (user_id, g.current_user["tenant_id"]),
    ).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "user", user_id)
    return jsonify(row_to_dict(row))


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@login_required
@roles_required()
def deactivate_user(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ? AND tenant_id = ?", (user_id, g.current_user["tenant_id"]))
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "deactivate", "user", user_id)
    return jsonify({"message": "User deactivated"})


@users_bp.route("/notifications", methods=["GET"])
@login_required
def my_notifications():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND tenant_id=? ORDER BY created_at DESC LIMIT 50",
        (g.current_user["user_id"], g.current_user["tenant_id"]),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@users_bp.route("/notifications/<int:notif_id>/read", methods=["PATCH"])
@login_required
def mark_notification_read(notif_id):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ? AND tenant_id = ?",
                 (notif_id, g.current_user["user_id"], g.current_user["tenant_id"]))
    conn.commit()
    conn.close()
    return jsonify({"message": "Marked as read"})
