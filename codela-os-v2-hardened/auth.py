import jwt
import os
import secrets
import hashlib
import re
from functools import wraps
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g, current_app, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, row_to_dict, rows_to_list
import totp as totp_lib
from validation import strict_json
from audit import write_audit

auth_bp = Blueprint("auth", __name__)

JWT_ALGO = "HS256"
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 30
PRE_AUTH_TOKEN_MINUTES = 5  # short-lived token used only to complete a 2FA challenge
PRE_AUTH_MAX_ATTEMPTS = 5

VALID_ROLES = (
    "founder", "admin", "sales", "sales_manager", "content_manager",
    "content_creator", "model", "moderator", "designer", "video_editor",
    "developer", "project_manager", "accountant",
)


# ---------------- token helpers ----------------

def create_access_token(user):
    payload = {
        "type": "access",
        "jti": secrets.token_urlsafe(24),
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "role": user["role"],
        "email": user["email"],
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=JWT_ALGO)


def create_pre_auth_token(conn, user):
    """Create a short-lived, single-use 2FA challenge."""
    jti = secrets.token_urlsafe(24)
    expires_at = datetime.utcnow() + timedelta(minutes=PRE_AUTH_TOKEN_MINUTES)
    conn.execute("UPDATE auth_challenges SET used_at=datetime('now') WHERE user_id=? AND tenant_id=? AND used_at IS NULL", (user["id"], user["tenant_id"]))
    conn.execute(
        "INSERT INTO auth_challenges (jti, user_id, tenant_id, expires_at, attempts) VALUES (?,?,?,?,0)",
        (jti, user["id"], user["tenant_id"], expires_at.isoformat()),
    )
    conn.commit()
    payload = {
        "type": "pre_auth",
        "jti": jti,
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "exp": expires_at,
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=JWT_ALGO)


def decode_token(token, expected_type=None):
    last=None
    for key in current_app.config.get("SECRET_KEYS",[current_app.config["SECRET_KEY"]]):
        try:
            payload=jwt.decode(token,key,algorithms=[JWT_ALGO])
            if expected_type and payload.get("type")!=expected_type:raise jwt.InvalidTokenError("Unexpected token type")
            return payload
        except jwt.InvalidTokenError as e:last=e
    raise last or jwt.InvalidTokenError("Invalid token")



def _cookie_auth_enabled():
    return os.getenv("CODELA_COOKIE_AUTH", "1" if os.getenv("CODELA_ENV") == "production" else "0") == "1"

def _set_refresh_cookie(resp, raw_token):
    if _cookie_auth_enabled():
        resp.set_cookie("codela_refresh", raw_token, max_age=REFRESH_TOKEN_DAYS*86400, httponly=True, secure=os.getenv("CODELA_ENV")=="production", samesite="None" if os.getenv("CODELA_ENV")=="production" else "Lax", path="/api/auth")
    return resp

def _clear_refresh_cookie(resp):
    if _cookie_auth_enabled(): resp.delete_cookie("codela_refresh", path="/api/auth")
    return resp

def _session_response(payload, raw_refresh):
    if not _cookie_auth_enabled(): payload["refresh_token"] = raw_refresh
    return _set_refresh_cookie(make_response(jsonify(payload)), raw_refresh)

def hash_refresh_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def is_client_portal_user(conn, user):
    row = conn.execute(
        "SELECT 1 FROM client_users WHERE tenant_id=? AND user_id=? AND is_active=1",
        (user["tenant_id"], user["id"]),
    ).fetchone()
    return bool(row)


def portal_client_id(conn, user):
    """If the current user is a client-portal account, return the client_id
    they're scoped to (None if they're not a client-portal user at all).
    A client-portal user must never see another client's data, regardless
    of tenant-level permissions they may otherwise hold."""
    row = conn.execute(
        "SELECT client_id FROM client_users WHERE tenant_id=? AND user_id=? AND is_active=1",
        (user["tenant_id"], user.get("id") or user.get("user_id")),
    ).fetchone()
    return row["client_id"] if row else None


def issue_session(conn, user, user_agent=None, ip_address=None):
    """Creates a new opaque refresh token, stores only its hash (so a DB leak
    doesn't leak usable tokens), and returns the raw token to hand to the client."""
    raw_token = secrets.token_urlsafe(48)
    expires_at = (datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS)).isoformat()
    conn.execute(
        """INSERT INTO sessions (user_id, tenant_id, refresh_token_hash, user_agent, ip_address, expires_at)
           VALUES (?,?,?,?,?,?)""",
        (user["id"], user["tenant_id"], hash_refresh_token(raw_token), user_agent, ip_address, expires_at),
    )
    conn.commit()
    return raw_token


