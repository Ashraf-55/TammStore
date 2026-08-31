"""
Publishing Center — Codela OS

Provides a pluggable adapter per social platform (TikTok, Instagram, YouTube,
Facebook). Each adapter's `publish()` method is where the real platform API
call belongs. Since this build environment has no network access and no
platform credentials, every adapter ships with a working MOCK implementation
that simulates a realistic response — so the whole publish → log → calendar
flow is fully testable end-to-end today.

To go live for a platform:
  1. Register a developer app with that platform and obtain an access token.
  2. Store it via POST /api/publish/connections (per tenant).
  3. Implement the marked TODO in that adapter's `_publish_live()` method
     using that platform's official API (each has very different upload
     flows — e.g. TikTok's Content Posting API, Instagram's Graph API
     Container/Publish flow, YouTube's videos.insert). This file intentionally
     keeps each adapter isolated so wiring one up doesn't touch the others.

Nothing here was tested against a live platform — only the mock path was
exercised, since that's what's actually verifiable in this environment.
"""
import time
import uuid
import os
from secret_store import encrypt_secret, decrypt_secret
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list
from auth import login_required, log_action
from policies.permissions import require_permission

publish_bp = Blueprint("publish", __name__)


class BasePlatformAdapter:
    platform_name = "base"

    def __init__(self, access_token=None):
        self.access_token = access_token

    def publish(self, content, caption):
        """Returns (success: bool, external_post_id: str|None, error: str|None, mode: 'mock'|'live')"""
        if self.access_token:
            return self._publish_live(content, caption)
        if os.getenv("CODELA_ENV") == "production":
            return False, None, f"Live platform credentials are required for {self.platform_name} in production", "unconfigured"
        return self._publish_mock(content, caption)

    def _publish_mock(self, content, caption):
        time.sleep(0.05)  # simulate network latency for a realistic feel
        fake_id = f"{self.platform_name}_mock_{uuid.uuid4().hex[:10]}"
        return True, fake_id, None, "mock"

    def _publish_live(self, content, caption):
        # TODO: implement real API call for this platform using self.access_token.
        # Left unimplemented deliberately — see module docstring.
        return False, None, f"Live publishing not yet implemented for {self.platform_name}", "live"


class TikTokAdapter(BasePlatformAdapter):
    platform_name = "tiktok"
    # TODO live: TikTok Content Posting API — POST /v2/post/publish/video/init/, then upload chunks.


class InstagramAdapter(BasePlatformAdapter):
    platform_name = "instagram"
    # TODO live: Instagram Graph API — POST /{ig-user-id}/media (create container),
    # then POST /{ig-user-id}/media_publish.


class YouTubeAdapter(BasePlatformAdapter):
    platform_name = "youtube"
    # TODO live: YouTube Data API v3 — videos.insert (resumable upload).


class FacebookAdapter(BasePlatformAdapter):
    platform_name = "facebook"
    # TODO live: Facebook Graph API — POST /{page-id}/videos.


ADAPTERS = {
    "tiktok": TikTokAdapter,
    "instagram": InstagramAdapter,
    "youtube": YouTubeAdapter,
    "facebook": FacebookAdapter,
}


# ---------------- Platform connections (credentials per tenant) ----------------

@publish_bp.route("/publish/connections", methods=["GET"])
@login_required
def list_connections():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, platform, account_name, is_active, connected_at FROM platform_connections WHERE tenant_id=?",
        (g.current_user["tenant_id"],),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@publish_bp.route("/publish/connections", methods=["POST"])
@login_required
@require_permission("publishing.manage")
def add_connection():
    data = request.get_json(force=True) or {}
    platform = data.get("platform")
    if platform not in ADAPTERS:
        return jsonify({"error": f"platform must be one of {list(ADAPTERS.keys())}"}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO platform_connections (tenant_id, platform, account_name, access_token) VALUES (?,?,?,?)",
        (g.current_user["tenant_id"], platform, data.get("account_name"), encrypt_secret(data.get("access_token"))),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, platform, account_name, is_active, connected_at FROM platform_connections WHERE id=?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "connect", "platform_connection", cur.lastrowid, details=platform)
    return jsonify(row_to_dict(row)), 201


# ---------------- Publish content ----------------

@publish_bp.route("/publish/content/<int:content_id>", methods=["POST"])
@login_required
@require_permission("publishing.manage")
def publish_content(content_id):
    """Publishes approved content to its target platform (mock unless a real
    access_token is on file for that platform), logs the attempt, and — on
    success — advances the content's status to 'published' automatically."""
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    if data.get("async"):
        from jobs import enqueue
        jid=enqueue("publish.content",{"content_id":content_id,"platform":data.get("platform"),"caption":data.get("caption")},tenant_id,idempotency_key=data.get("idempotency_key"))
        return jsonify({"status":"queued","job_id":jid}),202
    conn = get_db()

    content = conn.execute("SELECT * FROM content_ideas WHERE id=? AND tenant_id=?", (content_id, tenant_id)).fetchone()
    if content is None:
        conn.close()
        return jsonify({"error": "Content not found"}), 404

    platform = data.get("platform", content["platform"])
    if platform not in ADAPTERS:
        conn.close()
        return jsonify({"error": f"platform must be one of {list(ADAPTERS.keys())}"}), 400

    connection = conn.execute(
        "SELECT * FROM platform_connections WHERE tenant_id=? AND platform=? AND is_active=1",
        (tenant_id, platform),
    ).fetchone()
    access_token = decrypt_secret(connection["access_token"]) if connection and connection["access_token"] else None

    adapter = ADAPTERS[platform](access_token=access_token)
    success, external_id, error, mode = adapter.publish(content, data.get("caption", content["hook"]))

    status = "published" if success else "failed"
    cur = conn.execute(
        "INSERT INTO publish_log (tenant_id, content_id, platform, status, external_post_id, error_message, mode) VALUES (?,?,?,?,?,?,?)",
        (tenant_id, content_id, platform, status, external_id, error, mode),
    )

    if success:
        conn.execute("UPDATE content_ideas SET status='published' WHERE id=? AND tenant_id=?", (content_id, tenant_id))
        cal_entry = conn.execute("SELECT id FROM content_calendar WHERE content_id=? AND tenant_id=?", (content_id, tenant_id)).fetchone()
        if cal_entry:
            conn.execute("UPDATE content_calendar SET status='published' WHERE id=? AND tenant_id=?", (cal_entry["id"], tenant_id))
        else:
            conn.execute(
                "INSERT INTO content_calendar (tenant_id, content_id, platform, status, publish_date) VALUES (?,?,?,'published', date('now'))",
                (tenant_id, content_id, platform),
            )

    conn.commit()
    row = conn.execute("SELECT * FROM publish_log WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "publish", "content_idea", content_id, details=f"{platform} ({mode}): {status}")
    return jsonify(row_to_dict(row)), 201 if success else 502


@publish_bp.route("/publish/log", methods=["GET"])
@login_required
def publish_log():
    conn = get_db()
    rows = conn.execute(
        """SELECT pl.*, ci.title FROM publish_log pl
           JOIN content_ideas ci ON ci.id = pl.content_id
           WHERE pl.tenant_id=? ORDER BY pl.created_at DESC LIMIT 50""",
        (g.current_user["tenant_id"],),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))
