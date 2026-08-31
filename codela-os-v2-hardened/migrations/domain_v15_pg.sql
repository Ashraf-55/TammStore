-- Codela OS v15: complete operating system layer. Additive only.
CREATE TABLE IF NOT EXISTS tenant_settings (
    tenant_id INTEGER PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    brand_name TEXT, brand_logo_url TEXT,
    timezone TEXT NOT NULL DEFAULT 'Africa/Cairo',
    default_currency TEXT NOT NULL DEFAULT 'EGP',
    locale TEXT NOT NULL DEFAULT 'ar',
    date_format TEXT DEFAULT 'YYYY-MM-DD',
    invoice_prefix TEXT DEFAULT 'INV',
    updated_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);
CREATE TABLE IF NOT EXISTS notification_preferences (
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    in_app INTEGER NOT NULL DEFAULT 1, email INTEGER NOT NULL DEFAULT 1,
    task_assignments INTEGER NOT NULL DEFAULT 1, approvals INTEGER NOT NULL DEFAULT 1,
    requests INTEGER NOT NULL DEFAULT 1, finance INTEGER NOT NULL DEFAULT 1,
    hr INTEGER NOT NULL DEFAULT 1, academy INTEGER NOT NULL DEFAULT 1, content INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(tenant_id,user_id)
);
CREATE TABLE IF NOT EXISTS leave_requests (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    start_date TEXT NOT NULL, end_date TEXT NOT NULL,
    leave_type TEXT NOT NULL DEFAULT 'annual', reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    approved_by INTEGER REFERENCES users(id), approved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')), updated_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);
CREATE TABLE IF NOT EXISTS payroll_runs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    month TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
    created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')), updated_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id,month)
);
CREATE TABLE IF NOT EXISTS payroll_items (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    payroll_run_id INTEGER NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    base_salary REAL NOT NULL DEFAULT 0, commission REAL NOT NULL DEFAULT 0, bonus REAL NOT NULL DEFAULT 0,
    deductions REAL NOT NULL DEFAULT 0, net_pay REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE(tenant_id,payroll_run_id,employee_id)
);
CREATE TABLE IF NOT EXISTS project_status_history (
    id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE, from_status TEXT, to_status TEXT NOT NULL,
    changed_by INTEGER REFERENCES users(id), reason TEXT, created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);
CREATE TABLE IF NOT EXISTS request_comments (
    id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id),
    body TEXT NOT NULL, internal INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);
CREATE TABLE IF NOT EXISTS deliverable_versions (
    id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    deliverable_id INTEGER NOT NULL REFERENCES project_deliverables(id) ON DELETE CASCADE, version INTEGER NOT NULL,
    file_id INTEGER REFERENCES files(id) ON DELETE SET NULL, notes TEXT, created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')), UNIQUE(tenant_id,deliverable_id,version)
);
CREATE TABLE IF NOT EXISTS conversation_messages (
    id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id),
    body TEXT NOT NULL, message_type TEXT NOT NULL DEFAULT 'text', created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);
CREATE TABLE IF NOT EXISTS file_versions (
    id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE, version INTEGER NOT NULL,
    storage_key TEXT NOT NULL, size_bytes INTEGER NOT NULL DEFAULT 0, checksum TEXT,
    uploaded_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL DEFAULT (TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    UNIQUE(tenant_id,file_id,version)
);
CREATE INDEX IF NOT EXISTS idx_leave_tenant_status ON leave_requests(tenant_id,status,start_date);
CREATE INDEX IF NOT EXISTS idx_payroll_tenant_month ON payroll_runs(tenant_id,month);
CREATE INDEX IF NOT EXISTS idx_payroll_items_run ON payroll_items(tenant_id,payroll_run_id);
CREATE INDEX IF NOT EXISTS idx_project_status_history ON project_status_history(tenant_id,project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_request_comments ON request_comments(tenant_id,request_id,created_at);
CREATE INDEX IF NOT EXISTS idx_deliverable_versions ON deliverable_versions(tenant_id,deliverable_id,version);
CREATE INDEX IF NOT EXISTS idx_conversation_messages ON conversation_messages(tenant_id,conversation_id,created_at);
CREATE INDEX IF NOT EXISTS idx_file_versions ON file_versions(tenant_id,file_id,version);

-- Expand the permission vocabulary used by the complete UI/API surface.
INSERT INTO permissions(code,description) VALUES
('employees.manage','Manage employee records'),('roles.manage','Manage roles and assignments'),('settings.manage','Manage tenant settings'),
('reports.view','View reports'),('finance.manage','Manage finance operations'),('hr.manage','Manage HR operations'),
('academy.manage','Manage academy'),('content.approve','Approve content'),('content.versions','Manage content versions'),
('communication.manage','Manage conversations'),('files.manage','Manage files'),('client.portal','Use client portal'),
('projects.financials','View project financials'),('requests.comment','Comment on requests'),('requests.update','Update requests'),
('approvals.manage','Manage approvals'),('payroll.manage','Manage payroll') ON CONFLICT(code) DO NOTHING;

-- Existing v13 content_versions needs an explicit workflow state.