def _hash_api_key(raw_key):
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _authenticate_api_key(raw_key):
    """Returns a payload dict shaped like a decoded JWT (user_id, tenant_id,
    role, jti=None) if raw_key is a valid, non-revoked, non-expired API key;
    otherwise None. The key authenticates as a delegate of its creator —
    same tenant, same role/permissions as that user currently has."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT ak.*, u.role as user_role, u.is_active as user_active FROM api_keys ak JOIN users u ON u.id=ak.user_id AND u.tenant_id=ak.tenant_id WHERE ak.key_hash=?",
            (_hash_api_key(raw_key),),
        ).fetchone()
        if not row or row["revoked_at"] is not None:
            return None
        if row["expires_at"] and row["expires_at"] < datetime.utcnow().isoformat():
            return None
        if not row["user_active"]:
            return None
        conn.execute("UPDATE api_keys SET last_used_at=datetime('now') WHERE id=?", (row["id"],))
        conn.commit()
        return {"user_id": row["user_id"], "tenant_id": row["tenant_id"], "role": row["user_role"], "jti": None, "api_key_id": row["id"]}
    finally:
        conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and auth_header.split(" ", 1)[1].startswith("ck_"):
            payload = _authenticate_api_key(auth_header.split(" ", 1)[1])
            if payload is None:
                return jsonify({"error": "Invalid or revoked API key"}), 401
        elif not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        else:
            token = auth_header.split(" ", 1)[1]
            try:
                payload = decode_token(token, expected_type="access")
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired", "code": "token_expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

        # 'model' accounts are external, per-creator portal logins — they must
        # never reach general staff data (leads, finance, other creators'
        # content, etc), regardless of whether an individual route remembered
        # to add a role check. Allow only the Creator Portal blueprint and
        # universal account-management endpoints (login/me/logout/sessions).
        if payload.get("role") == "model" and request.blueprint not in ("creator_portal", "auth"):
            return jsonify({"error": "This account only has access to the Creator Portal"}), 403

        # Client-portal accounts (any user linked via client_users) are
        # external customers — they must never reach the general staff API
        # (which only checks tenant_id, not "does this client own this
        # record"), regardless of whether an individual route remembered a
        # client-visibility check. Restrict them to the dedicated
        # tenant-safe /api/client/* read model plus universal auth endpoints.
        if request.blueprint != "auth" and not (request.path == "/api/client" or request.path.startswith("/api/client/")):
            conn_cp = get_db()
            try:
                is_portal = conn_cp.execute(
                    "SELECT 1 FROM client_users WHERE tenant_id=? AND user_id=? AND is_active=1",
                    (payload.get("tenant_id"), payload.get("user_id")),
                ).fetchone()
            finally:
                conn_cp.close()
            if is_portal:
                return jsonify({"error": "This account only has access to the Client Portal"}), 403

        conn=get_db(); revoked=conn.execute("SELECT 1 FROM access_token_revocations WHERE jti=? AND expires_at>?",(payload.get("jti"),datetime.utcnow().isoformat())).fetchone() if payload.get("jti") else None; live=conn.execute("SELECT id,tenant_id,role,is_active FROM users WHERE id=? AND tenant_id=?",(payload.get("user_id"),payload.get("tenant_id"))).fetchone(); tenant=conn.execute("SELECT is_active FROM tenants WHERE id=?",(payload.get("tenant_id"),)).fetchone();conn.close()
        if revoked or live is None or not live["is_active"] or live["role"]!=payload.get("role"):return jsonify({"error":"Session is no longer valid","code":"session_invalid"}),401
        if tenant is None or not tenant["is_active"]:return jsonify({"error":"This workspace is suspended. Please contact your administrator or update your billing plan.","code":"tenant_suspended"}),403
        g.current_user = payload
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*allowed_roles):
    """Restrict an endpoint to specific roles. founder/admin always pass."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                return jsonify({"error": "Unauthorized"}), 401
            if user["role"] in ("founder", "admin") or user["role"] in allowed_roles:
                return fn(*args, **kwargs)
            return jsonify({"error": "Forbidden: insufficient role"}), 403
        return wrapper
    return decorator


def log_action(user_id,action,entity_type,entity_id=None,details=None,tenant_id=None):
 if tenant_id is None:
  c=get_db();r=c.execute("SELECT tenant_id FROM users WHERE id=?",(user_id,)).fetchone();c.close();tenant_id=r["tenant_id"] if r else None
 write_audit(user_id,tenant_id,action,entity_type,entity_id,details)


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or secrets.token_hex(4)


def record_login_attempt(email, tenant_id, success, ip_address=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO login_attempts (email, tenant_id, success, ip_address) VALUES (?,?,?,?)",
        (email, tenant_id, 1 if success else 0, ip_address if ip_address is not None else request.remote_addr),
    )
    conn.commit()
    conn.close()


def is_login_rate_limited(conn, email, ip_address):
    """Require both email+IP and IP-wide throttling to be below the limit.

    This prevents an attacker from locking out a victim by targeting only the
    victim's email, while still slowing credential stuffing from one address.
    """
    by_identity = conn.execute(
        """SELECT COUNT(*) c FROM login_attempts
           WHERE email=? AND ip_address=? AND success=0
             AND created_at >= datetime('now', '-15 minutes')""",
        (email, ip_address),
    ).fetchone()["c"]
    by_ip = conn.execute(
        """SELECT COUNT(*) c FROM login_attempts
           WHERE ip_address=? AND success=0
             AND created_at >= datetime('now', '-15 minutes')""",
        (ip_address,),
    ).fetchone()["c"]
    return by_identity >= 5 or by_ip >= 30


# ---------------- registration (creates a new tenant) ----------------

