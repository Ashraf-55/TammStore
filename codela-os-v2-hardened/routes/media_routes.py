from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists, pagination_params
from auth import login_required, log_action
from policies.permissions import require_permission, has_permission
import secrets
from werkzeug.security import generate_password_hash

media_bp = Blueprint("media", __name__)

CONTENT_STATUSES = ("idea", "research", "script", "approved", "shooting",
                     "editing", "review", "client_approval", "scheduled", "published")


# ---------------- CREATORS ----------------

@media_bp.route("/creators", methods=["GET"])
@login_required
def list_creators():
    conn = get_db()
    limit, offset = pagination_params(request)
    rows = conn.execute("SELECT * FROM creators WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (g.current_user["tenant_id"], limit, offset)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


def generate_unique_login_code(conn, tenant_id):
    for _ in range(20):
        code = f"MDL-{secrets.randbelow(9000) + 1000}"
        exists = conn.execute("SELECT id FROM creators WHERE tenant_id=? AND login_code=?", (tenant_id, code)).fetchone()
        if not exists:
            return code
    return f"MDL-{secrets.token_hex(4).upper()}"


@media_bp.route("/creators", methods=["POST"])
@login_required
@require_permission("content.manage")
def create_creator():
    """Creates a Creator profile. If create_login=true, also provisions a
    dedicated portal account (its own login_code + temporary password) so the
    model/creator can log into the restricted Creator Portal — separate from
    the main staff account system, per-creator, per the request."""
    data = request.get_json(force=True) or {}
    if not data.get("stage_name"):
        return jsonify({"error": "stage_name is required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    user_id = data.get("user_id")
    if user_id and not tenant_resource_exists(conn,"users",user_id,tenant_id): conn.close(); return jsonify({"error":"user_id must belong to this workspace"}),400
    login_code = None
    temp_password = None

    if data.get("create_login"):
        tenant = conn.execute("SELECT slug FROM tenants WHERE id=?", (tenant_id,)).fetchone()
        login_code = generate_unique_login_code(conn, tenant_id)
        temp_password = secrets.token_urlsafe(6)
        pseudo_email = f"{login_code.lower()}@{tenant['slug']}.portal.codela"
        cur = conn.execute(
            "INSERT INTO users (tenant_id, name, email, password_hash, role) VALUES (?,?,?,?,'model')",
            (tenant_id, data["stage_name"], pseudo_email, generate_password_hash(temp_password)),
        )
        conn.commit()
        user_id = cur.lastrowid

    cur = conn.execute(
        "INSERT INTO creators (tenant_id, user_id, login_code, stage_name, niche, content_pillars) VALUES (?,?,?,?,?,?)",
        (tenant_id, user_id, login_code, data.get("stage_name"), data.get("niche"), data.get("content_pillars")),
    )
    conn.commit()
    row = row_to_dict(conn.execute("SELECT * FROM creators WHERE id=? AND tenant_id=?", (cur.lastrowid, tenant_id)).fetchone())
    conn.close()
    if login_code:
        row["portal_login_code"] = login_code
        row["portal_temp_password"] = temp_password
        log_action(g.current_user["user_id"], "create_portal_login", "creator", cur.lastrowid, details=login_code)
    return jsonify(row), 201


@media_bp.route("/creators/<int:creator_id>/performance", methods=["GET"])
@login_required
def creator_performance(creator_id):
    conn = get_db()
    rows = conn.execute(
        """SELECT ci.id, ci.title, ci.platform, ci.status,
                  ca.views, ca.reach, ca.likes, ca.comments, ca.shares, ca.saves
           FROM content_ideas ci
           LEFT JOIN content_analytics ca ON ca.content_id = ci.id
           WHERE ci.creator_id = ? AND ci.tenant_id = ?
           ORDER BY ca.views DESC""",
        (creator_id, g.current_user["tenant_id"]),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ---------------- CONTENT IDEAS / PIPELINE ----------------

@media_bp.route("/content", methods=["GET"])
@login_required
def list_content():
    tenant_id = g.current_user["tenant_id"]
    status = request.args.get("status")
    creator_id = request.args.get("creator_id")
    conn = get_db()
    query = "SELECT * FROM content_ideas WHERE tenant_id = ?"
    params = [tenant_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    if creator_id:
        query += " AND creator_id = ?"
        params.append(creator_id)
    query += " ORDER BY created_at DESC"
    limit, offset = pagination_params(request)
    query += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@media_bp.route("/content", methods=["POST"])
@login_required
def create_content():
    data = request.get_json(force=True) or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    if data.get("creator_id") and not tenant_resource_exists(conn,"creators",data["creator_id"],tenant_id): conn.close(); return jsonify({"error":"creator_id must belong to this workspace"}),400
    cur = conn.execute(
        """INSERT INTO content_ideas (tenant_id, title, category, platform, creator_id, hook, script, status, expected_goal)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (tenant_id, data.get("title"), data.get("category"), data.get("platform"), data.get("creator_id"),
         data.get("hook"), data.get("script"), data.get("status", "idea"), data.get("expected_goal")),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM content_ideas WHERE id=? AND tenant_id=?", (cur.lastrowid, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "content_idea", cur.lastrowid)
    return jsonify(row_to_dict(row)), 201


@media_bp.route("/content/<int:content_id>", methods=["PATCH"])
@login_required
@require_permission("content.manage")
def update_content(content_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    if "status" in data and data["status"] not in CONTENT_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of {CONTENT_STATUSES}"}), 400
    if data.get("status") == "approved" and not has_permission(g.current_user, "content.workflow"):
        return jsonify({"error": "Permission denied", "code": "permission_denied", "permission": "content.workflow"}), 403
    fields, values = [], []
    for key in ("title", "category", "platform", "creator_id", "hook", "script", "status", "expected_goal"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    values += [content_id, tenant_id]
    conn = get_db()
    conn.execute(f"UPDATE content_ideas SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)

    # Automation: when content is approved, auto-create a calendar entry
    if data.get("status") == "approved":
        existing_cal = conn.execute("SELECT id FROM content_calendar WHERE content_id=? AND tenant_id=?", (content_id, tenant_id)).fetchone()
        if not existing_cal:
            conn.execute("INSERT INTO content_calendar (tenant_id, content_id, status) VALUES (?, ?, 'planned')", (tenant_id, content_id))
    conn.commit()
    row = conn.execute("SELECT * FROM content_ideas WHERE id=? AND tenant_id=?", (content_id, tenant_id)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "update", "content_idea", content_id)
    return jsonify(row_to_dict(row))


# ---------------- CALENDAR ----------------

@media_bp.route("/calendar", methods=["GET"])
@login_required
def list_calendar():
    conn = get_db()
    rows = conn.execute(
        """SELECT cc.*, ci.title, ci.platform AS content_platform
           FROM content_calendar cc
           JOIN content_ideas ci ON ci.id = cc.content_id
           WHERE cc.tenant_id = ?
           ORDER BY cc.publish_date""",
        (g.current_user["tenant_id"],),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@media_bp.route("/calendar/<int:entry_id>", methods=["PATCH"])
@login_required
def update_calendar_entry(entry_id):
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    fields, values = [], []
    for key in ("shoot_date", "editor_id", "designer_id", "publish_date", "platform", "status"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No valid fields"}), 400
    values += [entry_id, tenant_id]
    conn = get_db()
    conn.execute(f"UPDATE content_calendar SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM content_calendar WHERE id=? AND tenant_id=?", (entry_id, tenant_id)).fetchone()
    conn.close()
    return jsonify(row_to_dict(row))


# ---------------- ANALYTICS ----------------

@media_bp.route("/content/<int:content_id>/analytics", methods=["POST"])
@login_required
def record_analytics(content_id):
    data = request.get_json(force=True) or {}
    conn = get_db()
    if not tenant_resource_exists(conn,"content_ideas",content_id,g.current_user["tenant_id"]):
        conn.close(); return jsonify({"error":"Content not found"}),404
    cur = conn.execute(
        """INSERT INTO content_analytics (tenant_id, content_id, views, reach, likes, comments, shares, saves, watch_time_sec)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (g.current_user["tenant_id"], content_id, data.get("views", 0), data.get("reach", 0), data.get("likes", 0),
         data.get("comments", 0), data.get("shares", 0), data.get("saves", 0), data.get("watch_time_sec", 0)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM content_analytics WHERE id=? AND tenant_id=?", (cur.lastrowid,g.current_user["tenant_id"])).fetchone()
    conn.close()
    return jsonify(row_to_dict(row)), 201


@media_bp.route("/content/best", methods=["GET"])
@login_required
def best_content():
    """Ranking: best content by views (Gold/Silver/Bronze tiers)."""
    limit = int(request.args.get("limit", 10))
    conn = get_db()
    rows = conn.execute(
        """SELECT ci.id, ci.title, ci.platform, SUM(ca.views) AS total_views,
                  SUM(ca.likes) AS total_likes, SUM(ca.shares) AS total_shares
           FROM content_ideas ci
           JOIN content_analytics ca ON ca.content_id = ci.id
           WHERE ci.tenant_id = ?
           GROUP BY ci.id
           ORDER BY total_views DESC
           LIMIT ?""",
        (g.current_user["tenant_id"], limit),
    ).fetchall()
    conn.close()
    ranked = rows_to_list(rows)
    tiers = ["🥇 Best", "🥈 Good", "🥉 Weak"]
    for i, item in enumerate(ranked):
        third = max(len(ranked) // 3, 1)
        item["tier"] = tiers[min(i // third, 2)]
    return jsonify(ranked)
