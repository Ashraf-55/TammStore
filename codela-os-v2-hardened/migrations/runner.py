import datetime
from database import get_db, USE_POSTGRES
CURRENT_VERSION=25

def _exec(conn, sql):
    if USE_POSTGRES:
        cur=conn._conn.cursor(); cur.execute(sql)
    else:
        conn.executescript(sql)

def _ensure(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    conn.commit()

def upgrade(conn=None):
    own=conn is None; c=conn or get_db()
    # A migration command must also work against an empty database. Bootstrap
    # the base schema once, then apply versioned changes.
    if c.execute("SELECT to_regclass('public.tenants')" if USE_POSTGRES else "SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'").fetchone() is None:
        import os
        schema_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema_postgres.sql' if USE_POSTGRES else 'schema.sql')
        with open(schema_path,'r',encoding='utf-8') as fh:
            if USE_POSTGRES: c._conn.cursor().execute(fh.read())
            else: c.executescript(fh.read())
        c.commit()
    _ensure(c)
    applied={r["version"] for r in c.execute("SELECT version FROM schema_migrations").fetchall()}
    if 1 not in applied:
        if USE_POSTGRES:
            _exec(c,"CREATE TABLE IF NOT EXISTS access_token_revocations (jti TEXT PRIMARY KEY,user_id INTEGER,tenant_id INTEGER,expires_at TIMESTAMP NOT NULL,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP); CREATE INDEX IF NOT EXISTS idx_access_revocations_exp ON access_token_revocations(expires_at); ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_agent TEXT; ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS request_id TEXT;")
        else:
            _exec(c,"CREATE TABLE IF NOT EXISTS access_token_revocations (jti TEXT PRIMARY KEY,user_id INTEGER,tenant_id INTEGER,expires_at TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP); CREATE INDEX IF NOT EXISTS idx_access_revocations_exp ON access_token_revocations(expires_at);")
            cols={r[1] for r in c.execute("PRAGMA table_info(audit_log)").fetchall()}
            if "user_agent" not in cols:c.execute("ALTER TABLE audit_log ADD COLUMN user_agent TEXT")
            if "request_id" not in cols:c.execute("ALTER TABLE audit_log ADD COLUMN request_id TEXT")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(1,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(1)
    if 2 not in applied:
        _exec(c,"CREATE INDEX IF NOT EXISTS idx_audit_tenant_created ON audit_log(tenant_id,created_at); CREATE INDEX IF NOT EXISTS idx_sessions_user_tenant ON sessions(user_id,tenant_id,is_revoked);")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(2,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(2)
    if 3 not in applied:
        _exec(c,"CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status,run_after); CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id,created_at);")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(3,datetime.datetime.utcnow().isoformat())); c.commit()
    if 4 not in applied:
        if USE_POSTGRES:
            _exec(c,"ALTER TABLE auth_challenges ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0; ALTER TABLE jobs ADD COLUMN IF NOT EXISTS lease_until TIMESTAMP NULL; CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(status,lease_until);")
        else:
            cols={r[1] for r in c.execute("PRAGMA table_info(auth_challenges)").fetchall()}
            if "attempts" not in cols:c.execute("ALTER TABLE auth_challenges ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
            cols={r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()}
            if "lease_until" not in cols:c.execute("ALTER TABLE jobs ADD COLUMN lease_until TEXT")
            c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(status,lease_until)")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(4,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(4)
    if 5 not in applied:
        # Scope idempotency keys by tenant. Global jobs use a dedicated scope.
        # SQLite cannot drop an inline UNIQUE constraint, so rebuild the table.
        if USE_POSTGRES:
            _exec(c, "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS idempotency_scope TEXT; UPDATE jobs SET idempotency_scope=COALESCE(tenant_id::text,'__global__') WHERE idempotency_scope IS NULL; ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_idempotency_key_key; CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_idempotency_scope_key ON jobs(idempotency_scope,idempotency_key);")
        else:
            cols={r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()}
            if "idempotency_scope" not in cols:
                c.execute("ALTER TABLE jobs ADD COLUMN idempotency_scope TEXT")
            c.execute("UPDATE jobs SET idempotency_scope=COALESCE(CAST(tenant_id AS TEXT),'__global__') WHERE idempotency_scope IS NULL")
            # Rebuild to remove the old column-level UNIQUE constraint.
            c.execute("""CREATE TABLE jobs_v5 (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
                job_type TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 5,
                run_after TEXT NOT NULL DEFAULT (datetime('now')), started_at TEXT, finished_at TEXT,
                last_error TEXT, lease_until TEXT, idempotency_scope TEXT, idempotency_key TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""")
            c.execute("""INSERT INTO jobs_v5(id,tenant_id,job_type,payload,status,attempts,max_attempts,run_after,started_at,finished_at,last_error,lease_until,idempotency_scope,idempotency_key,created_at)
                         SELECT id,tenant_id,job_type,payload,status,attempts,max_attempts,run_after,started_at,finished_at,last_error,lease_until,idempotency_scope,idempotency_key,created_at FROM jobs""")
            c.execute("DROP TABLE jobs")
            c.execute("ALTER TABLE jobs_v5 RENAME TO jobs")
            c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status,run_after)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id,created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(status,lease_until)")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_idempotency_scope_key ON jobs(idempotency_scope,idempotency_key)")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(5,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(5)

    if 6 not in applied:
        # Bind active job heartbeats/completion to the worker that owns the lease.
        # Also make 2FA enrollment secrets explicitly short-lived.
        if USE_POSTGRES:
            _exec(c, "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS lease_token TEXT; ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_pending_secret TEXT; ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_pending_expires_at TIMESTAMP NULL; CREATE INDEX IF NOT EXISTS idx_jobs_lease_token ON jobs(id,lease_token); CREATE INDEX IF NOT EXISTS idx_users_totp_pending ON users(id,totp_pending_expires_at);")
        else:
            cols={r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()}
            if "lease_token" not in cols:c.execute("ALTER TABLE jobs ADD COLUMN lease_token TEXT")
            cols={r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()}
            if "totp_pending_secret" not in cols:c.execute("ALTER TABLE users ADD COLUMN totp_pending_secret TEXT")
            if "totp_pending_expires_at" not in cols:c.execute("ALTER TABLE users ADD COLUMN totp_pending_expires_at TEXT")
            c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_lease_token ON jobs(id,lease_token)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_users_totp_pending ON users(id,totp_pending_expires_at)")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(6,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(6)

    if 7 not in applied:
        # Bound pending 2FA enrollment attempts to prevent brute-force of the
        # six-digit confirmation code. The pending secret remains separate
        # from the active secret until confirmation succeeds.
        if USE_POSTGRES:
            _exec(c, "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_pending_attempts INTEGER NOT NULL DEFAULT 0; CREATE INDEX IF NOT EXISTS idx_users_totp_pending_attempts ON users(id,totp_pending_attempts);")
        else:
            cols={r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()}
            if "totp_pending_attempts" not in cols:
                c.execute("ALTER TABLE users ADD COLUMN totp_pending_attempts INTEGER NOT NULL DEFAULT 0")
            c.execute("CREATE INDEX IF NOT EXISTS idx_users_totp_pending_attempts ON users(id,totp_pending_attempts)")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(7,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(7)

    if 8 not in applied:
        # Payment subscribe requests need a tenant-scoped idempotency key so a
        # retried request cannot charge twice when a gateway is connected.
        if USE_POSTGRES:
            _exec(c, "ALTER TABLE subscription_invoices ADD COLUMN IF NOT EXISTS idempotency_key TEXT; CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_invoice_idempotency ON subscription_invoices(tenant_id,idempotency_key) WHERE idempotency_key IS NOT NULL;")
        else:
            cols={r[1] for r in c.execute("PRAGMA table_info(subscription_invoices)").fetchall()}
            if "idempotency_key" not in cols:c.execute("ALTER TABLE subscription_invoices ADD COLUMN idempotency_key TEXT")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_invoice_idempotency ON subscription_invoices(tenant_id,idempotency_key)")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(8,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(8)

    if 9 not in applied:
        # Encrypt existing platform integration secrets and enforce encrypted-at-rest
        # storage for all future writes. Production deliberately fails if a legacy
        # plaintext secret cannot be encrypted because the key is missing.
        from secret_store import encrypt_secret
        rows=c.execute("SELECT id, access_token FROM platform_connections WHERE access_token IS NOT NULL AND access_token != ''").fetchall()
        for r in rows:
            token=str(r["access_token"])
            if not token.startswith("enc:v1:"):
                c.execute("UPDATE platform_connections SET access_token=? WHERE id=?",(encrypt_secret(token, require_key=True),r["id"]))
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(9,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(9)

    if 10 not in applied:
        _exec(c,"CREATE INDEX IF NOT EXISTS idx_jobs_claim ON jobs(status,run_after,id)")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(10,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(10)

    if 11 not in applied:
        # Production invariants: encrypted integration secrets and atomic 2FA setup support.
        rows=c.execute("SELECT id, access_token FROM platform_connections WHERE access_token IS NOT NULL AND access_token != ''").fetchall()
        plaintext=[r["id"] for r in rows if not str(r["access_token"]).startswith("enc:v1:")]
        if plaintext:
            from secret_store import encryption_key_available, encrypt_secret
            if not encryption_key_available():
                raise RuntimeError("Migration 11 requires CODELA_ENCRYPTION_KEY to encrypt legacy integration secrets")
            for r in rows:
                token=str(r["access_token"])
                if not token.startswith("enc:v1:"):
                    c.execute("UPDATE platform_connections SET access_token=? WHERE id=?",(encrypt_secret(token, require_key=True),r["id"]))
        if USE_POSTGRES:
            _exec(c,"CREATE INDEX IF NOT EXISTS idx_jobs_running_lease ON jobs(status,lease_until,lease_token); CREATE INDEX IF NOT EXISTS idx_platform_connections_tenant ON platform_connections(tenant_id,id)")
        else:
            c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_running_lease ON jobs(status,lease_until,lease_token)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_platform_connections_tenant ON platform_connections(tenant_id,id)")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(11,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(11)

    if 13 not in applied:
        # Domain foundation: additive identity, RBAC, client portal, project delivery,
        # finance linkage, files, communication, academy, and content workflow tables.
        import os
        domain_path=os.path.join(os.path.dirname(__file__), 'domain_v13.sql')
        with open(domain_path,'r',encoding='utf-8') as fh:
            script=fh.read()
        if USE_POSTGRES:
            # Convert SQLite AUTOINCREMENT definitions in this migration to PostgreSQL
            # identity columns while preserving the same logical schema.
            script=script.replace('INTEGER PRIMARY KEY AUTOINCREMENT','BIGSERIAL PRIMARY KEY')
            c._conn.cursor().execute(script)
            # Existing request records get the new workflow fields.
            c._conn.cursor().execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS requester_user_id INTEGER REFERENCES users(id); ALTER TABLE requests ADD COLUMN IF NOT EXISTS requester_type TEXT NOT NULL DEFAULT 'internal'; ALTER TABLE requests ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id); ALTER TABLE requests ADD COLUMN IF NOT EXISTS assigned_to INTEGER REFERENCES users(id); ALTER TABLE requests ADD COLUMN IF NOT EXISTS assigned_team TEXT; ALTER TABLE requests ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP; ALTER TABLE requests ADD COLUMN IF NOT EXISTS resolution TEXT;")
            c._conn.cursor().execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS milestone_id INTEGER REFERENCES project_milestones(id); ALTER TABLE tasks ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id); ALTER TABLE tasks ADD COLUMN IF NOT EXISTS parent_task_id INTEGER REFERENCES tasks(id); ALTER TABLE tasks ADD COLUMN IF NOT EXISTS task_type TEXT DEFAULT 'work'; ALTER TABLE tasks ADD COLUMN IF NOT EXISTS estimated_hours REAL DEFAULT 0; ALTER TABLE tasks ADD COLUMN IF NOT EXISTS actual_hours REAL DEFAULT 0; ALTER TABLE tasks ADD COLUMN IF NOT EXISTS started_at TIMESTAMP; ALTER TABLE tasks ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;")
        else:
            c.executescript(script)
            cols={r[1] for r in c.execute('PRAGMA table_info(requests)').fetchall()}
            additions={
                'requester_user_id':'INTEGER REFERENCES users(id)',
                'requester_type':"TEXT NOT NULL DEFAULT 'internal'",
                'project_id':'INTEGER REFERENCES projects(id)',
                'assigned_to':'INTEGER REFERENCES users(id)',
                'assigned_team':'TEXT',
                'resolved_at':'TEXT',
                'resolution':'TEXT',
            }
            for name,definition in additions.items():
                if name not in cols:
                    c.execute(f'ALTER TABLE requests ADD COLUMN {name} {definition}')
            cols={r[1] for r in c.execute('PRAGMA table_info(tasks)').fetchall()}
            task_additions={
                'milestone_id':'INTEGER REFERENCES project_milestones(id)',
                'created_by':'INTEGER REFERENCES users(id)',
                'parent_task_id':'INTEGER REFERENCES tasks(id)',
                'task_type':"TEXT DEFAULT 'work'",
                'estimated_hours':'REAL DEFAULT 0',
                'actual_hours':'REAL DEFAULT 0',
                'started_at':'TEXT',
                'completed_at':'TEXT',
            }
            for name,definition in task_additions.items():
                if name not in cols:
                    c.execute(f'ALTER TABLE tasks ADD COLUMN {name} {definition}')
        # Global permission catalog. Tenant roles are created lazily; legacy role
        # checks remain supported by policies/permissions.py during the transition.
        permission_codes = [
            ("employees.manage","Manage employees and organization"),
            ("clients.view","View clients"),("clients.create","Create clients"),("clients.update","Update clients"),
            ("crm.view","View CRM"),("crm.manage","Manage CRM"),
            ("projects.view","View projects"),("projects.create","Create projects"),("projects.update","Update projects"),("projects.assign","Assign project members"),
            ("tasks.view","View tasks"),("tasks.create","Create tasks"),("tasks.update","Update tasks"),("tasks.assign","Assign tasks"),
            ("requests.view","View requests"),("requests.update","Update requests"),("requests.assign","Assign requests"),("requests.resolve","Resolve requests"),
            ("finance.view","View finance"),("finance.invoice.create","Create invoices"),("finance.payment.create","Record payments"),
            ("content.view","View content"),("content.manage","Manage content"),
        ]
        for code, description in permission_codes:
            c.execute("INSERT OR IGNORE INTO permissions(code,description) VALUES (?,?)",(code,description)) if not USE_POSTGRES else c.execute("INSERT INTO permissions(code,description) VALUES (?,?) ON CONFLICT(code) DO NOTHING",(code,description))
        # Backfill safe relationships without guessing cross-tenant ownership.
        c.execute("UPDATE requests SET requester_user_id=created_by WHERE 1=0") if False else None
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(13,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(13)

    if 14 not in applied:
        import os
        domain_path=os.path.join(os.path.dirname(__file__), 'domain_v14.sql')
        with open(domain_path,'r',encoding='utf-8') as fh:
            script=fh.read()
        _exec(c, script)
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(14,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(14)

    if 12 not in applied:
        # The billing plan catalog is system reference data, not demo data —
        # every deployment needs it (previously only seed.py inserted it, so
        # any environment that ran migrations without the demo seeder had an
        # empty `plans` table and every new tenant's trial subscription
        # silently failed to attach, denying all lead/user creation with 402).
        if c.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"] == 0:
            c.execute(
                "INSERT INTO plans (code, name, price_monthly, price_yearly, max_users, max_leads, max_storage_mb, features) VALUES "
                "('trial','Trial',0,0,5,50,500,'[\"core\"]'),"
                "('starter','Starter',49,490,5,200,2000,'[\"core\",\"automation\"]'),"
                "('pro','Pro',149,1490,20,2000,20000,'[\"core\",\"automation\",\"billing\",\"followups\"]'),"
                "('enterprise','Enterprise',399,3990,1000,100000,500000,'[\"core\",\"automation\",\"billing\",\"followups\",\"priority_support\"]')"
            )
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(12,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(12)

    if 15 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), 'domain_v15_pg.sql' if USE_POSTGRES else 'domain_v15.sql')
        with open(path,'r',encoding='utf-8') as fh:
            _exec(c, fh.read())
        if USE_POSTGRES:
            _exec(c, "ALTER TABLE content_versions ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft';")
        else:
            cols={r[1] for r in c.execute('PRAGMA table_info(content_versions)').fetchall()}
            if 'status' not in cols: c.execute("ALTER TABLE content_versions ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(15,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(15)

    if 16 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), 'domain_v16_pg.sql' if USE_POSTGRES else 'domain_v16.sql')
        with open(path,'r',encoding='utf-8') as fh:
            _exec(c, fh.read())
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(16,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(16)

    if 17 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), "domain_v17.sql")
        with open(path, "r", encoding="utf-8") as fh:
            script=fh.read()
        if USE_POSTGRES:
            # PostgreSQL uses explicit functions/triggers for the same integrity guarantees.
            pg = script.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
            # SQLite trigger syntax is not portable; create the tables/indexes first, then PG trigger functions.
            parts = pg.split("-- New-write integrity triggers.")[0]
            c._conn.cursor().execute(parts)
            c._conn.cursor().execute("""
            CREATE OR REPLACE FUNCTION codela_check_cross_tenant() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_TABLE_NAME='project_members' AND ((SELECT tenant_id FROM employees WHERE id=NEW.employee_id) IS DISTINCT FROM NEW.tenant_id OR (SELECT tenant_id FROM projects WHERE id=NEW.project_id) IS DISTINCT FROM NEW.tenant_id) THEN RAISE EXCEPTION 'cross_tenant_project_member'; END IF;
              IF TG_TABLE_NAME='tasks' AND NEW.project_id IS NOT NULL AND (SELECT tenant_id FROM projects WHERE id=NEW.project_id) IS DISTINCT FROM NEW.tenant_id THEN RAISE EXCEPTION 'cross_tenant_task_project'; END IF;
              IF TG_TABLE_NAME='tasks' AND NEW.assignee_id IS NOT NULL AND (SELECT tenant_id FROM users WHERE id=NEW.assignee_id) IS DISTINCT FROM NEW.tenant_id THEN RAISE EXCEPTION 'cross_tenant_task_assignee'; END IF;
              IF TG_TABLE_NAME='invoices' AND NEW.client_id IS NOT NULL AND (SELECT tenant_id FROM clients WHERE id=NEW.client_id) IS DISTINCT FROM NEW.tenant_id THEN RAISE EXCEPTION 'cross_tenant_invoice_client'; END IF;
              IF TG_TABLE_NAME='invoices' AND NEW.project_id IS NOT NULL AND (SELECT tenant_id FROM projects WHERE id=NEW.project_id) IS DISTINCT FROM NEW.tenant_id THEN RAISE EXCEPTION 'cross_tenant_invoice_project'; END IF;
              IF TG_TABLE_NAME='payments' AND (SELECT tenant_id FROM invoices WHERE id=NEW.invoice_id) IS DISTINCT FROM NEW.tenant_id THEN RAISE EXCEPTION 'cross_tenant_payment_invoice'; END IF;
              IF TG_TABLE_NAME='payments' AND NEW.amount <= 0 THEN RAISE EXCEPTION 'payment_amount_must_be_positive'; END IF;
              IF TG_TABLE_NAME='payment_allocations' AND ((SELECT tenant_id FROM payments WHERE id=NEW.payment_id) IS DISTINCT FROM NEW.tenant_id OR (SELECT tenant_id FROM invoices WHERE id=NEW.invoice_id) IS DISTINCT FROM NEW.tenant_id) THEN RAISE EXCEPTION 'cross_tenant_payment_allocation'; END IF;
              RETURN NEW;
            END; $$;
            DROP TRIGGER IF EXISTS trg_project_member_tenant ON project_members; CREATE TRIGGER trg_project_member_tenant BEFORE INSERT OR UPDATE ON project_members FOR EACH ROW EXECUTE FUNCTION codela_check_cross_tenant();
            DROP TRIGGER IF EXISTS trg_task_project_tenant ON tasks; CREATE TRIGGER trg_task_project_tenant BEFORE INSERT OR UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION codela_check_cross_tenant();
            DROP TRIGGER IF EXISTS trg_task_assignee_tenant ON tasks; CREATE TRIGGER trg_task_assignee_tenant BEFORE INSERT OR UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION codela_check_cross_tenant();
            DROP TRIGGER IF EXISTS trg_invoice_client_tenant ON invoices; CREATE TRIGGER trg_invoice_client_tenant BEFORE INSERT OR UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION codela_check_cross_tenant();
            DROP TRIGGER IF EXISTS trg_invoice_project_tenant ON invoices; CREATE TRIGGER trg_invoice_project_tenant BEFORE INSERT OR UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION codela_check_cross_tenant();
            DROP TRIGGER IF EXISTS trg_payment_invoice_tenant ON payments; CREATE TRIGGER trg_payment_invoice_tenant BEFORE INSERT OR UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION codela_check_cross_tenant();
            DROP TRIGGER IF EXISTS trg_allocation_tenant ON payment_allocations; CREATE TRIGGER trg_allocation_tenant BEFORE INSERT OR UPDATE ON payment_allocations FOR EACH ROW EXECUTE FUNCTION codela_check_cross_tenant();
            """)
        else:
            c.executescript(script)
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(17,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(17)

    if 18 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), "domain_v18.sql")
        with open(path, "r", encoding="utf-8") as fh:
            script=fh.read()
        if USE_POSTGRES:
            # PostgreSQL equivalent safeguards are installed explicitly because the
            # SQLite trigger syntax above is intentionally not portable.
            c._conn.cursor().execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_claim_v18 ON jobs(status,run_after,lease_until,id);
            CREATE INDEX IF NOT EXISTS idx_messages_tenant_created_v18 ON messages(tenant_id,created_at);
            CREATE INDEX IF NOT EXISTS idx_files_tenant_created_v18 ON files(tenant_id,created_at);
            CREATE INDEX IF NOT EXISTS idx_notifications_tenant_user_read_v18 ON notifications(tenant_id,user_id,is_read,created_at);
            CREATE INDEX IF NOT EXISTS idx_finance_transactions_tenant_date_v18 ON finance_transactions(tenant_id,date,created_at);
            """)
            c._conn.cursor().execute("""
            CREATE OR REPLACE FUNCTION codela_v18_payment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF (SELECT tenant_id FROM invoices WHERE id=NEW.invoice_id) IS DISTINCT FROM NEW.tenant_id OR NEW.amount <= 0 THEN RAISE EXCEPTION 'invalid_payment_update'; END IF;
              RETURN NEW;
            END; $$;
            DROP TRIGGER IF EXISTS trg_payment_tenant_update ON payments;
            CREATE TRIGGER trg_payment_tenant_update BEFORE UPDATE OF tenant_id,invoice_id,amount ON payments FOR EACH ROW EXECUTE FUNCTION codela_v18_payment_guard();
            CREATE OR REPLACE FUNCTION codela_v18_allocation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE pay_t BIGINT; inv_t BIGINT; pay_remaining NUMERIC; inv_remaining NUMERIC;
            BEGIN
              SELECT tenant_id INTO pay_t FROM payments WHERE id=NEW.payment_id;
              SELECT tenant_id INTO inv_t FROM invoices WHERE id=NEW.invoice_id;
              IF pay_t IS DISTINCT FROM NEW.tenant_id OR inv_t IS DISTINCT FROM NEW.tenant_id OR NEW.amount <= 0 THEN RAISE EXCEPTION 'invalid_payment_allocation_update'; END IF;
              SELECT (amount - COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE payment_id=NEW.payment_id AND id<>NEW.id),0)) INTO pay_remaining FROM payments WHERE id=NEW.payment_id;
              SELECT (total - COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE invoice_id=NEW.invoice_id AND id<>NEW.id),0)) INTO inv_remaining FROM invoices WHERE id=NEW.invoice_id;
              IF NEW.amount > pay_remaining OR NEW.amount > inv_remaining THEN RAISE EXCEPTION 'invalid_payment_allocation_update'; END IF;
              RETURN NEW;
            END; $$;
            DROP TRIGGER IF EXISTS trg_allocation_tenant_update ON payment_allocations;
            CREATE TRIGGER trg_allocation_tenant_update BEFORE UPDATE OF tenant_id,payment_id,invoice_id,amount ON payment_allocations FOR EACH ROW EXECUTE FUNCTION codela_v18_allocation_guard();
            """)
        else:
            c.executescript(script)
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(18,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(18)

    if 19 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), 'domain_v19_pg.sql' if USE_POSTGRES else 'domain_v19.sql')
        with open(path,'r',encoding='utf-8') as fh:
            _exec(c, fh.read())
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(19,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(19)

    if 20 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), 'domain_v20_pg.sql' if USE_POSTGRES else 'domain_v20.sql')
        with open(path,'r',encoding='utf-8') as fh:
            _exec(c, fh.read())
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(20,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(20)

    if 21 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), 'domain_v21_pg.sql' if USE_POSTGRES else 'domain_v21.sql')
        with open(path,'r',encoding='utf-8') as fh:
            script=fh.read()
        if USE_POSTGRES:
            _exec(c, script)
        else:
            cols={r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()}
            if "email_verified_at" not in cols:
                c.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")
            # The ALTER above is already applied (guarded for idempotency);
            # run only the remaining CREATE TABLE/INDEX statements from the file.
            remainder = script.split("email_verified_at TEXT;", 1)[-1]
            c.executescript(remainder)
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(21,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(21)

    if 22 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), 'domain_v22_pg.sql' if USE_POSTGRES else 'domain_v22.sql')
        with open(path,'r',encoding='utf-8') as fh:
            _exec(c, fh.read())
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(22,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(22)

    if 23 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), 'domain_v23_pg.sql' if USE_POSTGRES else 'domain_v23.sql')
        with open(path,'r',encoding='utf-8') as fh:
            _exec(c, fh.read())
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(23,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(23)

    if 24 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), 'domain_v24_pg.sql' if USE_POSTGRES else 'domain_v24.sql')
        with open(path,'r',encoding='utf-8') as fh:
            _exec(c, fh.read())
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(24,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(24)

    if 25 not in applied:
        import os
        path=os.path.join(os.path.dirname(__file__), 'domain_v25_pg.sql' if USE_POSTGRES else 'domain_v25.sql')
        with open(path,'r',encoding='utf-8') as fh:
            _exec(c, fh.read())
        c.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",(25,datetime.datetime.utcnow().isoformat())); c.commit(); applied.add(25)

    if own:c.close()

def downgrade(target_version=0):
    c=get_db(); _ensure(c)
    rows=c.execute("SELECT version FROM schema_migrations ORDER BY version DESC").fetchall()
    for r in rows:
        v=r["version"]
        if v<=target_version:continue
        if v==18:
            pass
        elif v==17:
            pass
        elif v==16:
            pass
        elif v==14:
            pass
        elif v==13:
            # v13 is intentionally additive. Keep data and tables on downgrade; only
            # remove the migration marker so an explicit re-upgrade can reconcile schema.
            pass
        elif v==12:
            # Only remove the four default plan rows if untouched (no
            # subscriptions or billing history reference them); otherwise
            # leave the catalog in place rather than break live tenants.
            in_use = c.execute("SELECT COUNT(*) AS n FROM subscriptions").fetchone()["n"]
            if in_use == 0:
                c.execute("DELETE FROM plans WHERE code IN ('trial','starter','pro','enterprise')")
        elif v==11:
            _exec(c,"DROP INDEX IF EXISTS idx_jobs_running_lease; DROP INDEX IF EXISTS idx_platform_connections_tenant")
        elif v==10:
            _exec(c,"DROP INDEX IF EXISTS idx_jobs_claim")
        elif v==9:
            # Secrets cannot safely be downgraded to plaintext. Keep the encrypted
            # values and only remove the migration marker. Older code must refuse
            # plaintext assumptions in production.
            pass
        elif v==8:
            if USE_POSTGRES:
                _exec(c, "DROP INDEX IF EXISTS uq_subscription_invoice_idempotency; ALTER TABLE subscription_invoices DROP COLUMN IF EXISTS idempotency_key;")
            else:
                c.execute("DROP INDEX IF EXISTS uq_subscription_invoice_idempotency")
                c.execute("ALTER TABLE subscription_invoices DROP COLUMN idempotency_key")
        elif v==7:
            if USE_POSTGRES:
                _exec(c, "DROP INDEX IF EXISTS idx_users_totp_pending_attempts; ALTER TABLE users DROP COLUMN IF EXISTS totp_pending_attempts;")
            else:
                c.execute("DROP INDEX IF EXISTS idx_users_totp_pending_attempts")
                c.execute("ALTER TABLE users DROP COLUMN totp_pending_attempts")
        elif v==6:
            if USE_POSTGRES:
                _exec(c, "ALTER TABLE jobs DROP COLUMN IF EXISTS lease_token; ALTER TABLE users DROP COLUMN IF EXISTS totp_pending_expires_at; ALTER TABLE users DROP COLUMN IF EXISTS totp_pending_secret;")
            else:
                # SQLite 3.35+ supports DROP COLUMN; fail loudly on older engines rather than silently leaving schema drift.
                c.execute("DROP INDEX IF EXISTS idx_jobs_lease_token")
                c.execute("DROP INDEX IF EXISTS idx_users_totp_pending")
                c.execute("ALTER TABLE jobs DROP COLUMN lease_token")
                c.execute("ALTER TABLE users DROP COLUMN totp_pending_expires_at")
                c.execute("ALTER TABLE users DROP COLUMN totp_pending_secret")
        elif v==5:
            if USE_POSTGRES:
                _exec(c,"DROP INDEX IF EXISTS uq_jobs_idempotency_scope_key; ALTER TABLE jobs ADD CONSTRAINT jobs_idempotency_key_key UNIQUE(idempotency_key); ALTER TABLE jobs DROP COLUMN IF EXISTS idempotency_scope;")
            else:
                c.execute("""CREATE TABLE jobs_v4 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
                    job_type TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 5,
                    run_after TEXT NOT NULL DEFAULT (datetime('now')), started_at TEXT, finished_at TEXT,
                    last_error TEXT, lease_until TEXT, idempotency_key TEXT UNIQUE,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )""")
                c.execute("""INSERT INTO jobs_v4(id,tenant_id,job_type,payload,status,attempts,max_attempts,run_after,started_at,finished_at,last_error,lease_until,idempotency_key,created_at)
                             SELECT id,tenant_id,job_type,payload,status,attempts,max_attempts,run_after,started_at,finished_at,last_error,lease_until,idempotency_key,created_at FROM jobs""")
                c.execute("DROP TABLE jobs"); c.execute("ALTER TABLE jobs_v4 RENAME TO jobs")
                c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status,run_after)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id,created_at)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(status,lease_until)")
        elif v==4:_exec(c,"DROP INDEX IF EXISTS idx_jobs_lease;")
        elif v==3:_exec(c,"DROP INDEX IF EXISTS idx_jobs_queue; DROP INDEX IF EXISTS idx_jobs_tenant;")
        elif v==2:_exec(c,"DROP INDEX IF EXISTS idx_audit_tenant_created; DROP INDEX IF EXISTS idx_sessions_user_tenant;")
        elif v==1:_exec(c,"DROP TABLE IF EXISTS access_token_revocations;")
        c.execute("DELETE FROM schema_migrations WHERE version=?",(v,)); c.commit()
    c.close()

