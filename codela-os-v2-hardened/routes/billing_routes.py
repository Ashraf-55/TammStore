"""
SaaS Subscription Engine — Codela OS

Plans (trial/starter/pro/enterprise) with real usage limits (max_users,
max_leads, max_storage_mb) enforced via `check_usage_limit()` — called from
auth.py (/auth/invite) and routes/crm_routes.py (create_lead) to return
HTTP 402 once a tenant is over its plan's quota.

Every new tenant gets a 14-day trial subscription automatically via
`create_trial_subscription()`, called from auth.py's /auth/register.

Same mock/live adapter pattern as routes/communication_routes.py and
routes/publish_routes.py: `PaymentGatewayAdapter.charge()` runs in mock mode
until a real payment provider credential is configured via env var, and
fails closed (never silently pretends to succeed) in production without one.

To go live: wire the real HTTP call into `PaymentGatewayAdapter._charge_live()`.
# TODO live: plug in Stripe/Paddle/PayTabs (or similar) charge call here.
"""
import json
import os
import time
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from database import get_db, row_to_dict, rows_to_list, pagination_params
from auth import login_required, roles_required, log_action

billing_bp = Blueprint("billing", __name__)


# ---------------- payment gateway adapter (mock/live) ----------------

class PaymentGatewayAdapter:
    env_var = "PAYMENT_GATEWAY_API_KEY"

    def __init__(self):
        self.credential = os.environ.get(self.env_var)

    def charge(self, tenant_id, amount, description):
        """Returns (success: bool, external_id: str|None, error: str|None, mode: 'mock'|'live')"""
        if self.credential:
            return self._charge_live(tenant_id, amount, description)
        if os.getenv("CODELA_ENV") == "production":
            return False, None, "Live payment gateway credentials are required in production", "unconfigured"
        return self._charge_mock(tenant_id, amount, description)

    def _charge_mock(self, tenant_id, amount, description):
        time.sleep(0.02)
        return True, f"pg_mock_{uuid.uuid4().hex[:12]}", None, "mock"

    def _charge_live(self, tenant_id, amount, description):
        # TODO live: implement the real provider call using self.credential.
        return False, None, "Live charging not yet implemented", "live"


# ---------------- helpers ----------------

def _plan_row_by_code(conn, code):
    return conn.execute("SELECT * FROM plans WHERE code=? AND is_active=1", (code,)).fetchone()


def _current_subscription(conn, tenant_id):
    return conn.execute(
        """SELECT s.*, p.code AS plan_code, p.name AS plan_name, p.price_monthly, p.price_yearly,
                  p.max_users, p.max_leads, p.max_storage_mb, p.features
           FROM subscriptions s JOIN plans p ON p.id = s.plan_id
           WHERE s.tenant_id=?""",
        (tenant_id,),
    ).fetchone()


def usage_for_tenant(conn, tenant_id):
    users_used = conn.execute("SELECT COUNT(*) c FROM users WHERE tenant_id=? AND is_active=1", (tenant_id,)).fetchone()["c"]
    leads_used = conn.execute("SELECT COUNT(*) c FROM leads WHERE tenant_id=?", (tenant_id,)).fetchone()["c"]
    storage_bytes = conn.execute("SELECT COALESCE(SUM(size_bytes),0) c FROM files WHERE tenant_id=?", (tenant_id,)).fetchone()["c"]
    return {"users": users_used, "leads": leads_used, "storage_mb": round((storage_bytes or 0) / (1024 * 1024), 2)}


def check_usage_limit(conn, tenant_id, resource):
    """resource is one of 'users', 'leads', 'storage_mb'. Returns (allowed, used, limit).
    Fails open (allowed=True) only if the tenant has no subscription row at all,
    since that indicates a provisioning bug rather than a real quota state —
    every tenant is expected to have one via create_trial_subscription()."""
    sub = _current_subscription(conn, tenant_id)
    if sub is None:
        return True, 0, None
    usage = usage_for_tenant(conn, tenant_id)
    limit_col = {"users": "max_users", "leads": "max_leads", "storage_mb": "max_storage_mb"}[resource]
    limit = sub[limit_col]
    used = usage[resource]
    return used < limit, used, limit