@auth_bp.route("/register", methods=["POST"])
@strict_json({"name":(str,True,120),"email":(str,True,320),"password":(str,True,200),"company_name":(str,True,160)})
def register():
    """Self-serve sign-up: creates a brand-new tenant (company workspace) and
    its first user as 'founder'. To add teammates to an EXISTING tenant, use
    the authenticated /auth/invite endpoint instead."""
    data = request.get_json(force=True) or {}
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    company_name = data.get("company_name")

    if not all([name, email, password, company_name]):
        return jsonify({"error": "name, email, password, and company_name are required"}), 400
    if len(password) < 12:
        return jsonify({"error": "Password must be at least 12 characters"}), 400

    conn = get_db()
    base_slug = slugify(company_name)
    slug = base_slug
    n = 1
    while conn.execute("SELECT id FROM tenants WHERE slug=?", (slug,)).fetchone():
        n += 1
        slug = f"{base_slug}-{n}"

    cur = conn.execute("INSERT INTO tenants (name, slug) VALUES (?,?)", (company_name, slug))
    conn.commit()
    tenant_id = cur.lastrowid

    password_hash = generate_password_hash(password)
    cur = conn.execute(
        "INSERT INTO users (tenant_id, name, email, password_hash, role) VALUES (?,?,?,?,'founder')",
        (tenant_id, name, email, password_hash),
    )
    conn.commit()
    user_id = cur.lastrowid
    user = row_to_dict(conn.execute(
        "SELECT id, tenant_id, name, email, role, created_at FROM users WHERE id=?", (user_id,)
    ).fetchone())

    # Every new workspace starts on a 14-day trial subscription (SaaS Billing Engine)
    from routes.billing_routes import create_trial_subscription
    create_trial_subscription(conn, tenant_id)
    conn.commit()

    tenant = row_to_dict(conn.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone())

    dev_verify_token = _issue_email_verification_token(conn, tenant_id, user_id)
    conn.commit()

    raw_refresh = issue_session(conn, user, request.headers.get("User-Agent"), request.remote_addr)
    conn.close()

    log_action(user_id, "register", "tenant", tenant_id, details=f"created workspace '{company_name}'", tenant_id=tenant_id)
    access_token = create_access_token(user)
    response_payload = {"user": user, "tenant": tenant, "access_token": access_token}
    from config import PRODUCTION
    if not PRODUCTION:
        response_payload["dev_verify_token"] = dev_verify_token
    return _session_response(response_payload, raw_refresh) if _cookie_auth_enabled() else (jsonify({**response_payload, "refresh_token": raw_refresh}), 201)


@auth_bp.route("/invite", methods=["POST"])
@login_required
@roles_required()
def invite_member():
    """Create a PENDING invitation for the CALLER's tenant (founder/admin only).
    No `users` row is created here — the invitee only becomes an actual user
    by calling /auth/accept-invite with a valid token. This avoids the old
    design flaw of creating an active account with a temp password that was
    returned directly in the API response."""
    data = request.get_json(force=True) or {}
    name = data.get("name")
    email = (data.get("email") or "").strip().lower()
    role = data.get("role", "sales")

    if not all([name, email]):
        return jsonify({"error": "name and email are required"}), 400
    if role not in VALID_ROLES:
        return jsonify({"error": f"Invalid role. Must be one of {VALID_ROLES}"}), 400

    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    existing_user = conn.execute("SELECT id FROM users WHERE tenant_id=? AND email=?", (tenant_id, email)).fetchone()
    if existing_user:
        conn.close()
        return jsonify({"error": "Email already registered in this workspace"}), 409

    from routes.billing_routes import check_usage_limit
    allowed, used, limit = check_usage_limit(conn, tenant_id, "users")
    if not allowed:
        conn.close()
        return jsonify({"error": f"Plan limit reached: {used}/{limit} users used. Upgrade your plan to invite more.",
                         "code": "plan_limit_reached"}), 402

    # Superseding an earlier pending invite to the same email keeps only one
    # valid link outstanding at a time.
    conn.execute(
        "UPDATE invitations SET status='revoked', revoked_at=datetime('now') WHERE tenant_id=? AND email=? AND status='pending'",
        (tenant_id, email),
    )
    raw_token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=INVITE_EXPIRY_DAYS)).isoformat()
    cur = conn.execute(
        "INSERT INTO invitations (tenant_id, email, name, role, invited_by, token_hash, expires_at) VALUES (?,?,?,?,?,?,?)",
        (tenant_id, email, name, role, g.current_user["user_id"], _hash_reset_token(raw_token), expires_at),
    )
    conn.commit()
    invite = row_to_dict(conn.execute("SELECT id, email, name, role, status, expires_at, created_at FROM invitations WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()
    log_action(g.current_user["user_id"], "invite", "invitation", cur.lastrowid)

    from config import PRODUCTION
    result = {"invitation": invite}
    if not PRODUCTION:
        result["dev_invite_token"] = raw_token
        result["dev_note"] = "Email delivery is not configured; token returned here only because CODELA_ENV != production."
    return jsonify(result), 201


@auth_bp.route("/invitations", methods=["GET"])
@login_required
@roles_required()
def list_invitations():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    status = request.args.get("status")
    if status:
        rows = conn.execute("SELECT id, email, name, role, status, expires_at, accepted_at, revoked_at, created_at FROM invitations WHERE tenant_id=? AND status=? ORDER BY created_at DESC", (tenant_id, status)).fetchall()
    else:
        rows = conn.execute("SELECT id, email, name, role, status, expires_at, accepted_at, revoked_at, created_at FROM invitations WHERE tenant_id=? ORDER BY created_at DESC", (tenant_id,)).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@auth_bp.route("/invitations/<int:invite_id>/revoke", methods=["POST"])
@login_required
@roles_required()
def revoke_invitation(invite_id):
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    row = conn.execute("SELECT * FROM invitations WHERE id=? AND tenant_id=?", (invite_id, tenant_id)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Invitation not found"}), 404
    if row["status"] != "pending":
        conn.close()
        return jsonify({"error": f"Cannot revoke an invitation with status '{row['status']}'"}), 409
    conn.execute("UPDATE invitations SET status='revoked', revoked_at=datetime('now') WHERE id=?", (invite_id,))
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "revoke_invitation", "invitation", invite_id)
    return jsonify({"message": "Invitation revoked"}), 200


@auth_bp.route("/invitations/<int:invite_id>/resend", methods=["POST"])
@login_required
@roles_required()
def resend_invitation(invite_id):
    """Issues a fresh token + expiry for an existing pending/expired invite,
    invalidating the old link."""
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    row = conn.execute("SELECT * FROM invitations WHERE id=? AND tenant_id=?", (invite_id, tenant_id)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Invitation not found"}), 404
    if row["status"] not in ("pending", "expired"):
        conn.close()
        return jsonify({"error": f"Cannot resend an invitation with status '{row['status']}'"}), 409
    raw_token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=INVITE_EXPIRY_DAYS)).isoformat()
    conn.execute("UPDATE invitations SET status='pending', token_hash=?, expires_at=? WHERE id=?", (_hash_reset_token(raw_token), expires_at, invite_id))
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "resend_invitation", "invitation", invite_id)

    from config import PRODUCTION
    result = {"message": "Invitation resent"}
    if not PRODUCTION:
        result["dev_invite_token"] = raw_token
    return jsonify(result), 200


