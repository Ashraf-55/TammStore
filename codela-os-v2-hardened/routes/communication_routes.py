"""
Communication Center — Codela OS

Same mock/live adapter pattern as routes/publish_routes.py, applied to
outbound WhatsApp/email/SMS instead of social posting: every send is logged
to `messages` regardless of channel, and actually reaches the provider only
once real credentials are configured (via env vars — no credentials exist
in this build environment, so every send below runs in mock mode and is
fully testable end-to-end today).

To go live for a channel:
  WhatsApp -> WhatsApp Cloud API (Meta): POST /{phone-number-id}/messages.
              Needs a permanent access token + verified phone number ID.
  Email    -> Any transactional provider (SES, SendGrid, Postmark...).
  SMS      -> Twilio or similar.
Wire the real HTTP call into that adapter's `_send_live()` — each is left
as a clearly marked TODO, isolated per-channel so wiring one up doesn't
touch the others.
"""
import os
import time
import uuid
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, tenant_resource_exists, pagination_params
from auth import login_required, log_action

communication_bp = Blueprint("communication", __name__)


class BaseChannelAdapter:
    channel_name = "base"
    env_var = None

    def __init__(self):
        self.credential = os.environ.get(self.env_var) if self.env_var else None

    def send(self, to_address, subject, body):
        """Returns (success: bool, external_id: str|None, error: str|None, mode: 'mock'|'live')"""
        if self.credential:
            return self._send_live(to_address, subject, body)
        if os.getenv("CODELA_ENV") == "production":
            return False, None, f"Live provider credentials are required for {self.channel_name} in production", "unconfigured"
        return self._send_mock(to_address, subject, body)

    def _send_mock(self, to_address, subject, body):
        time.sleep(0.03)
        return True, f"{self.channel_name}_mock_{uuid.uuid4().hex[:10]}", None, "mock"

    def _send_live(self, to_address, subject, body):
        # TODO: implement the real provider call using self.credential.
        return False, None, f"Live sending not yet implemented for {self.channel_name}", "live"


class WhatsAppAdapter(BaseChannelAdapter):
    channel_name = "whatsapp"
    env_var = "WHATSAPP_CLOUD_API_TOKEN"
    # TODO live: WhatsApp Cloud API — POST https://graph.facebook.com/v19.0/{phone-number-id}/messages


class EmailAdapter(BaseChannelAdapter):
    channel_name = "email"
    env_var = "TRANSACTIONAL_EMAIL_API_KEY"
    # TODO live: plug in SES/SendGrid/Postmark send call here.


class SMSAdapter(BaseChannelAdapter):
    channel_name = "sms"
    env_var = "SMS_PROVIDER_API_KEY"
    # TODO live: plug in Twilio (or similar) send call here.


ADAPTERS = {"whatsapp": WhatsAppAdapter, "email": EmailAdapter, "sms": SMSAdapter}


def send_via_adapter(conn, tenant_id, channel, to_address, subject, body, lead_id=None, client_id=None, user_id=None):
    """Shared by the HTTP route below AND the Automation Engine's send_message
    action, so both paths log identically to `messages`. Does not commit —
    caller owns the transaction (the automation engine batches multiple
    actions per rule into one commit; the HTTP route commits itself)."""
    if channel not in ADAPTERS:
        raise ValueError(f"channel must be one of {list(ADAPTERS.keys())}")
    adapter = ADAPTERS[channel]()
    success, external_id, error, mode = adapter.send(to_address, subject, body)
    status = "sent" if success else "failed"
    conn.execute(
        """INSERT INTO messages (tenant_id, channel, direction, lead_id, client_id, user_id, to_address, subject, body, status, external_id, error_message, mode)
           VALUES (?,?,'outbound',?,?,?,?,?,?,?,?,?,?)""",
        (tenant_id, channel, lead_id, client_id, user_id, to_address, subject, body, status, external_id, error, mode),
    )
    return {"status": status, "mode": mode, "external_id": external_id, "error": error}


# ---------------- templates ----------------