def create_trial_subscription(conn, tenant_id):
    """Attaches a 14-day trial subscription to a brand-new tenant. Caller owns
    the transaction (does not commit) so it composes with the rest of
    /auth/register's insert sequence."""
    plan = _plan_row_by_code(conn, "trial")
    if plan is None:
        # Reference data missing (should not happen — migration 12 seeds it).
        # Fail loudly rather than leaving the tenant without any subscription,
        # which would silently deny all lead/user creation via check_usage_limit.
        raise RuntimeError("Trial plan is not configured — the 'plans' reference table is empty")
    trial_ends_at = (datetime.utcnow() + timedelta(days=14)).isoformat()
    conn.execute(
        """INSERT INTO subscriptions (tenant_id, plan_id, status, billing_cycle, current_period_start,
                                       current_period_end, trial_ends_at)
           VALUES (?,?,'trialing','monthly',datetime('now'),?,?)""",
        (tenant_id, plan["id"], trial_ends_at, trial_ends_at),
    )


def _suspend_tenant(conn, tenant_id):
    conn.execute("UPDATE tenants SET is_active=0 WHERE id=?", (tenant_id,))


def _serialize_subscription(sub, usage):
    features = sub["features"]
    if isinstance(features, str):
        try:
            features = json.loads(features)
        except (TypeError, ValueError):
            features = []
    return {
        "plan_code": sub["plan_code"],
        "plan_name": sub["plan_name"],
        "status": sub["status"],
        "billing_cycle": sub["billing_cycle"],
        "current_period_start": sub["current_period_start"],
        "current_period_end": sub["current_period_end"],
        "trial_ends_at": sub["trial_ends_at"],
        "canceled_at": sub["canceled_at"],
        "price_monthly": sub["price_monthly"],
        "price_yearly": sub["price_yearly"],
        "features": features,
        "limits": {"max_users": sub["max_users"], "max_leads": sub["max_leads"], "max_storage_mb": sub["max_storage_mb"]},
        "usage": usage,
    }


# ---------------- routes ----------------

