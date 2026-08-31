"""
Automation Engine — Codela OS

The "brain" of the OS: a generic TRIGGER -> CONDITION -> ACTION engine that
other modules call into instead of hard-coding one-off side effects.

Usage from any route module:

    from automation import fire_event
    fire_event("lead.created", tenant_id, {"lead": lead_dict})

fire_event() loads every active automation_rule for that tenant + event,
evaluates its conditions (a JSON list of {field, op, value} matched against
the flattened context) and — if they all pass — runs its actions (a JSON
list of {type, ...params}) in order. Every run (matched or not, succeeded or
failed) is written to automation_runs for observability.

Supported trigger_event values emitted elsewhere in the codebase:
  lead.created, lead.assigned, deal.won, deal.lost, task.overdue,
  followup.overdue, request.created, attendance.flagged

Supported action types (see ACTION_HANDLERS below):
  assign_user, send_notification, create_followup, create_task,
  send_message, update_lead_status, create_finance_transaction

Conditions operate on a dotted path into the context dict, e.g.
  {"field": "lead.score", "op": ">=", "value": 70}
  {"field": "lead.source", "op": "in", "value": ["referral", "website"]}

This module intentionally has no network calls and no side effects beyond
this tenant's own DB rows — every action is something the rest of the app
already does directly, just reachable generically now.
"""
import json
import threading
from datetime import datetime, timedelta
from database import get_db, row_to_dict

# ---------------------------------------------------------------------------
# Automation loop protection
#
# No current action handler calls fire_event() itself, so there is no active
# infinite-loop bug today. But nothing structural stops the next handler
# anyone adds (e.g. a future "fire_custom_event" action type) from doing
# Event A -> rule -> Event B -> rule -> Event A forever. This caps the
# cascade depth so that scenario fails safely (skipped + logged) instead of
# recursing without limit.
# ---------------------------------------------------------------------------
MAX_AUTOMATION_CASCADE_DEPTH = 5
_cascade_depth = threading.local()


def _current_cascade_depth():
    return getattr(_cascade_depth, "value", 0)


def _get_path(context, dotted_path):
    """Resolve 'lead.score' against {'lead': {'score': 70}} -> 70. Missing -> None."""
    value = context
    for part in dotted_path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    "in": lambda a, b: a in (b or []),
    "not_in": lambda a, b: a not in (b or []),
    "contains": lambda a, b: b is not None and str(b) in str(a or ""),
    "is_empty": lambda a, b: a in (None, "", 0),
    "is_not_empty": lambda a, b: a not in (None, "", 0),
}


def _evaluate_conditions(conditions, context):
    """AND semantics: every condition in the list must pass. Empty list -> always match."""
    for cond in conditions:
        field = cond.get("field")
        op = cond.get("op", "==")
        expected = cond.get("value")
        actual = _get_path(context, field) if field else None
        fn = _OPS.get(op)
        if fn is None or not fn(actual, expected):
            return False
    return True


# ---------------- action handlers ----------------
# Each handler receives (conn, tenant_id, action, context) and may raise on failure.
# It should NOT commit/close conn — the engine manages the transaction per rule.

def _action_assign_user(conn, tenant_id, action, context):
    """Assign a lead to a user. params: user_id (or 'round_robin' role-based via role param)."""
    lead_id = _get_path(context, "lead.id")
    if not lead_id:
        raise ValueError("assign_user requires a lead in context")
    user_id = action.get("user_id")
    if not user_id and action.get("role"):
        # naive round robin: least-loaded active user with that role
        row = conn.execute(
            """SELECT u.id FROM users u
               LEFT JOIN leads l ON l.assigned_sales_id = u.id AND l.tenant_id = u.tenant_id AND l.status NOT IN ('won','lost')
               WHERE u.tenant_id=? AND u.role=? AND u.is_active=1
               GROUP BY u.id ORDER BY COUNT(l.id) ASC LIMIT 1""",
            (tenant_id, action["role"]),
        ).fetchone()
        user_id = row["id"] if row else None
    if not user_id:
        raise ValueError("assign_user: no user_id resolved")
    conn.execute("UPDATE leads SET assigned_sales_id=?, updated_at=datetime('now') WHERE id=? AND tenant_id=?",
                 (user_id, lead_id, tenant_id))
    return f"assigned lead #{lead_id} to user #{user_id}"


