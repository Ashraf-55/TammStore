from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists, pagination_params
from auth import login_required, log_action

assets_bp = Blueprint("assets", __name__)


@assets_bp.route("/assets", methods=["GET"])
@login_required
def list_assets():
    tenant_id = g.current_user["tenant_id"]
    status = request.args.get("status")
    owner_id = request.args.get("owner_id")
    conn = get_db()
    query = "SELECT * FROM assets WHERE tenant_id = ?"
    params = [tenant_id]
    if status:
        query += " AND status = ?"; params.append(status)
    if owner_id:
        query += " AND owner_id = ?"; params.append(owner_id)
    query += " ORDER BY created_at DESC"
    limit, offset = pagination_params(request)
    query += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@assets_bp.route("/assets/<int:asset_id>", methods=["GET"])
@login_required
def get_asset(asset_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    asset = conn.execute("SELECT * FROM assets WHERE id=? AND tenant_id=?", (asset_id, tenant_id)).fetchone()
    if asset is None:
        conn.close()
        return jsonify({"error": "Asset not found"}), 404
    logs = conn.execute("SELECT * FROM asset_maintenance_log WHERE asset_id=? AND tenant_id=? ORDER BY date DESC", (asset_id, tenant_id)).fetchall()
    conn.close()
    result = row_to_dict(asset)
    result["maintenance_log"] = rows_to_list(logs)
    return jsonify(result)


@assets_bp.route("/assets", methods=["POST"])
@login_required
def create_asset():
    data = request.get_json(force=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    conn = get_db()
    if data.get("owner_id") and not tenant_resource_exists(conn,"users",data["owner_id"],g.current_user["tenant_id"]): conn.close(); return jsonify({"error":"owner_id must belong to this workspace"}),400
    cur = conn.execute(
        """INSERT INTO assets (tenant_id, name, category, owner_id, location, status, purchase_date, value)
           VALUES (?,?,?,?,?,?,?,?)""",
        (g.current_user["tenant_id"], data["name"], data.get("category"), data.get("owner_id"), data.get("location"),
         data.get("status", "available"), data.get("purchase_date"), data.get("value")),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM assets WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "asset", cur.lastrowid)
    return jsonify(row_to_dict(row)), 201


@assets_bp.route("/assets/<int:asset_id>", methods=["PATCH"])
@login_required
def update_asset(asset_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    fields, values = [], []
    for key in ("name", "category", "owner_id", "location", "status", "purchase_date", "value"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    values += [asset_id, tenant_id]
    conn = get_db()
    conn.execute(f"UPDATE assets SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM assets WHERE id=? AND tenant_id=?", (asset_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "asset", asset_id)
    return jsonify(row_to_dict(row))


@assets_bp.route("/assets/<int:asset_id>/maintenance", methods=["POST"])
@login_required
def log_maintenance(asset_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    if not tenant_resource_exists(conn,"assets",asset_id,tenant_id): conn.close(); return jsonify({"error":"Asset not found"}),404
    cur = conn.execute(
        "INSERT INTO asset_maintenance_log (tenant_id, asset_id, notes, cost) VALUES (?,?,?,?)",
        (tenant_id, asset_id, data.get("notes"), data.get("cost", 0)),
    )
    conn.execute("UPDATE assets SET status='maintenance' WHERE id=? AND tenant_id=?", (asset_id, tenant_id))
    conn.commit()
    row = conn.execute("SELECT * FROM asset_maintenance_log WHERE id=? AND tenant_id=?", (cur.lastrowid, tenant_id)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201
