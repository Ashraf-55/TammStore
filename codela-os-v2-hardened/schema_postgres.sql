-- ============================================================
-- Codela OS — Database Schema (PostgreSQL)
-- Modules: CORE, CRM, PROJECTS, MEDIA, FINANCE, AUDIT, HR, SOP,
--          ASSETS, REQUESTS, MULTI-TENANT, SECURITY (2FA/Sessions)
-- ============================================================

-- ---------------- TENANTS (Multi-tenant / SaaS) ----------------

CREATE TABLE IF NOT EXISTS tenants (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    plan            TEXT NOT NULL DEFAULT 'trial' CHECK (plan IN ('trial','starter','pro','enterprise')),
    is_active       INTEGER NOT NULL DEFAULT 1,
    office_lat      REAL,
    office_lng      REAL,
    office_radius_m INTEGER DEFAULT 200,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- CORE ----------------

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN (
                        'founder','admin','sales','sales_manager',
                        'content_manager','content_creator','model',
                        'moderator','designer','video_editor',
                        'developer','project_manager','accountant'
                    )),
    department      TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    totp_secret     TEXT,
    totp_pending_secret TEXT,
    totp_pending_expires_at TIMESTAMP NULL,
    totp_pending_attempts INTEGER NOT NULL DEFAULT 0,
    totp_enabled    INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