@auth_bp.route("/accept-invite", methods=["POST"])
@strict_json({"token": (str, True, 500), "password": (str, True, 200)})
def accept_invite():
    """Public endpoint: turns a pending invitation into an actual active user
    account and logs them in immediately."""
    data = request.get_json(force=True) or {}
    raw_token = data.get("token")
    password = data.get("password")
    if len(password) < 12:
        return jsonify({"error": "Password must be at least 12 characters"}), 400

    conn = get_db()
    token_hash = _hash_reset_token(raw_token)
    invite = conn.execute("SELECT * FROM invitations WHERE token_hash=?", (token_hash,)).fetchone()
    if not invite or invite["status"] != "pending" or invite["expires_at"] < datetime.utcnow().isoformat():
        conn.close()
        return jsonify({"error": "This invitation link is invalid or has expired"}), 400

    existing_user = conn.execute("SELECT id FROM users WHERE tenant_id=? AND email=?", (invite["tenant_id"], invite["email"])).fetchone()
    if existing_user:
        conn.close()
        return jsonify({"error": "Email already registered in this workspace"}), 409

    cur = conn.execute(
        "INSERT INTO users (tenant_id, name, email, password_hash, role) VALUES (?,?,?,?,?)",
        (invite["tenant_id"], invite["name"] or invite["email"], invite["email"], generate_password_hash(password), invite["role"]),
    )
    user_id = cur.lastrowid
    conn.execute("UPDATE invitations SET status='accepted', accepted_at=datetime('now') WHERE id=?", (invite["id"],))
    conn.commit()
    user = row_to_dict(conn.execute("SELECT id, tenant_id, name, email, role, created_at FROM users WHERE id=?", (user_id,)).fetchone())
    raw_refresh = issue_session(conn, user, request.headers.get("User-Agent"), request.remote_addr)
    conn.close()
    log_action(user_id, "accept_invite", "user", user_id, tenant_id=invite["tenant_id"])
    access_token = create_access_token(user)
    return _session_response({"user": user, "access_token": access_token}, raw_refresh) if _cookie_auth_enabled() else (jsonify({"user": user, "access_token": access_token, "refresh_token": raw_refresh}), 201)


# ---------------- email verification ----------------

EMAIL_VERIFY_EXPIRY_HOURS = 24


def _issue_email_verification_token(conn, tenant_id, user_id):
    conn.execute(
        "UPDATE email_verification_tokens SET used_at=datetime('now') WHERE tenant_id=? AND user_id=? AND used_at IS NULL",
        (tenant_id, user_id),
    )
    raw_token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(hours=EMAIL_VERIFY_EXPIRY_HOURS)).isoformat()
    conn.execute(
        "INSERT INTO email_verification_tokens (tenant_id, user_id, token_hash, expires_at) VALUES (?,?,?,?)",
        (tenant_id, user_id, _hash_reset_token(raw_token), expires_at),
    )
    return raw_token


@auth_bp.route("/resend-verification", methods=["POST"])
@login_required
def resend_verification():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=? AND tenant_id=?", (g.current_user["user_id"], g.current_user["tenant_id"])).fetchone()
    if user["email_verified_at"]:
        conn.close()
        return jsonify({"message": "Email is already verified"}), 200
    raw_token = _issue_email_verification_token(conn, user["tenant_id"], user["id"])
    conn.commit()
    conn.close()
    log_action(user["id"], "resend_email_verification", "user", user["id"])

    from config import PRODUCTION
    result = {"message": "Verification email sent"}
    if not PRODUCTION:
        result["dev_verify_token"] = raw_token
        result["dev_note"] = "Email delivery is not configured; token returned here only because CODELA_ENV != production."
    return jsonify(result), 200


@auth_bp.route("/verify-email", methods=["POST"])
@strict_json({"token": (str, True, 500)})
def verify_email():
    data = request.get_json(force=True) or {}
    raw_token = data.get("token")
    conn = get_db()
    token_hash = _hash_reset_token(raw_token)
    row = conn.execute("SELECT * FROM email_verification_tokens WHERE token_hash=?", (token_hash,)).fetchone()
    if not row or row["used_at"] is not None or row["expires_at"] < datetime.utcnow().isoformat():
        conn.close()
        return jsonify({"error": "This verification link is invalid or has expired"}), 400
    conn.execute("UPDATE email_verification_tokens SET used_at=datetime('now') WHERE id=?", (row["id"],))
    conn.execute("UPDATE users SET email_verified_at=datetime('now') WHERE id=? AND tenant_id=?", (row["user_id"], row["tenant_id"]))
    conn.commit()
    conn.close()
    log_action(row["user_id"], "email_verified", "user", row["user_id"], tenant_id=row["tenant_id"])
    return jsonify({"message": "Email verified"}), 200


# ---------------- API key management ----------------

def _generate_api_key():
    raw = "ck_" + secrets.token_urlsafe(32)
    return raw, raw[:10]  # short prefix shown in listings for identification