@billing_bp.route("/billing/plans", methods=["GET"])
def list_plans():
    """Public plan catalog — no auth required so a pricing page can call it."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM plans WHERE is_active=1 ORDER BY price_monthly ASC").fetchall()
    conn.close()
    plans = []
    for row in rows:
        plan = row_to_dict(row)
        if isinstance(plan.get("features"), str):
            try:
                plan["features"] = json.loads(plan["features"])
            except (TypeError, ValueError):
                plan["features"] = []
        plans.append(plan)
    return jsonify(plans)


@billing_bp.route("/billing/subscription", methods=["GET"])
@login_required
def get_subscription():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    sub = _current_subscription(conn, tenant_id)
    if sub is None:
        conn.close()
        return jsonify({"error": "No subscription found for this workspace"}), 404
    usage = usage_for_tenant(conn, tenant_id)
    conn.close()
    return jsonify(_serialize_subscription(sub, usage))


@billing_bp.route("/billing/subscribe", methods=["POST"])
@login_required
@roles_required()
def subscribe():
    """Upgrade/downgrade/(re)activate the caller's tenant onto a plan.
    founder/admin only. Requires idempotency_key in production so a retried
    request (e.g. after a flaky connection) can't double-charge."""
    data = request.get_json(force=True) or {}
    plan_code = data.get("plan_code")
    billing_cycle = data.get("billing_cycle", "monthly")
    idempotency_key = data.get("idempotency_key")

    if not plan_code:
        return jsonify({"error": "plan_code is required"}), 400
    if billing_cycle not in ("monthly", "yearly"):
        return jsonify({"error": "billing_cycle must be 'monthly' or 'yearly'"}), 400
    if os.getenv("CODELA_ENV") == "production" and not idempotency_key:
        return jsonify({"error": "idempotency_key is required in production", "code": "idempotency_key_required"}), 400

    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    plan = _plan_row_by_code(conn, plan_code)
    if plan is None:
        conn.close()
        return jsonify({"error": f"Unknown or inactive plan: {plan_code}"}), 400

    if idempotency_key:
        existing = conn.execute(
            "SELECT * FROM subscription_invoices WHERE tenant_id=? AND idempotency_key=?",
            (tenant_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            sub = _current_subscription(conn, tenant_id)
            usage = usage_for_tenant(conn, tenant_id)
            conn.close()
            return jsonify(_serialize_subscription(sub, usage))

    amount = plan["price_monthly"] if billing_cycle == "monthly" else plan["price_yearly"]
    period_days = 30 if billing_cycle == "monthly" else 365
    period_end = (datetime.utcnow() + timedelta(days=period_days)).isoformat()

    gateway = PaymentGatewayAdapter()
    charged, external_id, error, mode = (True, None, None, "mock") if amount == 0 else gateway.charge(
        tenant_id, amount, f"{plan['name']} plan ({billing_cycle})"
    )
    if not charged:
        conn.close()
        return jsonify({"error": error or "Payment failed", "code": "payment_failed"}), 402

    existing_sub = conn.execute("SELECT id FROM subscriptions WHERE tenant_id=?", (tenant_id,)).fetchone()
    if existing_sub:
        conn.execute(
            """UPDATE subscriptions SET plan_id=?, status='active', billing_cycle=?,
                       current_period_start=datetime('now'), current_period_end=?,
                       canceled_at=NULL
               WHERE tenant_id=?""",
            (plan["id"], billing_cycle, period_end, tenant_id),
        )
    else:
        conn.execute(
            """INSERT INTO subscriptions (tenant_id, plan_id, status, billing_cycle,
                                           current_period_start, current_period_end)
               VALUES (?,?,'active',?,datetime('now'),?)""",
            (tenant_id, plan["id"], billing_cycle, period_end),
        )

    sub_row = conn.execute("SELECT id FROM subscriptions WHERE tenant_id=?", (tenant_id,)).fetchone()
    conn.execute(
        """INSERT INTO subscription_invoices (tenant_id, subscription_id, amount, status,
                                                period_start, period_end, paid_at, mode, idempotency_key)
           VALUES (?,?,?,'paid',datetime('now'),?,datetime('now'),?,?)""",
        (tenant_id, sub_row["id"], amount, period_end, mode, idempotency_key),
    )
    conn.execute("UPDATE tenants SET plan=?, is_active=1 WHERE id=?", (plan_code, tenant_id))
    conn.commit()

    sub = _current_subscription(conn, tenant_id)
    usage = usage_for_tenant(conn, tenant_id)
    conn.close()
    log_action(g.current_user["user_id"], "subscribe", "subscription", details=f"plan={plan_code} cycle={billing_cycle}")
    return jsonify(_serialize_subscription(sub, usage)), 200


@billing_bp.route("/billing/cancel", methods=["POST"])
@login_required
@roles_required()
def cancel_subscription():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    sub = conn.execute("SELECT id FROM subscriptions WHERE tenant_id=?", (tenant_id,)).fetchone()
    if sub is None:
        conn.close()
        return jsonify({"error": "No subscription found for this workspace"}), 404
    conn.execute(
        "UPDATE subscriptions SET status='canceled', canceled_at=datetime('now') WHERE tenant_id=?",
        (tenant_id,),
    )
    conn.commit()
    sub = _current_subscription(conn, tenant_id)
    usage = usage_for_tenant(conn, tenant_id)
    conn.close()
    log_action(g.current_user["user_id"], "cancel_subscription", "subscription")
    return jsonify(_serialize_subscription(sub, usage))


@billing_bp.route("/billing/invoices", methods=["GET"])
@login_required
def list_billing_invoices():
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    limit, offset = pagination_params(request)
    rows = conn.execute(
        "SELECT * FROM subscription_invoices WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (tenant_id, limit, offset)
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@billing_bp.route("/billing/check-trials", methods=["POST"])
@login_required
def check_trials():
    """Expires the caller's tenant out of 'trialing' status once trial_ends_at
    has passed, suspending the tenant so it stops accepting further logins
    (see auth.login_required's tenant-active check) until it subscribes.
    Intended to also be safe to call from an external scheduler with any
    tenant's token — it only ever touches the caller's own tenant."""
    tenant_id = g.current_user["tenant_id"]
    conn = get_db()
    sub = conn.execute(
        "SELECT * FROM subscriptions WHERE tenant_id=? AND status='trialing'", (tenant_id,)
    ).fetchone()
    expired = False
    if sub is not None and sub["trial_ends_at"] and sub["trial_ends_at"] < datetime.utcnow().isoformat():
        conn.execute("UPDATE subscriptions SET status='past_due' WHERE id=?", (sub["id"],))
        _suspend_tenant(conn, tenant_id)
        conn.commit()
        expired = True
        log_action(g.current_user["user_id"], "trial_expired", "subscription", entity_id=sub["id"])
    conn.close()
    return jsonify({"checked": True, "trial_expired": expired})