def _action_send_notification(conn, tenant_id, action, context):
    user_id = action.get("user_id") or _get_path(context, "lead.assigned_sales_id")
    if not user_id:
        raise ValueError("send_notification: no user_id resolved")
    message = (action.get("message") or "Automation notification").format(**_safe_flatten(context))
    link = action.get("link", "")
    conn.execute(
        "INSERT INTO notifications (tenant_id, user_id, type, message, link) VALUES (?,?,?,?,?)",
        (tenant_id, user_id, action.get("notification_type", "automation"), message, link),
    )
    return f"notified user #{user_id}"


def _action_create_followup(conn, tenant_id, action, context):
    lead_id = _get_path(context, "lead.id")
    if not lead_id:
        raise ValueError("create_followup requires a lead in context")
    delay_hours = int(action.get("delay_hours", 24))
    due_at = (datetime.utcnow() + timedelta(hours=delay_hours)).isoformat(timespec="seconds")
    assigned_to = action.get("assigned_to") or _get_path(context, "lead.assigned_sales_id")
    cur = conn.execute(
        """INSERT INTO followups (tenant_id, lead_id, assigned_to, channel, title, message, due_at, status)
           VALUES (?,?,?,?,?,?,?, 'pending')""",
        (tenant_id, lead_id, assigned_to, action.get("channel", "whatsapp"),
         action.get("title", "Follow up"), action.get("message"), due_at),
    )
    return f"created followup #{cur.lastrowid} for lead #{lead_id}"


def _action_create_task(conn, tenant_id, action, context):
    project_id = action.get("project_id")
    if not project_id:
        row = conn.execute("SELECT id FROM projects WHERE tenant_id=? AND name='Automation Tasks'", (tenant_id,)).fetchone()
        if row:
            project_id = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO projects (tenant_id, name, description, status) VALUES (?, 'Automation Tasks', 'Auto-created by the Automation Engine', 'active')",
                (tenant_id,),
            )
            project_id = cur.lastrowid
    title = (action.get("title") or "Automated task").format(**_safe_flatten(context))
    cur = conn.execute(
        "INSERT INTO tasks (tenant_id, project_id, title, description, assignee_id, priority, status) VALUES (?,?,?,?,?,?, 'todo')",
        (tenant_id, project_id, title, action.get("description"), action.get("assignee_id"), action.get("priority", "medium")),
    )
    return f"created task #{cur.lastrowid}"


def _action_send_message(conn, tenant_id, action, context):
    if action.get("async"):
        from jobs import enqueue
        lead_id=_get_path(context,"lead.id"); to_address=action.get("to") or _get_path(context,"lead.whatsapp") or _get_path(context,"lead.phone") or _get_path(context,"lead.email"); body=(action.get("body") or "").format(**_safe_flatten(context)); jid=enqueue("communication.send",{"channel":action.get("channel","whatsapp"),"to":to_address,"subject":action.get("subject"),"body":body,"lead_id":lead_id},tenant_id,idempotency_key=action.get("idempotency_key")); return f"message queued as job #{jid}"
    # Deferred import avoids a circular import (communication imports nothing from automation).
    from routes.communication_routes import send_via_adapter
    lead_id = _get_path(context, "lead.id")
    to_address = action.get("to") or _get_path(context, "lead.whatsapp") or _get_path(context, "lead.phone") or _get_path(context, "lead.email")
    body = (action.get("body") or "").format(**_safe_flatten(context))
    channel = action.get("channel", "whatsapp")
    result = send_via_adapter(conn, tenant_id, channel=channel, to_address=to_address, subject=action.get("subject"),
                               body=body, lead_id=lead_id, client_id=None, user_id=None)
    return f"message {result['status']} via {channel} ({result['mode']})"


def _action_update_lead_status(conn, tenant_id, action, context):
    lead_id = _get_path(context, "lead.id")
    if not lead_id:
        raise ValueError("update_lead_status requires a lead in context")
    conn.execute("UPDATE leads SET status=?, updated_at=datetime('now') WHERE id=? AND tenant_id=?",
                 (action.get("status"), lead_id, tenant_id))
    return f"lead #{lead_id} -> {action.get('status')}"


def _action_create_finance_transaction(conn, tenant_id, action, context):
    amount = action.get("amount")
    if amount is None:
        amount = _get_path(context, "deal.value") or 0
    conn.execute(
        "INSERT INTO finance_transactions (tenant_id, type, category, amount, description, client_id, date) VALUES (?,?,?,?,?,?,date('now'))",
        (tenant_id, action.get("tx_type", "income"), action.get("category", "automation"), amount,
         action.get("description", "Created by Automation Engine"), _get_path(context, "deal.client_id")),
    )
    return f"finance transaction created: {amount}"