@auth_bp.route("/api-keys", methods=["POST"])
@login_required
@roles_required()
def create_api_key():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    expires_in_days = data.get("expires_in_days")
    expires_at = None
    if expires_in_days is not None:
        try:
            expires_at = (datetime.utcnow() + timedelta(days=int(expires_in_days))).isoformat()
        except (TypeError, ValueError):
            return jsonify({"error": "expires_in_days must be an integer"}), 400

    raw_key, prefix = _generate_api_key()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO api_keys (tenant_id, user_id, name, key_prefix, key_hash, expires_at) VALUES (?,?,?,?,?,?)",
        (g.current_user["tenant_id"], g.current_user["user_id"], name, prefix, _hash_api_key(raw_key), expires_at),
    )
    conn.commit()
    key_id = cur.lastrowid
    conn.close()
    log_action(g.current_user["user_id"], "create_api_key", "api_key", key_id, details=name)
    # The raw key is shown exactly once — it is not recoverable after this response.
    return jsonify({"id": key_id, "name": name, "key": raw_key, "key_prefix": prefix, "expires_at": expires_at,
                     "warning": "Store this key now. It will not be shown again."}), 201


@auth_bp.route("/api-keys", methods=["GET"])
@login_required
@roles_required()
def list_api_keys():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, key_prefix, last_used_at, expires_at, revoked_at, created_at FROM api_keys WHERE tenant_id=? ORDER BY created_at DESC",
        (g.current_user["tenant_id"],),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@auth_bp.route("/api-keys/<int:key_id>/revoke", methods=["POST"])
@login_required
@roles_required()
def revoke_api_key(key_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM api_keys WHERE id=? AND tenant_id=?", (key_id, g.current_user["tenant_id"])).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "API key not found"}), 404
    if row["revoked_at"] is not None:
        conn.close()
        return jsonify({"error": "API key is already revoked"}), 409
    conn.execute("UPDATE api_keys SET revoked_at=datetime('now') WHERE id=?", (key_id,))
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "revoke_api_key", "api_key", key_id)
    return jsonify({"message": "API key revoked"}), 200


@auth_bp.route("/api-keys/<int:key_id>/rotate", methods=["POST"])
@login_required
@roles_required()
def rotate_api_key(key_id):
    """Revokes the existing key and issues a brand new secret under the same
    name/expiry policy — the old key stops working immediately."""
    conn = get_db()
    row = conn.execute("SELECT * FROM api_keys WHERE id=? AND tenant_id=?", (key_id, g.current_user["tenant_id"])).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "API key not found"}), 404
    raw_key, prefix = _generate_api_key()
    conn.execute(
        "UPDATE api_keys SET key_hash=?, key_prefix=?, revoked_at=NULL, last_used_at=NULL WHERE id=?",
        (_hash_api_key(raw_key), prefix, key_id),
    )
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "rotate_api_key", "api_key", key_id)
    return jsonify({"id": key_id, "key": raw_key, "key_prefix": prefix,
                     "warning": "Store this key now. It will not be shown again."}), 200


# ---------------- password recovery (forgot / reset) ----------------

RESET_TOKEN_MINUTES = 30
INVITE_EXPIRY_DAYS = 7


def _hash_reset_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def is_reset_rate_limited(conn, ip_address):
    """Max 5 forgot-password requests per IP per 15 minutes, independent of
    which email was targeted — stops an attacker from mass-spamming reset
    emails at arbitrary addresses."""
    if not ip_address:
        return False
    count = conn.execute(
        "SELECT COUNT(*) c FROM login_attempts WHERE ip_address=? AND email LIKE 'password-reset:%' AND created_at >= datetime('now', '-15 minutes')",
        (ip_address,),
    ).fetchone()["c"]
    return count >= 5


def _record_reset_attempt(conn, email, ip_address):
    conn.execute(
        "INSERT INTO login_attempts (email, success, ip_address) VALUES (?,0,?)",
        (f"password-reset:{email}", ip_address),
    )
    conn.commit()


@auth_bp.route("/forgot-password", methods=["POST"])
@strict_json({"email": (str, True, 320)})
def forgot_password():
    """Always responds 200 with the same generic message whether or not the
    email exists, so this endpoint can't be used to enumerate accounts."""
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    generic_message = {"message": "If an account exists for that email, a password reset link has been sent."}

    conn = get_db()
    if is_reset_rate_limited(conn, request.remote_addr):
        conn.close()
        return jsonify({"error": "Too many reset requests. Please try again later."}), 429

    _record_reset_attempt(conn, email, request.remote_addr)
    user = conn.execute("SELECT * FROM users WHERE email=? AND is_active=1", (email,)).fetchone()
    if not user:
        conn.close()
        return jsonify(generic_message), 200

    # Invalidate any earlier unconsumed tokens for this user — only the
    # newest reset link is ever valid.
    conn.execute(
        "UPDATE password_reset_tokens SET used_at=datetime('now') WHERE tenant_id=? AND user_id=? AND used_at IS NULL",
        (user["tenant_id"], user["id"]),
    )
    raw_token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(minutes=RESET_TOKEN_MINUTES)).isoformat()
    conn.execute(
        "INSERT INTO password_reset_tokens (tenant_id, user_id, token_hash, expires_at, requested_ip) VALUES (?,?,?,?,?)",
        (user["tenant_id"], user["id"], _hash_reset_token(raw_token), expires_at, request.remote_addr),
    )
    conn.commit()
    log_action(user["id"], "forgot_password_requested", "user", user["id"], tenant_id=user["tenant_id"])
    conn.close()

    # No email provider is wired up in this codebase yet (see integrations
    # backlog). In production this must be replaced with a real send-email
    # call instead of returning the token in the API response.
    from config import PRODUCTION
    if not PRODUCTION:
        generic_message["dev_reset_token"] = raw_token
        generic_message["dev_note"] = "Email delivery is not configured; token returned here only because CODELA_ENV != production."
    return jsonify(generic_message), 200


