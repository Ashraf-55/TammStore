-- Codela OS v16: complete gap closure. Additive and tenant-scoped.
CREATE TABLE IF NOT EXISTS employee_contracts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE, contract_type TEXT NOT NULL DEFAULT 'employment',
 start_date TEXT NOT NULL, end_date TEXT, salary REAL NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT 'EGP', status TEXT NOT NULL DEFAULT 'active',
 notes TEXT, created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS employee_documents (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE, file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
 document_type TEXT NOT NULL, title TEXT NOT NULL, expires_at TEXT, status TEXT NOT NULL DEFAULT 'active', created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS employee_salary_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE, salary REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'EGP', effective_from TEXT NOT NULL, effective_to TEXT, reason TEXT, created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS employee_reporting_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE, manager_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
 effective_from TEXT NOT NULL, effective_to TEXT, reason TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS quote_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 quote_id INTEGER NOT NULL REFERENCES quotes(id) ON DELETE CASCADE, description TEXT NOT NULL, quantity REAL NOT NULL DEFAULT 1,
 unit_price REAL NOT NULL DEFAULT 0, tax_pct REAL NOT NULL DEFAULT 0, total REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS quote_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 quote_id INTEGER NOT NULL REFERENCES quotes(id) ON DELETE CASCADE, from_status TEXT, to_status TEXT NOT NULL,
 changed_by INTEGER REFERENCES users(id), note TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS payment_allocations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE, invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
 amount REAL NOT NULL CHECK(amount >= 0), created_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(tenant_id,payment_id,invoice_id)
);
CREATE TABLE IF NOT EXISTS refunds (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 payment_id INTEGER REFERENCES payments(id) ON DELETE SET NULL, invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
 amount REAL NOT NULL CHECK(amount > 0), reason TEXT, status TEXT NOT NULL DEFAULT 'pending', created_by INTEGER REFERENCES users(id), processed_at TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS credit_notes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL, note_number TEXT NOT NULL, amount REAL NOT NULL CHECK(amount > 0),
 reason TEXT, status TEXT NOT NULL DEFAULT 'draft', created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(tenant_id,note_number)
);
CREATE TABLE IF NOT EXISTS task_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE, from_status TEXT, to_status TEXT, event_type TEXT NOT NULL,
 user_id INTEGER REFERENCES users(id), payload TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS notification_deliveries (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 notification_id INTEGER REFERENCES notifications(id) ON DELETE CASCADE, channel TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
 attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, delivered_at TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS file_access_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id), action TEXT NOT NULL,
 ip_address TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS audit_entity_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL, related_type TEXT NOT NULL, related_id INTEGER NOT NULL,
 created_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(tenant_id,entity_type,entity_id,related_type,related_id)
);
CREATE TABLE IF NOT EXISTS workflow_definitions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 entity_type TEXT NOT NULL, name TEXT NOT NULL, config_json TEXT NOT NULL DEFAULT '{}', is_active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS workflow_transitions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 workflow_id INTEGER NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE, from_status TEXT, to_status TEXT NOT NULL,
 permission_code TEXT, sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS backup_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE, backup_type TEXT NOT NULL,
 storage_key TEXT, checksum TEXT, size_bytes INTEGER, status TEXT NOT NULL DEFAULT 'started', error TEXT,
 started_at TEXT NOT NULL DEFAULT (datetime('now')), finished_at TEXT
);
CREATE TABLE IF NOT EXISTS system_health_checks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE, component TEXT NOT NULL,
 status TEXT NOT NULL, latency_ms REAL, details TEXT, checked_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_employee_contracts ON employee_contracts(tenant_id,employee_id,status);
CREATE INDEX IF NOT EXISTS idx_employee_documents ON employee_documents(tenant_id,employee_id,expires_at);
CREATE INDEX IF NOT EXISTS idx_salary_history ON employee_salary_history(tenant_id,employee_id,effective_from);
CREATE INDEX IF NOT EXISTS idx_reporting_history ON employee_reporting_history(tenant_id,employee_id,effective_from);
CREATE INDEX IF NOT EXISTS idx_quote_items ON quote_items(tenant_id,quote_id);
CREATE INDEX IF NOT EXISTS idx_quote_events ON quote_events(tenant_id,quote_id,created_at);
CREATE INDEX IF NOT EXISTS idx_payment_allocations ON payment_allocations(tenant_id,payment_id,invoice_id);
CREATE INDEX IF NOT EXISTS idx_refunds ON refunds(tenant_id,status,created_at);
CREATE INDEX IF NOT EXISTS idx_credit_notes ON credit_notes(tenant_id,invoice_id,status);
CREATE INDEX IF NOT EXISTS idx_task_events ON task_events(tenant_id,task_id,created_at);
CREATE INDEX IF NOT EXISTS idx_notification_deliveries ON notification_deliveries(tenant_id,status,created_at);
CREATE INDEX IF NOT EXISTS idx_file_access ON file_access_log(tenant_id,file_id,created_at);
CREATE INDEX IF NOT EXISTS idx_audit_entity_links ON audit_entity_links(tenant_id,entity_type,entity_id);
CREATE INDEX IF NOT EXISTS idx_workflow_transitions ON workflow_transitions(tenant_id,workflow_id,from_status);
CREATE INDEX IF NOT EXISTS idx_health_checks ON system_health_checks(tenant_id,component,checked_at);
INSERT INTO permissions(code,description) VALUES
('employees.update','Update employee records'),('employees.documents','Manage employee documents'),('employees.contracts','Manage employee contracts'),
('tasks.assign','Assign tasks to project members'),('tasks.manage','Manage task workflow'),('deliverables.versions','Manage deliverable versions'),
('quotes.manage','Manage quotes'),('quotes.approve','Approve quotes'),('finance.refund','Manage refunds'),('finance.credit_note','Manage credit notes'),
('finance.reconcile','Reconcile payment allocations'),('notifications.manage','Manage notifications'),('files.access','Access linked files'),
('academy.assessments','Manage assessments'),('academy.certificates','Manage certificates'),('content.workflow','Manage content workflow'),
('workflows.manage','Manage workflow definitions'),('audit.view','View audit/activity timelines'),('system.health','View system health'),('backup.manage','Manage backup runs')
ON CONFLICT(code) DO NOTHING;
