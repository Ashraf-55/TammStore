"""
Database access layer for Codela OS.

Defaults to SQLite (zero-config, file-based) for local development and small
deployments. Set the DATABASE_URL environment variable to a postgres:// URL
to use PostgreSQL instead — requires `pip install psycopg2-binary` (not
bundled by default since most local setups won't need it).

NOTE: the PostgreSQL path is provided as a migration-ready option and uses
schema_postgres.sql. It has not been exercised against a live Postgres
server in this build environment (no network access here) — test it in
your own environment before relying on it in production.
"""
import os
import sqlite3
import re

DB_PATH = os.environ.get("CODELA_DB_PATH", os.path.join(os.path.dirname(__file__), "codela.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")
SCHEMA_PG_PATH = os.path.join(os.path.dirname(__file__), "schema_postgres.sql")

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith(("postgres://", "postgresql://")))
if os.getenv("CODELA_ENV", "development").lower() == "production" and not USE_POSTGRES:
    raise RuntimeError("Production requires PostgreSQL via DATABASE_URL; SQLite is forbidden")

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras


class PGRowWrapper(dict):
    """Makes psycopg2 RealDictRow behave like sqlite3.Row for dict(row) calls
    already used throughout the route files."""
    pass


def get_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = False
        return PGConnectionAdapter(conn)
    conn = sqlite3.connect(DB_PATH, timeout=int(os.getenv("CODELA_DB_TIMEOUT_SECONDS", 10)))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _translate_sqlite_sql(query):
    """Translate the small SQLite-specific SQL subset used by route code.

    Keeping this compatibility layer centralized means the application can
    use the same parameterized queries against SQLite and PostgreSQL.
    """
    # datetime('now', '-15 minutes') -> CURRENT_TIMESTAMP - INTERVAL '15 minutes'
    def datetime_offset(match):
        sign = match.group(1)
        amount = match.group(2)
        unit = match.group(3)
        return f"CURRENT_TIMESTAMP {sign} INTERVAL '{amount} {unit}'"

    query = re.sub(
        r"datetime\(\s*'now'\s*,\s*'([+-])([0-9]+)\s+(minutes?|hours?|days?)'\s*\)",
        datetime_offset, query, flags=re.IGNORECASE
    )
    query = re.sub(r"datetime\(\s*'now'\s*\)", "CURRENT_TIMESTAMP", query, flags=re.IGNORECASE)
    query = re.sub(r"date\(\s*'now'\s*\)", "CURRENT_DATE", query, flags=re.IGNORECASE)
    query = re.sub(r"time\(\s*'now'\s*\)", "CURRENT_TIME", query, flags=re.IGNORECASE)
    return query