@auth_bp.route("/reset-password", methods=["POST"])
@strict_json({"token": (str, True, 500), "password": (str, True, 200)})
def reset_password():
    data = request.get_json(force=True) or {}
    raw_token = data.get("token")
    new_password = data.get("password")
    if len(new_password) < 12:
        return jsonify({"error": "Password must be at least 12 characters"}), 400

    conn = get_db()
    token_hash = _hash_reset_token(raw_token)
    row = conn.execute(
        "SELECT * FROM password_reset_tokens WHERE token_hash=?", (token_hash,)
    ).fetchone()
    if not row or row["used_at"] is not None or row["expires_at"] < datetime.utcnow().isoformat():
        conn.close()
        return jsonify({"error": "This reset link is invalid or has expired"}), 400

    conn.execute("UPDATE password_reset_tokens SET used_at=datetime('now') WHERE id=?", (row["id"],))
    conn.execute(
        "UPDATE users SET password_hash=? WHERE id=? AND tenant_id=?",
        (generate_password_hash(new_password), row["user_id"], row["tenant_id"]),
    )
    # Force re-login everywhere: a password reset must invalidate every
    # existing session, otherwise a stolen device/token would still work
    # after the legitimate owner "secures" their account.
    conn.execute("UPDATE sessions SET is_revoked=1 WHERE user_id=? AND tenant_id=?", (row["user_id"], row["tenant_id"]))
    conn.commit()
    log_action(row["user_id"], "password_reset_completed", "user", row["user_id"], tenant_id=row["tenant_id"])
    conn.close()
    return jsonify({"message": "Password has been reset. Please log in with your new password."}), 200


# ---------------- login (password step, then optional 2FA step) ----------------

@auth_bp.route("/login", methods=["POST"])
@strict_json({"email":(str,True,320),"password":(str,True,200),"tenant_slug":(str,False,120)})
def login():
    data = request.get_json(force=True) or {}
    email = data.get("email")
    password = data.get("password")
    tenant_slug = data.get("tenant_slug")
    if not all([email, password]):
        return jsonify({"error": "email and password are required"}), 400

    conn = get_db()
    if is_login_rate_limited(conn, email, request.remote_addr):
        conn.close()
        return jsonify({"error": "Too many failed attempts. Please try again in 15 minutes.", "code": "locked_out"}), 429

    if tenant_slug:
        user = conn.execute(
            """SELECT u.* FROM users u JOIN tenants t ON t.id = u.tenant_id
               WHERE u.email=? AND t.slug=?""", (email, tenant_slug),
        ).fetchone()
    else:
        matches = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchall()
        if len(matches) > 1:
            conn.close()
            return jsonify({"error": "Multiple workspaces use this email — please specify tenant_slug", "code": "tenant_ambiguous"}), 409
        user = matches[0] if matches else None

    if user is None or not check_password_hash(user["password_hash"], password):
        conn.close()
        record_login_attempt(email, user["tenant_id"] if user else None, False)
        return jsonify({"error": "Invalid credentials"}), 401
    if not user["is_active"]:
        conn.close()
        return jsonify({"error": "Account is disabled"}), 403
    tenant_row = conn.execute("SELECT is_active FROM tenants WHERE id=?", (user["tenant_id"],)).fetchone()
    if tenant_row is None or not tenant_row["is_active"]:
        conn.close()
        return jsonify({"error": "This workspace is suspended. Please contact your administrator or update your billing plan.", "code": "tenant_suspended"}), 403

    if user["totp_enabled"]:
        conn.close()
        # Password verification succeeded; the actual login is recorded only
        # after the 2FA code succeeds. The challenge itself is one-time use.
        conn = get_db()
        pre_auth_token = create_pre_auth_token(conn, user)
        conn.close()
        return jsonify({"requires_2fa": True, "pre_auth_token": pre_auth_token}), 200

    raw_refresh = issue_session(conn, user, request.headers.get("User-Agent"), request.remote_addr)
    conn.close()
    record_login_attempt(email, user["tenant_id"], True)

    user_dict = row_to_dict(user)
    user_dict.pop("password_hash", None)
    user_dict.pop("totp_secret", None)
    conn = get_db()
    user_dict["client_portal"] = is_client_portal_user(conn, user)
    conn.close()
    return _session_response({"user": user_dict, "access_token": create_access_token(user)}, raw_refresh) if _cookie_auth_enabled() else (jsonify({"user": user_dict, "access_token": create_access_token(user), "refresh_token": raw_refresh}), 200)


@auth_bp.route("/2fa/login-verify", methods=["POST"])
def two_fa_login_verify():
    data = request.get_json(force=True) or {}
    pre_auth_token = data.get("pre_auth_token")
    code = data.get("code")
    if not pre_auth_token or not code:
        return jsonify({"error": "pre_auth_token and code are required"}), 400
    try:
        payload = decode_token(pre_auth_token, expected_type="pre_auth")
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "2FA challenge expired, please log in again"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=? AND tenant_id=?", (payload["user_id"], payload["tenant_id"])).fetchone()
    if user is None:
        conn.close()
        return jsonify({"error": "Invalid 2FA code"}), 401

    email = user["email"]
    challenge = conn.execute(
        "SELECT * FROM auth_challenges WHERE jti=? AND user_id=? AND tenant_id=?",
        (payload.get("jti"), user["id"], user["tenant_id"]),
    ).fetchone()
    if challenge is None or challenge["used_at"] is not None or int(challenge["attempts"] or 0) >= PRE_AUTH_MAX_ATTEMPTS:
        conn.close()
        return jsonify({"error": "2FA challenge already used or invalid"}), 401
    try:
        challenge_expired = challenge["expires_at"] < datetime.utcnow().isoformat()
    except TypeError:
        challenge_expired = challenge["expires_at"] < datetime.utcnow()
    if challenge_expired:
        conn.close()
        return jsonify({"error": "2FA challenge expired, please log in again"}), 401

    if is_login_rate_limited(conn, email, request.remote_addr):
        conn.close()
        return jsonify({"error": "Too many failed attempts. Please try again in 15 minutes.", "code": "locked_out"}), 429

    if not user["totp_secret"] or not totp_lib.verify_totp(user["totp_secret"], code):
        conn.execute("UPDATE auth_challenges SET attempts=attempts+1, used_at=CASE WHEN attempts+1>=? THEN datetime('now') ELSE used_at END WHERE jti=? AND used_at IS NULL", (PRE_AUTH_MAX_ATTEMPTS, payload["jti"]))
        conn.commit(); conn.close()
        record_login_attempt(email, user["tenant_id"], False)
        return jsonify({"error": "Invalid 2FA code"}), 401

    conn.execute("UPDATE auth_challenges SET used_at=datetime('now') WHERE jti=? AND used_at IS NULL", (payload["jti"],))
    conn.commit()
    raw_refresh = issue_session(conn, user, request.headers.get("User-Agent"), request.remote_addr)
    record_login_attempt(email, user["tenant_id"], True)
    user_dict = row_to_dict(user)
    user_dict.pop("password_hash", None)
    user_dict.pop("totp_secret", None)
    user_dict["client_portal"] = is_client_portal_user(conn, user)
    conn.close()
    return _session_response({"user": user_dict, "access_token": create_access_token(user)}, raw_refresh) if _cookie_auth_enabled() else (jsonify({"user": user_dict, "access_token": create_access_token(user), "refresh_token": raw_refresh}), 200)


