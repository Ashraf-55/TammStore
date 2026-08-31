"""
Creator Portal — Codela OS

A restricted set of endpoints for 'model'-role accounts (dedicated per-creator
logins provisioned via POST /api/creators with create_login=true). A creator
can only ever see their OWN assigned content/tasks and their own submissions —
never other creators' or the full staff dataset.

'Download a task/video' is implemented as viewing the assigned content's
script/hook/video_url (no binary file storage exists yet, so any actual video
file lives at an external link the team pastes into video_url).
'Upload their own tasks' is implemented as submitting a new content idea
(with an optional video_url link) that lands in the normal pipeline tagged
submitted_by_creator=1, visible to the media team like any other idea.
"""
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list
from auth import login_required

creator_portal_bp = Blueprint("creator_portal", __name__)


def require_creator_profile(conn):
    """Every model-role user must be linked to exactly one creators row to use the portal."""
    creator = conn.execute(
        "SELECT * FROM creators WHERE user_id=? AND tenant_id=?",
        (g.current_user["user_id"], g.current_user["tenant_id"]),
    ).fetchone()
    return creator


@creator_portal_bp.route("/creator-portal/me", methods=["GET"])
@login_required
def portal_me():
    if g.current_user["role"] != "model":
        return jsonify({"error": "This portal is for creator/model accounts only"}), 403
    conn = get_db()
    creator = require_creator_profile(conn)
    conn.close()
    if creator is None:
        return jsonify({"error": "No creator profile linked to this account"}), 404
    return jsonify(row_to_dict(creator))


@creator_portal_bp.route("/creator-portal/my-content", methods=["GET"])
@login_required
def my_content():
    if g.current_user["role"] != "model":
        return jsonify({"error": "This portal is for creator/model accounts only"}), 403
    conn = get_db()
    creator = require_creator_profile(conn)
    if creator is None:
        conn.close()
        return jsonify({"error": "No creator profile linked to this account"}), 404
    rows = conn.execute(
        "SELECT * FROM content_ideas WHERE creator_id=? AND tenant_id=? ORDER BY created_at DESC",
        (creator["id"], g.current_user["tenant_id"]),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@creator_portal_bp.route("/creator-portal/my-tasks", methods=["GET"])
@login_required
def my_tasks():
    """Any Project tasks directly assigned to this creator's user account."""
    if g.current_user["role"] != "model":
        return jsonify({"error": "This portal is for creator/model accounts only"}), 403
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE assignee_id=? AND tenant_id=? ORDER BY deadline",
        (g.current_user["user_id"], g.current_user["tenant_id"]),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@creator_portal_bp.route("/creator-portal/submit", methods=["POST"])
@login_required
def submit_content():
    """Creator uploads/submits their own content idea or finished video link."""
    if g.current_user["role"] != "model":
        return jsonify({"error": "This portal is for creator/model accounts only"}), 403
    data = request.get_json(force=True) or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    conn = get_db()
    creator = require_creator_profile(conn)
    if creator is None:
        conn.close()
        return jsonify({"error": "No creator profile linked to this account"}), 404

    cur = conn.execute(
        """INSERT INTO content_ideas (tenant_id, title, category, platform, creator_id, hook, script,
           video_url, submitted_by_creator, status)
           VALUES (?,?,?,?,?,?,?,?,1,'review')""",
        (g.current_user["tenant_id"], data["title"], data.get("category"), data.get("platform"),
         creator["id"], data.get("hook"), data.get("script"), data.get("video_url")),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM content_ideas WHERE id=? AND tenant_id=?", (cur.lastrowid, g.current_user["tenant_id"])).fetchone()

    # notify managers that a creator submitted something needing review
    managers = conn.execute(
        "SELECT id FROM users WHERE tenant_id=? AND role IN ('content_manager','founder','admin')",
        (g.current_user["tenant_id"],),
    ).fetchall()
    for m in managers:
        conn.execute(
            "INSERT INTO notifications (tenant_id, user_id, type, message, link) VALUES (?,?,?,?,?)",
            (g.current_user["tenant_id"], m["id"], "creator_submission",
             f"{creator['stage_name']} submitted: {data['title']}", f"/content/{cur.lastrowid}"),
        )
    conn.commit()
    conn.close()
    return jsonify(row_to_dict(row)), 201