class PGConnectionAdapter:
    """Thin adapter so route code written against sqlite3's conn.execute(...).fetchone()
    style also works unmodified against psycopg2. Translates '?' placeholders to '%s'."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, params=()):
        cur = self._conn.cursor()
        query = _translate_sqlite_sql(query)
        query = query.replace("?", "%s")

        # Route code relies on sqlite3.Cursor.lastrowid. PostgreSQL does not
        # expose an equivalent, so make INSERTs return their generated id.
        # This keeps the existing route layer portable without LASTVAL(),
        # which is connection-state dependent and unsafe as a general adapter.
        stripped = query.lstrip().lower()
        if stripped.startswith("insert") and " returning " not in stripped:
            m=re.search(r"insert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)",stripped); table=m.group(1) if m else ""
            if table in {"tenants","users","sessions","notifications","leads","lead_activities","clients","deals","projects","tasks","task_comments","creators","content_ideas","content_calendar","content_analytics","platform_connections","publish_log","finance_transactions","salaries","attendance","courses","enrollments","sops","sop_categories","assets","asset_maintenance_log","requests","automation_rules","automation_runs","followup_sequences","followup_steps","followups","message_templates","messages","commission_rules","invoices","invoice_items","payments","subscriptions","subscription_invoices","jobs","login_attempts","departments","positions","employees","client_contacts","client_addresses","project_members","project_milestones","project_deliverables","project_approvals","project_activities","task_time_entries","project_budgets","project_costs","expenses","quotes","files","conversations","conversation_participants","students","instructors","student_attendance","assessments","assessment_attempts","content_briefs","content_versions","content_approvals","leave_requests","payroll_runs","payroll_items","project_status_history","request_comments","deliverable_versions","conversation_messages","file_versions","employee_contracts","employee_documents","employee_salary_history","employee_reporting_history","quote_items","quote_events","payment_allocations","refunds","credit_notes","task_events","notification_deliveries","file_access_log","audit_entity_links","workflow_definitions","workflow_transitions","backup_runs","system_health_checks","roles","lessons","instructors"}:
                query=query.rstrip().rstrip(";")+" RETURNING id"; cur.execute(query,params); returned=cur.fetchone(); return PGCursorAdapter(cur,self._conn,returned[0] if returned else None)

        cur.execute(query, params)
        return PGCursorAdapter(cur, self._conn)

    def executescript(self, script):
        cur = self._conn.cursor()
        cur.execute(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


class PGCursorAdapter:
    def __init__(self, cur, conn, lastrowid=None):
        self._cur = cur
        self._conn = conn
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def rowcount(self):
        return self._cur.rowcount
def init_db():
    conn = get_db()
    schema_path = SCHEMA_PG_PATH if USE_POSTGRES else SCHEMA_PATH
    with open(schema_path, "r", encoding="utf-8") as f:
        script = f.read()
    if USE_POSTGRES:
        cur = conn._conn.cursor()
        cur.execute(script)
        conn.commit()
    else:
        conn.executescript(script)
        conn.commit()
    conn.close()
    from migrations.runner import upgrade
    upgrade()


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    return [dict(r) for r in rows]


_ALLOWED_TENANT_TABLES = {
    "users", "leads", "clients", "projects", "tasks", "deals", "assets",
    "content_ideas", "content_calendar", "content_analytics", "finance_transactions",
    "salaries", "invoices", "invoice_items", "payments", "commission_rules",
    "requests", "followups", "followup_sequences", "followup_steps", "courses",
    "enrollments", "sops", "automation_rules", "message_templates", "creators",
    "publish_log", "attendance", "notifications", "platform_connections", "lead_activities", "task_comments", "content_calendar", "content_analytics", "asset_maintenance_log", "messages", "departments", "positions", "employees", "employee_status_history", "roles", "user_roles", "client_contacts", "client_users", "client_addresses", "project_members", "project_milestones", "project_deliverables", "project_approvals", "project_activities", "task_dependencies", "task_watchers", "task_time_entries", "project_budgets", "project_costs", "expenses", "quotes", "files", "file_links", "conversations", "conversation_participants", "message_attachments", "students", "instructors", "course_instructors", "student_attendance", "assessments", "assessment_attempts", "content_briefs", "content_versions", "content_approvals", "content_assets", "tenant_settings", "leave_requests", "payroll_runs", "payroll_items", "project_status_history", "request_comments", "deliverable_versions", "conversation_messages", "file_versions", "employee_contracts", "employee_documents", "employee_salary_history", "employee_reporting_history", "quote_items", "quote_events", "payment_allocations", "refunds", "credit_notes", "task_events", "notification_deliveries", "file_access_log", "audit_entity_links", "workflow_definitions", "workflow_transitions", "backup_runs", "system_health_checks",
}

def tenant_resource_exists(conn, table, resource_id, tenant_id):
    """Return True only when a resource belongs to the active tenant.

    The table name is allow-listed because SQL identifiers cannot be parameterized.
    Use this for validating foreign-key IDs supplied by API clients.
    """
    if table not in _ALLOWED_TENANT_TABLES:
        raise ValueError(f"Unsupported tenant table: {table}")
    row = conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND tenant_id=?", (resource_id, tenant_id)).fetchone()
    return row is not None


DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100  # matches the existing global validator in app.py's
                        # before_request guard, which already rejects
                        # ?limit=<not 1-100> with a 400 before a route is
                        # ever reached. This clamp is a defensive fallback
                        # for any caller of pagination_params() that isn't
                        # behind that guard.


def pagination_params(request):
    """Parse limit/offset from query args for a list endpoint. Callers who
    never pass ?limit=/?offset= still get a bounded query (DEFAULT_PAGE_LIMIT)
    instead of an unbounded SELECT * — this is the actual production risk on
    a large tenant, not the response shape. Passing an explicit ?limit=
    enables real pagination for callers who want it; app.py's before_request
    guard already validates it's an integer in [1,100] and returns 400
    otherwise, so by the time this runs the value (if present) is trusted.
    offset isn't validated upstream, so it's defensively clamped here."""
    try:
        limit = int(request.args.get("limit", DEFAULT_PAGE_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_PAGE_LIMIT
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    limit = max(1, min(limit, MAX_PAGE_LIMIT))
    offset = max(0, offset)
    return limit, offset