# ---------------- 2FA setup/disable (requires being logged in already) ----------------

@auth_bp.route("/2fa/setup", methods=["POST"])
@login_required
@strict_json({"password":(str,True,200), "code":(str,False,6)})
def two_fa_setup():
    # Changing an MFA secret is a sensitive account-security action. Require
    # the current password, and when MFA is already enabled also require the
    # current TOTP code so a stolen access token alone cannot replace MFA.
    data = request.get_json(force=True) or {}
    password = data.get("password")
    code = (data.get("code") or "").strip()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=? AND tenant_id=?", (g.current_user["user_id"], g.current_user["tenant_id"])).fetchone()
    if user is None or not user["is_active"]:
        conn.close(); return jsonify({"error":"Account not found or disabled"}), 404
    if not check_password_hash(user["password_hash"], password):
        conn.close(); return jsonify({"error":"Invalid credentials"}), 401
    if user["totp_enabled"]:
        if not code or not user["totp_secret"] or not totp_lib.verify_totp(user["totp_secret"], code):
            conn.close(); return jsonify({"error":"Current 2FA code is required"}), 401
    secret = totp_lib.generate_secret()
    pending_until = (datetime.utcnow() + timedelta(minutes=10)).isoformat(timespec='seconds')
    conn.execute("UPDATE users SET totp_pending_secret=?, totp_pending_expires_at=?, totp_pending_attempts=0 WHERE id=? AND tenant_id=?", (secret, pending_until, user["id"], user["tenant_id"]))
    conn.commit(); conn.close()
    uri = totp_lib.provisioning_uri(secret, user["email"])
    log_action(user["id"], "start_2fa_setup", "user", user["id"])
    return jsonify({"secret": secret, "provisioning_uri": uri,
                     "note": "Scan provisioning_uri as a QR code in your authenticator app, then confirm with /auth/2fa/confirm"})


@auth_bp.route("/2fa/confirm", methods=["POST"])
@login_required
def two_fa_confirm():
    data = request.get_json(force=True) or {}
    code = data.get("code")
    conn = get_db()
    if hasattr(conn, "_conn"):
        conn._conn.cursor().execute("BEGIN")
        cur = conn._conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=%s AND tenant_id=%s FOR UPDATE", (g.current_user["user_id"], g.current_user["tenant_id"]))
        user = cur.fetchone()
    else:
        conn.execute("BEGIN IMMEDIATE")
        user = conn.execute("SELECT * FROM users WHERE id=? AND tenant_id=?", (g.current_user["user_id"], g.current_user["tenant_id"])).fetchone()
    pending_secret = user["totp_pending_secret"] if user else None
    pending_attempts = int(user["totp_pending_attempts"] or 0) if user else 0
    if user is None or not pending_secret or not user["totp_pending_expires_at"]:
        conn.close()
        return jsonify({"error": "No active 2FA setup"}), 400
    try:
        expired = datetime.fromisoformat(str(user["totp_pending_expires_at"])) <= datetime.utcnow()
    except ValueError:
        expired = True
    if expired:
        conn.execute("UPDATE users SET totp_pending_secret=NULL, totp_pending_expires_at=NULL, totp_pending_attempts=0 WHERE id=? AND tenant_id=?", (user["id"], user["tenant_id"]))
        conn.commit(); conn.close()
        return jsonify({"error": "2FA setup expired. Start setup again."}), 400
    if pending_attempts >= 5:
        conn.close()
        return jsonify({"error": "Too many 2FA setup attempts. Start setup again."}), 429
    if not isinstance(code, str) or not code.isdigit() or len(code) != 6 or not totp_lib.verify_totp(pending_secret, code):
        next_attempts = pending_attempts + 1
        if next_attempts >= 5:
            conn.execute("UPDATE users SET totp_pending_secret=NULL, totp_pending_expires_at=NULL, totp_pending_attempts=? WHERE id=? AND tenant_id=?", (next_attempts, user["id"], user["tenant_id"]))
        else:
            conn.execute("UPDATE users SET totp_pending_attempts=? WHERE id=? AND tenant_id=?", (next_attempts, user["id"], user["tenant_id"]))
        conn.commit(); conn.close()
        return jsonify({"error": "Invalid code — 2FA not enabled"}), 400
    conn.execute("UPDATE users SET totp_secret=?, totp_enabled=1, totp_pending_secret=NULL, totp_pending_expires_at=NULL, totp_pending_attempts=0 WHERE id=? AND tenant_id=?", (pending_secret, user["id"], user["tenant_id"]))
    conn.commit()
    conn.close()
    log_action(user["id"], "enable_2fa", "user", user["id"])
    return jsonify({"message": "2FA enabled"})