CREATE TABLE IF NOT EXISTS sessions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL,
    user_agent      TEXT,
    ip_address      TEXT,
    is_revoked      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL,
    tenant_id       INTEGER,
    success         INTEGER NOT NULL,
    ip_address      TEXT,
    user_agent      TEXT,
    request_id      TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_challenges (
    jti             TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    expires_at      TIMESTAMP NOT NULL,
    used_at         TIMESTAMP,
    attempts        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notifications (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,
    message         TEXT NOT NULL,
    link            TEXT,
    is_read         INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id),
    action          TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       INTEGER,
    details         TEXT,
    ip_address      TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- CRM ----------------

CREATE TABLE IF NOT EXISTS leads (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    company         TEXT,
    phone           TEXT,
    whatsapp        TEXT,
    email           TEXT,
    industry        TEXT,
    source          TEXT,
    assigned_sales_id INTEGER REFERENCES users(id),
    service_interested TEXT,
    budget          REAL,
    status          TEXT NOT NULL DEFAULT 'new' CHECK (status IN (
                        'new','contacted','qualified','meeting',
                        'proposal','negotiation','won','lost'
                    )),
    score           INTEGER DEFAULT 0,
    score_tier      TEXT DEFAULT 'cold' CHECK (score_tier IN ('hot','warm','cold')),
    notes           TEXT,
    next_followup   TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lead_activities (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id),
    type            TEXT NOT NULL CHECK (type IN ('call','message','meeting','note','followup')),
    content          TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS clients (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    lead_id         INTEGER REFERENCES leads(id),
    name            TEXT NOT NULL,
    company         TEXT,
    phone           TEXT,
    email           TEXT,
    account_manager_id INTEGER REFERENCES users(id),
    industry        TEXT,
    notes           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deals (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    lead_id         INTEGER REFERENCES leads(id),
    client_id       INTEGER REFERENCES clients(id),
    title           TEXT NOT NULL,
    value           REAL NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','won','lost')),
    sales_id        INTEGER REFERENCES users(id),
    closed_at       TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- PROJECTS ----------------

CREATE TABLE IF NOT EXISTS projects (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_id       INTEGER REFERENCES clients(id),
    name            TEXT NOT NULL,
    description     TEXT,
    project_manager_id INTEGER REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','delayed','cancelled')),
    start_date      TEXT,
    end_date        TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    assignee_id     INTEGER REFERENCES users(id),
    priority        TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high','urgent')),
    status          TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','in_progress','review','approved','done')),
    deadline        TEXT,
    order_index     INTEGER DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_comments (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    task_id         INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id),
    comment         TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- MEDIA ----------------

CREATE TABLE IF NOT EXISTS creators (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id),
    login_code      TEXT,
    stage_name      TEXT NOT NULL,
    niche           TEXT,
    content_pillars TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, login_code)
);

CREATE TABLE IF NOT EXISTS content_ideas (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    category        TEXT,
    platform        TEXT,
    creator_id      INTEGER REFERENCES creators(id),
    hook            TEXT,
    script          TEXT,
    video_url       TEXT,
    submitted_by_creator INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'idea' CHECK (status IN (
                        'idea','research','script','approved','shooting',
                        'editing','review','client_approval','scheduled','published'
                    )),
    expected_goal   TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_calendar (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content_id      INTEGER REFERENCES content_ideas(id),
    shoot_date      TEXT,
    editor_id       INTEGER REFERENCES users(id),
    designer_id     INTEGER REFERENCES users(id),
    publish_date    TEXT,
    platform        TEXT,
    status          TEXT NOT NULL DEFAULT 'planned',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_analytics (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content_id      INTEGER NOT NULL REFERENCES content_ideas(id) ON DELETE CASCADE,
    views           INTEGER DEFAULT 0,
    reach           INTEGER DEFAULT 0,
    likes           INTEGER DEFAULT 0,
    comments        INTEGER DEFAULT 0,
    shares          INTEGER DEFAULT 0,
    saves           INTEGER DEFAULT 0,
    watch_time_sec  INTEGER DEFAULT 0,
    recorded_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- PUBLISHING (social platform connections + publish log) ----------------

CREATE TABLE IF NOT EXISTS platform_connections (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL CHECK (platform IN ('tiktok','instagram','youtube','facebook')),
    account_name    TEXT,
    access_token    TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    connected_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, platform, account_name)
);

CREATE TABLE IF NOT EXISTS publish_log (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content_id      INTEGER NOT NULL REFERENCES content_ideas(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','published','failed')),
    external_post_id TEXT,
    error_message   TEXT,
    mode            TEXT NOT NULL DEFAULT 'mock' CHECK (mode IN ('mock','live')),
    idempotency_key TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- FINANCE ----------------

CREATE TABLE IF NOT EXISTS finance_transactions (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type            TEXT NOT NULL CHECK (type IN ('income','expense')),
    category        TEXT NOT NULL,
    amount          REAL NOT NULL,
    description     TEXT,
    client_id       INTEGER REFERENCES clients(id),
    project_id      INTEGER REFERENCES projects(id),
    date            DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS salaries (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    month           TEXT NOT NULL,
    base_salary     REAL NOT NULL DEFAULT 0,
    commission      REAL NOT NULL DEFAULT 0,
    bonus           REAL NOT NULL DEFAULT 0,
    deductions      REAL NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid')),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- HR & ACADEMY ----------------

CREATE TABLE IF NOT EXISTS attendance (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date            DATE NOT NULL DEFAULT CURRENT_DATE,
    check_in        TEXT,
    check_out       TEXT,
    status          TEXT NOT NULL DEFAULT 'present' CHECK (status IN ('present','late','absent','leave')),
    notes           TEXT,
    check_in_ip     TEXT,
    check_in_lat    REAL,
    check_in_lng    REAL,
    check_in_distance_m INTEGER,
    check_out_ip    TEXT,
    check_out_lat   REAL,
    check_out_lng   REAL,
    is_flagged      INTEGER NOT NULL DEFAULT 0,
    flag_reason     TEXT,
    UNIQUE(user_id, date)
);

CREATE TABLE IF NOT EXISTS courses (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    weeks           INTEGER DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lessons (
    id              SERIAL PRIMARY KEY,
    course_id       INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    order_index     INTEGER DEFAULT 0,
    content         TEXT
);

CREATE TABLE IF NOT EXISTS enrollments (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    course_id       INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress','completed','dropped')),
    progress_pct    INTEGER DEFAULT 0,
    enrolled_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(course_id, user_id)
);

CREATE TABLE IF NOT EXISTS lesson_progress (
    id              SERIAL PRIMARY KEY,
    enrollment_id   INTEGER NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    completed       INTEGER NOT NULL DEFAULT 0,
    score           INTEGER,
    completed_at    TEXT,
    UNIQUE(enrollment_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS certificates (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id       INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    certificate_code TEXT NOT NULL UNIQUE,
    issued_at       TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- SOP CENTER ----------------

CREATE TABLE IF NOT EXISTS sop_categories (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    UNIQUE(tenant_id, name)
);

CREATE TABLE IF NOT EXISTS sops (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    category_id     INTEGER REFERENCES sop_categories(id),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- ASSETS & EQUIPMENT ----------------

CREATE TABLE IF NOT EXISTS assets (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    category        TEXT,
    owner_id        INTEGER REFERENCES users(id),
    location        TEXT,
    status          TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available','in_use','maintenance','retired')),
    purchase_date   TEXT,
    value           REAL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS asset_maintenance_log (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    asset_id        INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    date            DATE NOT NULL DEFAULT CURRENT_DATE,
    notes           TEXT,
    cost            REAL DEFAULT 0
);

-- ---------------- REQUESTS (auto -> Task automation) ----------------

CREATE TABLE IF NOT EXISTS requests (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    requester_name  TEXT NOT NULL,
    requester_contact TEXT,
    client_id       INTEGER REFERENCES clients(id),
    request_type    TEXT NOT NULL DEFAULT 'general',
    title           TEXT NOT NULL,
    description     TEXT,
    priority        TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high','urgent')),
    status          TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','triaged','in_progress','resolved','rejected')),
    created_task_id INTEGER REFERENCES tasks(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- Helpful indexes ----------------
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_sales ON leads(assigned_sales_id);
CREATE INDEX IF NOT EXISTS idx_clients_tenant ON clients(tenant_id);
CREATE INDEX IF NOT EXISTS idx_deals_tenant ON deals(tenant_id);
CREATE INDEX IF NOT EXISTS idx_projects_tenant ON projects(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tasks_tenant ON tasks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_content_tenant ON content_ideas(tenant_id);
CREATE INDEX IF NOT EXISTS idx_content_status ON content_ideas(status);
CREATE INDEX IF NOT EXISTS idx_finance_tenant ON finance_transactions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_finance_date ON finance_transactions(date);
CREATE INDEX IF NOT EXISTS idx_requests_tenant ON requests(tenant_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance(user_id, date);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(refresh_token_hash);

-- ============================================================
-- V2 ADDITIONS: Automation, Follow-up, Communication, Finance/Billing,
--               SaaS Subscription Engines (PostgreSQL)
-- ============================================================

-- ---------------- AUTOMATION ENGINE ----------------

CREATE TABLE IF NOT EXISTS automation_rules (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    trigger_event   TEXT NOT NULL,
    conditions      TEXT NOT NULL DEFAULT '[]',
    actions         TEXT NOT NULL DEFAULT '[]',
    is_active       INTEGER NOT NULL DEFAULT 1,
    run_count       INTEGER NOT NULL DEFAULT 0,
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS automation_runs (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    rule_id         INTEGER REFERENCES automation_rules(id) ON DELETE CASCADE,
    trigger_event   TEXT NOT NULL,
    entity_type     TEXT,
    entity_id       INTEGER,
    status          TEXT NOT NULL CHECK (status IN ('success','failed','skipped')),
    result          TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- FOLLOW-UP ENGINE ----------------

CREATE TABLE IF NOT EXISTS followup_sequences (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    applies_to      TEXT NOT NULL DEFAULT 'lead',
    is_default      INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS followup_steps (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sequence_id     INTEGER NOT NULL REFERENCES followup_sequences(id) ON DELETE CASCADE,
    step_order      INTEGER NOT NULL DEFAULT 1,
    delay_hours     INTEGER NOT NULL DEFAULT 24,
    channel         TEXT NOT NULL DEFAULT 'whatsapp' CHECK (channel IN ('whatsapp','email','call','note')),
    title           TEXT NOT NULL,
    message_template TEXT,
    UNIQUE(sequence_id, step_order)
);

CREATE TABLE IF NOT EXISTS followups (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    sequence_id     INTEGER REFERENCES followup_sequences(id),
    step_id         INTEGER REFERENCES followup_steps(id),
    assigned_to     INTEGER REFERENCES users(id),
    channel         TEXT NOT NULL DEFAULT 'whatsapp' CHECK (channel IN ('whatsapp','email','call','note')),
    title           TEXT NOT NULL,
    message         TEXT,
    due_at          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','done','overdue','skipped','cancelled')),
    completed_at    TEXT,
    completed_by    INTEGER REFERENCES users(id),
    notes           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- COMMUNICATION CENTER ----------------

CREATE TABLE IF NOT EXISTS message_templates (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    channel         TEXT NOT NULL CHECK (channel IN ('whatsapp','email','sms')),
    subject         TEXT,
    body            TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL CHECK (channel IN ('whatsapp','email','sms')),
    direction       TEXT NOT NULL DEFAULT 'outbound' CHECK (direction IN ('outbound','inbound')),
    lead_id         INTEGER REFERENCES leads(id),
    client_id       INTEGER REFERENCES clients(id),
    user_id         INTEGER REFERENCES users(id),
    to_address      TEXT,
    subject         TEXT,
    body            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','sent','failed')),
    external_id     TEXT,
    error_message   TEXT,
    mode            TEXT NOT NULL DEFAULT 'mock' CHECK (mode IN ('mock','live')),
    idempotency_key TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- FINANCE ENGINE: commissions + invoicing ----------------

CREATE TABLE IF NOT EXISTS commission_rules (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    role            TEXT,
    rule_type       TEXT NOT NULL DEFAULT 'percent_of_deal' CHECK (rule_type IN ('percent_of_deal','flat')),
    rate            REAL NOT NULL DEFAULT 0,
    flat_amount     REAL NOT NULL DEFAULT 0,
    min_deal_value  REAL NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invoices (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_id       INTEGER REFERENCES clients(id),
    project_id      INTEGER REFERENCES projects(id),
    deal_id         INTEGER REFERENCES deals(id),
    invoice_number  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','paid','overdue','cancelled')),
    issue_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date        TEXT,
    subtotal        REAL NOT NULL DEFAULT 0,
    tax_pct         REAL NOT NULL DEFAULT 0,
    total           REAL NOT NULL DEFAULT 0,
    amount_paid     REAL NOT NULL DEFAULT 0,
    notes           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, invoice_number)
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id      INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description     TEXT NOT NULL,
    quantity        REAL NOT NULL DEFAULT 1,
    unit_price      REAL NOT NULL DEFAULT 0,
    amount          REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payments (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id      INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount          REAL NOT NULL,
    method          TEXT,
    reference       TEXT,
    paid_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- SAAS SUBSCRIPTION ENGINE ----------------

CREATE TABLE IF NOT EXISTS plans (
    id              SERIAL PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    price_monthly   REAL NOT NULL DEFAULT 0,
    price_yearly    REAL NOT NULL DEFAULT 0,
    max_users       INTEGER NOT NULL DEFAULT 5,
    max_leads       INTEGER NOT NULL DEFAULT 100,
    max_storage_mb  INTEGER NOT NULL DEFAULT 500,
    features        TEXT NOT NULL DEFAULT '[]',
    is_active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id         INTEGER NOT NULL REFERENCES plans(id),
    status          TEXT NOT NULL DEFAULT 'trialing' CHECK (status IN ('trialing','active','past_due','canceled')),
    billing_cycle   TEXT NOT NULL DEFAULT 'monthly' CHECK (billing_cycle IN ('monthly','yearly')),
    current_period_start TIMESTAMP NOT NULL DEFAULT NOW(),
    current_period_end   TEXT,
    trial_ends_at   TEXT,
    canceled_at     TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscription_invoices (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    amount          REAL NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','failed')),
    period_start    TEXT,
    period_end      TEXT,
    paid_at         TEXT,
    mode            TEXT NOT NULL DEFAULT 'mock' CHECK (mode IN ('mock','live')),
    idempotency_key TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------- V2 indexes ----------------
CREATE INDEX IF NOT EXISTS idx_automation_rules_tenant ON automation_rules(tenant_id, trigger_event);
CREATE INDEX IF NOT EXISTS idx_automation_runs_tenant ON automation_runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_followups_tenant ON followups(tenant_id);
CREATE INDEX IF NOT EXISTS idx_followups_lead ON followups(lead_id);
CREATE INDEX IF NOT EXISTS idx_followups_status_due ON followups(status, due_at);
CREATE INDEX IF NOT EXISTS idx_followups_assigned ON followups(assigned_to);
CREATE INDEX IF NOT EXISTS idx_messages_tenant ON messages(tenant_id);
CREATE INDEX IF NOT EXISTS idx_messages_lead ON messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_commission_rules_tenant ON commission_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_invoices_tenant ON invoices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant ON subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_subscription_invoices_sub ON subscription_invoices(subscription_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_invoice_idempotency ON subscription_invoices(tenant_id,idempotency_key);


CREATE INDEX IF NOT EXISTS idx_login_attempts_identity ON login_attempts(email, ip_address, success, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address, success, created_at);

-- ---------------- BACKGROUND JOBS ----------------
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL, payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5, run_after TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP, finished_at TIMESTAMP, last_error TEXT, lease_until TIMESTAMP, lease_token TEXT,
    idempotency_scope TEXT, idempotency_key TEXT, created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_idempotency_scope_key ON jobs(idempotency_scope,idempotency_key);
CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status, run_after);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id, created_at);


-- DOMAIN FOUNDATION V13 (also installed by migration runner)
-- Codela OS Domain Foundation v13
-- Additive migration: no legacy table is dropped.

CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT,
    manager_employee_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, name),
    UNIQUE(tenant_id, code)
);

CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    code TEXT,
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, title),
    UNIQUE(tenant_id, code)
);

CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    employee_code TEXT,
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    position_id INTEGER REFERENCES positions(id) ON DELETE SET NULL,
    manager_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    hire_date TEXT,
    employment_type TEXT NOT NULL DEFAULT 'full_time',
    employment_status TEXT NOT NULL DEFAULT 'active',
    hourly_cost REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    updated_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, user_id),
    UNIQUE(tenant_id, employee_code)
);

CREATE TABLE IF NOT EXISTS employee_status_history (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    effective_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    is_system INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, name)
);

CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY(role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    PRIMARY KEY(tenant_id, user_id, role_id)
);

CREATE TABLE IF NOT EXISTS client_contacts (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    job_title TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS client_users (
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'client_user',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    PRIMARY KEY(tenant_id, client_id, user_id),
    UNIQUE(tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS client_addresses (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    label TEXT NOT NULL DEFAULT 'primary',
    address_line1 TEXT,
    address_line2 TEXT,
    city TEXT,
    country TEXT,
    postal_code TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS project_members (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member',
    status TEXT NOT NULL DEFAULT 'active',
    joined_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, project_id, employee_id)
);

CREATE TABLE IF NOT EXISTS project_milestones (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    start_date TEXT,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS project_deliverables (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    milestone_id INTEGER REFERENCES project_milestones(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    submitted_by INTEGER REFERENCES users(id),
    submitted_at TEXT,
    due_date TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    updated_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS project_approvals (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    deliverable_id INTEGER NOT NULL REFERENCES project_deliverables(id) ON DELETE CASCADE,
    requested_by INTEGER REFERENCES users(id),
    approver_id INTEGER REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'pending',
    feedback TEXT,
    requested_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS project_activities (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    actor_user_id INTEGER REFERENCES users(id),
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    payload TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    PRIMARY KEY(tenant_id, task_id, depends_on_task_id),
    CHECK(task_id <> depends_on_task_id)
);

CREATE TABLE IF NOT EXISTS task_watchers (
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY(tenant_id, task_id, user_id)
);

CREATE TABLE IF NOT EXISTS task_time_entries (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    work_date TEXT NOT NULL,
    hours REAL NOT NULL CHECK(hours >= 0),
    hourly_cost REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS project_budgets (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    budget_amount REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, project_id)
);

CREATE TABLE IF NOT EXISTS project_costs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id INTEGER,
    amount REAL NOT NULL DEFAULT 0,
    description TEXT,
    occurred_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    amount REAL NOT NULL DEFAULT 0,
    category TEXT NOT NULL DEFAULT 'general',
    description TEXT,
    expense_date TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD')),
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS quotes (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    deal_id INTEGER REFERENCES deals(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    quote_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    subtotal REAL NOT NULL DEFAULT 0,
    tax_pct REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    valid_until TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, quote_number)
);

CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uploaded_by INTEGER REFERENCES users(id),
    original_name TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    checksum TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS file_links (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, file_id, entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    subject TEXT,
    context_type TEXT,
    context_id INTEGER,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS conversation_participants (
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY(tenant_id, conversation_id, user_id)
);

CREATE TABLE IF NOT EXISTS message_attachments (
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    PRIMARY KEY(tenant_id, message_id, file_id)
);

CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    student_code TEXT,
    guardian_name TEXT,
    guardian_contact TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, student_code),
    UNIQUE(tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS instructors (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    bio TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS course_instructors (
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    instructor_id INTEGER NOT NULL REFERENCES instructors(id) ON DELETE CASCADE,
    PRIMARY KEY(tenant_id, course_id, instructor_id)
);

CREATE TABLE IF NOT EXISTS student_attendance (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE SET NULL,
    attendance_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'present',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS assessments (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    max_score REAL NOT NULL DEFAULT 100,
    pass_score REAL NOT NULL DEFAULT 50,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS assessment_attempts (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    score REAL NOT NULL DEFAULT 0,
    passed INTEGER NOT NULL DEFAULT 0,
    attempted_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS content_briefs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content_id INTEGER NOT NULL REFERENCES content_ideas(id) ON DELETE CASCADE,
    objective TEXT,
    audience TEXT,
    deliverables TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS content_versions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content_id INTEGER NOT NULL REFERENCES content_ideas(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    body TEXT,
    asset_url TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id, content_id, version)
);

CREATE TABLE IF NOT EXISTS content_approvals (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content_id INTEGER NOT NULL REFERENCES content_ideas(id) ON DELETE CASCADE,
    approver_id INTEGER REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'pending',
    feedback TEXT,
    requested_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS content_assets (
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content_id INTEGER NOT NULL REFERENCES content_ideas(id) ON DELETE CASCADE,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    PRIMARY KEY(tenant_id, content_id, file_id)
);

-- Requests evolve from a standalone inbox into a cross-domain intake record.
-- Columns are added separately by the runner for existing installations.

CREATE INDEX IF NOT EXISTS idx_employees_tenant ON employees(tenant_id);
CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(tenant_id, department_id);
CREATE INDEX IF NOT EXISTS idx_client_contacts_client ON client_contacts(tenant_id, client_id);
CREATE INDEX IF NOT EXISTS idx_client_users_client ON client_users(tenant_id, client_id);
CREATE INDEX IF NOT EXISTS idx_project_members_project ON project_members(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_project_members_employee ON project_members(tenant_id, employee_id);
CREATE INDEX IF NOT EXISTS idx_project_milestones_project ON project_milestones(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_project_deliverables_project ON project_deliverables(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_project_approvals_project ON project_approvals(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_task_time_entries_task ON task_time_entries(tenant_id, task_id);
CREATE INDEX IF NOT EXISTS idx_task_time_entries_employee ON task_time_entries(tenant_id, employee_id);
CREATE INDEX IF NOT EXISTS idx_project_costs_project ON project_costs(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_files_tenant ON files(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_file_links_entity ON file_links(tenant_id, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_conversations_context ON conversations(tenant_id, context_type, context_id);
CREATE INDEX IF NOT EXISTS idx_students_tenant ON students(tenant_id);
CREATE INDEX IF NOT EXISTS idx_course_instructors_course ON course_instructors(tenant_id, course_id);
CREATE INDEX IF NOT EXISTS idx_student_attendance_student ON student_attendance(tenant_id, student_id);
CREATE INDEX IF NOT EXISTS idx_assessment_attempts_student ON assessment_attempts(tenant_id, student_id);
