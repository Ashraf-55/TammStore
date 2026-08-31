from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists, pagination_params
from auth import login_required, log_action
from policies.permissions import require_permission

sop_bp = Blueprint("sop", __name__)


@sop_bp.route("/sop/categories", methods=["GET"])
@login_required
def list_sop_categories():
    conn = get_db()
    rows = conn.execute("SELECT * FROM sop_categories WHERE tenant_id=? ORDER BY name", (g.current_user["tenant_id"],)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@sop_bp.route("/sop/categories", methods=["POST"])
@login_required
def create_sop_category():
    data = request.get_json(force=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO sop_categories (tenant_id, name) VALUES (?,?)", (g.current_user["tenant_id"], data["name"]))
        conn.commit()
    except Exception:
        conn.close()
        return jsonify({"error": "Category already exists"}), 409
    row = conn.execute("SELECT * FROM sop_categories WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@sop_bp.route("/sop", methods=["GET"])
@login_required
def list_sops():
    tenant_id = g.current_user["tenant_id"]
    category_id = request.args.get("category_id")
    search = request.args.get("q")
    conn = get_db()
    query = """SELECT s.*, c.name AS category_name FROM sops s
               LEFT JOIN sop_categories c ON c.id = s.category_id WHERE s.tenant_id = ?"""
    params = [tenant_id]
    if category_id:
        query += " AND s.category_id = ?"; params.append(category_id)
    if search:
        query += " AND (s.title LIKE ? OR s.content LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    query += " ORDER BY s.updated_at DESC"
    limit, offset = pagination_params(request)
    query += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@sop_bp.route("/sop/<int:sop_id>", methods=["GET"])
@login_required
def get_sop(sop_id):
    conn = get_db()
    row = conn.execute(
        """SELECT s.*, c.name AS category_name FROM sops s
           LEFT JOIN sop_categories c ON c.id = s.category_id WHERE s.id=? AND s.tenant_id=?""",
        (sop_id, g.current_user["tenant_id"]),
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "SOP not found"}), 404
    return jsonify(row_to_dict(row))


@sop_bp.route("/sop", methods=["POST"])
@login_required
def create_sop():
    data = request.get_json(force=True) or {}
    if not data.get("title") or not data.get("content"):
        return jsonify({"error": "title and content are required"}), 400
    conn = get_db()
    if data.get("category_id") and not tenant_resource_exists(conn,"sop_categories",data["category_id"],g.current_user["tenant_id"]): conn.close(); return jsonify({"error":"category_id must belong to this workspace"}),400
    cur = conn.execute(
        "INSERT INTO sops (tenant_id, category_id, title, content, created_by) VALUES (?,?,?,?,?)",
        (g.current_user["tenant_id"], data.get("category_id"), data["title"], data["content"], g.current_user["user_id"]),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sops WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "sop", cur.lastrowid)
    return jsonify(row_to_dict(row)), 201


@sop_bp.route("/sop/<int:sop_id>", methods=["PATCH"])
@login_required
def update_sop(sop_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    fields, values = [], []
    for key in ("title", "content", "category_id"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    fields.append("updated_at = datetime('now')")
    values += [sop_id, tenant_id]
    conn = get_db()
    conn.execute(f"UPDATE sops SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM sops WHERE id=? AND tenant_id=?", (sop_id, g.current_user["tenant_id"])).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "sop", sop_id)
    return jsonify(row_to_dict(row))


@sop_bp.route("/sop/<int:sop_id>", methods=["DELETE"])
@login_required
@require_permission("content.manage")
def delete_sop(sop_id):
    conn = get_db()
    conn.execute("DELETE FROM sops WHERE id=? AND tenant_id=?", (sop_id, g.current_user["tenant_id"]))
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "delete", "sop", sop_id)
    return jsonify({"message": "SOP deleted"})