@auth_bp.route("/2fa/disable", methods=["POST"])
@login_required
def two_fa_disable():
    data = request.get_json(force=True) or {}
    password = data.get("password")
    code = data.get("code")
    if not password or not code:
        return jsonify({"error": "password and current 2FA code are required"}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (g.current_user["user_id"],)).fetchone()
    if user is None or not user["is_active"]:
        conn.close()
        return jsonify({"error": "Account not found or disabled"}), 404
    if not check_password_hash(user["password_hash"], password):
        conn.close()
        return jsonify({"error": "Invalid credentials"}), 401
    if not user["totp_enabled"] or not user["totp_secret"] or not totp_lib.verify_totp(user["totp_secret"], code):
        conn.close()
        return jsonify({"error": "Invalid 2FA code"}), 401

    conn.execute("UPDATE users SET totp_enabled=0, totp_secret=NULL, totp_pending_secret=NULL, totp_pending_expires_at=NULL, totp_pending_attempts=0 WHERE id=? AND tenant_id=?", (user["id"], user["tenant_id"]))
    conn.commit()
    conn.close()
    log_action(user["id"], "disable_2fa", "user", user["id"])
    return jsonify({"message": "2FA disabled"})


# ---------------- refresh / logout / session management ----------------

@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True) or {}
    raw_token = request.cookies.get("codela_refresh") if _cookie_auth_enabled() else data.get("refresh_token")
    if not raw_token:
        return jsonify({"error": "refresh_token is required"}), 400

    conn = get_db()
    token_hash = hash_refresh_token(raw_token)
    session = conn.execute(
        "SELECT * FROM sessions WHERE refresh_token_hash=? AND is_revoked=0", (token_hash,)
    ).fetchone()
    if session is None or session["expires_at"] < datetime.utcnow().isoformat():
        conn.close()
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    user = conn.execute("SELECT * FROM users WHERE id=? AND tenant_id=?", (session["user_id"],session["tenant_id"])).fetchone()
    if user is None or not user["is_active"]:
        conn.close()
        return jsonify({"error": "Account is disabled or missing"}), 401

    # Refresh-token rotation: the presented token is single-use. Reusing an
    # already-revoked token therefore fails instead of extending its lifetime.
    conn.execute("UPDATE sessions SET is_revoked=1, last_used_at=datetime('now') WHERE id=?", (session["id"],))
    new_refresh = issue_session(conn, user, request.headers.get("User-Agent"), request.remote_addr)
    conn.close()
    return _session_response({"access_token": create_access_token(user)}, new_refresh) if _cookie_auth_enabled() else jsonify({"access_token": create_access_token(user), "refresh_token": new_refresh})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
 data=request.get_json(silent=True) or {};c=get_db(); raw_refresh=request.cookies.get("codela_refresh") if _cookie_auth_enabled() else data.get("refresh_token")
 if raw_refresh:c.execute("UPDATE sessions SET is_revoked=1 WHERE refresh_token_hash=? AND user_id=? AND tenant_id=?",(hash_refresh_token(raw_refresh),g.current_user["user_id"],g.current_user["tenant_id"]))
 c.execute("INSERT INTO access_token_revocations (jti,user_id,tenant_id,expires_at) VALUES (?,?,?,?) ON CONFLICT(jti) DO UPDATE SET expires_at=excluded.expires_at",(g.current_user.get("jti"),g.current_user["user_id"],g.current_user["tenant_id"],datetime.utcfromtimestamp(g.current_user["exp"]).isoformat()));c.commit();c.close();log_action(g.current_user["user_id"],"logout","session",details={"refresh_token":"[REDACTED]"});return _clear_refresh_cookie(jsonify({"message":"Logged out"}))


@auth_bp.route("/logout-all", methods=["POST"])
@login_required
def logout_all():
    conn = get_db()
    conn.execute("UPDATE sessions SET is_revoked=1 WHERE user_id=? AND tenant_id=?", (g.current_user["user_id"],g.current_user["tenant_id"]))
    conn.commit()
    conn.close()
    log_action(g.current_user["user_id"], "logout_all_sessions", "user", g.current_user["user_id"])
    return jsonify({"message": "All sessions revoked"})


@auth_bp.route("/sessions", methods=["GET"])
@login_required
def list_sessions():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_agent, ip_address, created_at, last_used_at, expires_at, is_revoked FROM sessions WHERE user_id=? AND tenant_id=? ORDER BY last_used_at DESC",
        (g.current_user["user_id"],g.current_user["tenant_id"]),
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@auth_bp.route("/sessions/<int:session_id>/revoke", methods=["POST"])
@login_required
def revoke_session(session_id):
    conn = get_db()
    conn.execute("UPDATE sessions SET is_revoked=1 WHERE id=? AND user_id=? AND tenant_id=?", (session_id,g.current_user["user_id"],g.current_user["tenant_id"]))
    conn.commit()
    conn.close()
    return jsonify({"message": "Session revoked"})


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    conn = get_db()
    user = conn.execute(
        "SELECT id, tenant_id, name, email, role, department, is_active, totp_enabled, email_verified_at, created_at FROM users WHERE id=?",
        (g.current_user["user_id"],),
    ).fetchone()
    tenant = conn.execute("SELECT id, name, slug, plan FROM tenants WHERE id=?", (g.current_user["tenant_id"],)).fetchone()
    client_portal = is_client_portal_user(conn, user) if user else False
    conn.close()
    if user is None:
        return jsonify({"error": "User not found"}), 404
    result = row_to_dict(user)
    result["tenant"] = row_to_dict(tenant)
    result["client_portal"] = client_portal
    return jsonify(result)