ACTION_HANDLERS = {
    "assign_user": _action_assign_user,
    "send_notification": _action_send_notification,
    "create_followup": _action_create_followup,
    "create_task": _action_create_task,
    "send_message": _action_send_message,
    "update_lead_status": _action_update_lead_status,
    "create_finance_transaction": _action_create_finance_transaction,
}


def _safe_flatten(context, prefix=""):
    """Flattens {'lead': {'name': 'X'}} -> {'lead.name': 'X', 'lead_name': 'X', ...}
    so {lead_name} style .format() placeholders work in message/title templates."""
    flat = {}
    for k, v in (context or {}).items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            flat.update(_safe_flatten(v, prefix=f"{key}_"))
        else:
            flat[key] = v
    return flat


def fire_event_sync(event_name, tenant_id, context=None, conn=None):
    """Entry point every module calls. Safe to call even if no rules match —
    it's then just a no-op (aside from an empty scan of automation_rules).
    Never raises: a broken rule shouldn't break the request that triggered it."""
    context = context or {}
    owns_conn = conn is None
    conn = conn or get_db()

    depth = _current_cascade_depth()
    if depth >= MAX_AUTOMATION_CASCADE_DEPTH:
        # An action handler somewhere is (directly or indirectly) re-firing
        # events in a cycle. Stop here, log it for visibility, and don't
        # execute any rules for this call.
        try:
            conn.execute(
                "INSERT INTO automation_runs (tenant_id, rule_id, trigger_event, entity_type, entity_id, status, result) VALUES (?,?,?,?,?,'skipped',?)",
                (tenant_id, None, event_name, None, None, f"max automation cascade depth ({MAX_AUTOMATION_CASCADE_DEPTH}) exceeded — likely an event loop"),
            )
            conn.commit()
        except Exception:
            pass
        finally:
            if owns_conn:
                conn.close()
        return

    _cascade_depth.value = depth + 1
    try:
        rules = conn.execute(
            "SELECT * FROM automation_rules WHERE tenant_id=? AND trigger_event=? AND is_active=1",
            (tenant_id, event_name),
        ).fetchall()
        for rule in rules:
            rule = row_to_dict(rule)
            try:
                conditions = json.loads(rule["conditions"] or "[]")
                actions = json.loads(rule["actions"] or "[]")
            except (TypeError, ValueError):
                conditions, actions = [], []

            entity_type = list(context.keys())[0] if context else None
            entity_id = _get_path(context, f"{entity_type}.id") if entity_type else None

            if not _evaluate_conditions(conditions, context):
                conn.execute(
                    "INSERT INTO automation_runs (tenant_id, rule_id, trigger_event, entity_type, entity_id, status, result) VALUES (?,?,?,?,?,'skipped','conditions not met')",
                    (tenant_id, rule["id"], event_name, entity_type, entity_id),
                )
                continue

            results = []
            try:
                for action in actions:
                    handler = ACTION_HANDLERS.get(action.get("type"))
                    if handler is None:
                        results.append(f"unknown action type: {action.get('type')}")
                        continue
                    results.append(handler(conn, tenant_id, action, context))
                conn.execute("UPDATE automation_rules SET run_count = run_count + 1 WHERE id=?", (rule["id"],))
                conn.execute(
                    "INSERT INTO automation_runs (tenant_id, rule_id, trigger_event, entity_type, entity_id, status, result) VALUES (?,?,?,?,?,'success',?)",
                    (tenant_id, rule["id"], event_name, entity_type, entity_id, "; ".join(results)),
                )
            except Exception as exc:  # noqa: BLE001 — one bad rule must not break the request
                conn.execute(
                    "INSERT INTO automation_runs (tenant_id, rule_id, trigger_event, entity_type, entity_id, status, result) VALUES (?,?,?,?,?,'failed',?)",
                    (tenant_id, rule["id"], event_name, entity_type, entity_id, str(exc)),
                )
        conn.commit()
    except Exception:  # noqa: BLE001 — automation must never take down the caller
        try:
            conn.commit()
        except Exception:
            pass
    finally:
        if owns_conn:
            conn.close()
        _cascade_depth.value = depth


def fire_event(event_name, tenant_id, context=None, conn=None):
    """Queue automation in production/async mode; keep synchronous behavior for local development/tests."""
    import os
    if conn is None and os.getenv("CODELA_AUTOMATION_ASYNC", "1" if os.getenv("CODELA_ENV") == "production" else "0") == "1":
        from jobs import enqueue_job
        return enqueue_job("automation.fire_event", {"event_name": event_name, "tenant_id": tenant_id, "context": context or {}}, tenant_id=tenant_id, idempotency_key=None)
    return fire_event_sync(event_name, tenant_id, context, conn)