@communication_bp.route("/communication/templates", methods=["GET"])
@login_required
def list_templates():
    conn = get_db()
    channel = request.args.get("channel")
    if channel:
        rows = conn.execute("SELECT * FROM message_templates WHERE tenant_id=? AND channel=? ORDER BY name",
                             (g.current_user["tenant_id"], channel)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM message_templates WHERE tenant_id=? ORDER BY channel, name",
                             (g.current_user["tenant_id"],)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@communication_bp.route("/communication/templates", methods=["POST"])
@login_required
def create_template():
    data = request.get_json(force=True) or {}
    if not data.get("name") or data.get("channel") not in ADAPTERS or not data.get("body"):
        return jsonify({"error": f"name, body, and channel (one of {list(ADAPTERS.keys())}) are required"}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO message_templates (tenant_id, name, channel, subject, body) VALUES (?,?,?,?,?)",
        (g.current_user["tenant_id"], data["name"], data["channel"], data.get("subject"), data["body"]),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM message_templates WHERE id=? AND tenant_id=?", (cur.lastrowid, g.current_user["tenant_id"])).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "create", "message_template", cur.lastrowid)
    return jsonify(row_to_dict(row)), 201


# ---------------- sending ----------------

@communication_bp.route("/communication/send", methods=["POST"])
@login_required
def send_message():
    """Body: {channel, to, body, subject?, lead_id?, client_id?, template_id?}
    If template_id is given, its body/subject are used as the base (body param
    still wins if also provided, for a quick override)."""
    data = request.get_json(force=True) or {}
    tenant_id = g.current_user["tenant_id"]
    if data.get("async"):
        from jobs import enqueue
        if data.get("channel") not in ADAPTERS or not data.get("to") or not data.get("body"): return jsonify({"error":"channel, to and body are required for async send"}),400
        jid=enqueue("communication.send",{k:data.get(k) for k in ("channel","to","subject","body","lead_id","client_id")},tenant_id,idempotency_key=data.get("idempotency_key"))
        return jsonify({"status":"queued","job_id":jid}),202
    channel = data.get("channel")
    if channel not in ADAPTERS:
        return jsonify({"error": f"channel must be one of {list(ADAPTERS.keys())}"}), 400
    to_address = data.get("to")
    if not to_address:
        return jsonify({"error": "to is required"}), 400

    conn = get_db()
    for fk,table in (("lead_id","leads"),("client_id","clients")):
        if data.get(fk) and not tenant_resource_exists(conn,table,data[fk],tenant_id): conn.close(); return jsonify({"error":f"{fk} must belong to this workspace"}),400
    subject, body = data.get("subject"), data.get("body")
    if data.get("template_id"):
        tmpl = conn.execute("SELECT * FROM message_templates WHERE id=? AND tenant_id=?", (data["template_id"], tenant_id)).fetchone()
        if tmpl is None:
            conn.close()
            return jsonify({"error": "Template not found"}), 404
        subject = subject or tmpl["subject"]
        body = body or tmpl["body"]
    if not body:
        conn.close()
        return jsonify({"error": "body is required (directly or via template_id)"}), 400

    result = send_via_adapter(conn, tenant_id, channel, to_address, subject, body,
                               lead_id=data.get("lead_id"), client_id=data.get("client_id"),
                               user_id=g.current_user["user_id"])
    conn.commit()
    row = conn.execute("SELECT * FROM messages WHERE tenant_id=? ORDER BY id DESC LIMIT 1", (tenant_id,)).fetchone()
    conn.close()
    log_action(g.current_user["user_id"], "send", "message", row["id"], details=f"{channel} ({result['mode']}): {result['status']}")
    return jsonify(row_to_dict(row)), 201 if result["status"] == "sent" else 502


@communication_bp.route("/communication/log", methods=["GET"])
@login_required
def message_log():
    tenant_id = g.current_user["tenant_id"]
    lead_id = request.args.get("lead_id")
    conn = get_db()
    limit, offset = pagination_params(request)
    if lead_id:
        rows = conn.execute("SELECT * FROM messages WHERE tenant_id=? AND lead_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                             (tenant_id, lead_id, limit, offset)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM messages WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                             (tenant_id, limit, offset)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))
