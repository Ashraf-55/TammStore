-- Codela OS v17: production integrity and idempotency closure.
CREATE TABLE IF NOT EXISTS api_idempotency_keys (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
 scope TEXT NOT NULL,
 idem_key TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 status_code INTEGER,
 response_json TEXT,
 created_at TEXT NOT NULL DEFAULT (datetime('now')),
 expires_at TEXT,
 UNIQUE(tenant_id, scope, idem_key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expiry ON api_idempotency_keys(expires_at);

CREATE TABLE IF NOT EXISTS webhook_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
 provider TEXT NOT NULL,
 event_id TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'received',
 attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT,
 processed_at TEXT,
 created_at TEXT NOT NULL DEFAULT (datetime('now')),
 UNIQUE(provider,event_id)
);
CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events(status,created_at);

CREATE TABLE IF NOT EXISTS payment_intents (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
 idempotency_key TEXT NOT NULL,
 amount REAL NOT NULL CHECK(amount > 0),
 status TEXT NOT NULL DEFAULT 'created',
 provider TEXT,
 provider_reference TEXT,
 created_at TEXT NOT NULL DEFAULT (datetime('now')),
 UNIQUE(tenant_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_payment_intents_invoice ON payment_intents(tenant_id,invoice_id,status);

CREATE INDEX IF NOT EXISTS idx_tasks_tenant_project_status ON tasks(tenant_id,project_id,status,created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_tenant_assignee_status ON tasks(tenant_id,assignee_id,status,created_at);
CREATE INDEX IF NOT EXISTS idx_projects_tenant_client_status ON projects(tenant_id,client_id,status,created_at);
CREATE INDEX IF NOT EXISTS idx_requests_tenant_project_status ON requests(tenant_id,project_id,status,created_at);
CREATE INDEX IF NOT EXISTS idx_invoices_tenant_client_status ON invoices(tenant_id,client_id,status,due_date);
CREATE INDEX IF NOT EXISTS idx_payments_tenant_invoice_paid ON payments(tenant_id,invoice_id,paid_at);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_entity ON audit_log(tenant_id,entity_type,entity_id,created_at);

-- New-write integrity triggers. Existing legacy rows are intentionally not rewritten.
CREATE TRIGGER IF NOT EXISTS trg_project_member_tenant
BEFORE INSERT ON project_members
WHEN (SELECT tenant_id FROM employees WHERE id=NEW.employee_id) IS NULL
  OR (SELECT tenant_id FROM employees WHERE id=NEW.employee_id) <> NEW.tenant_id
  OR (SELECT tenant_id FROM projects WHERE id=NEW.project_id) <> NEW.tenant_id
BEGIN SELECT RAISE(ABORT,'cross_tenant_project_member'); END;

CREATE TRIGGER IF NOT EXISTS trg_task_project_tenant
BEFORE INSERT ON tasks
WHEN NEW.project_id IS NOT NULL AND (SELECT tenant_id FROM projects WHERE id=NEW.project_id) <> NEW.tenant_id
BEGIN SELECT RAISE(ABORT,'cross_tenant_task_project'); END;

CREATE TRIGGER IF NOT EXISTS trg_task_assignee_tenant
BEFORE INSERT ON tasks
WHEN NEW.assignee_id IS NOT NULL AND (SELECT tenant_id FROM users WHERE id=NEW.assignee_id) <> NEW.tenant_id
BEGIN SELECT RAISE(ABORT,'cross_tenant_task_assignee'); END;

CREATE TRIGGER IF NOT EXISTS trg_invoice_client_tenant
BEFORE INSERT ON invoices
WHEN NEW.client_id IS NOT NULL AND (SELECT tenant_id FROM clients WHERE id=NEW.client_id) <> NEW.tenant_id
BEGIN SELECT RAISE(ABORT,'cross_tenant_invoice_client'); END;

CREATE TRIGGER IF NOT EXISTS trg_invoice_project_tenant
BEFORE INSERT ON invoices
WHEN NEW.project_id IS NOT NULL AND (SELECT tenant_id FROM projects WHERE id=NEW.project_id) <> NEW.tenant_id
BEGIN SELECT RAISE(ABORT,'cross_tenant_invoice_project'); END;

CREATE TRIGGER IF NOT EXISTS trg_payment_invoice_tenant
BEFORE INSERT ON payments
WHEN (SELECT tenant_id FROM invoices WHERE id=NEW.invoice_id) <> NEW.tenant_id
BEGIN SELECT RAISE(ABORT,'cross_tenant_payment_invoice'); END;

CREATE TRIGGER IF NOT EXISTS trg_payment_positive
BEFORE INSERT ON payments
WHEN NEW.amount <= 0
BEGIN SELECT RAISE(ABORT,'payment_amount_must_be_positive'); END;

CREATE TRIGGER IF NOT EXISTS trg_allocation_tenant
BEFORE INSERT ON payment_allocations
WHEN (SELECT tenant_id FROM payments WHERE id=NEW.payment_id) <> NEW.tenant_id
   OR (SELECT tenant_id FROM invoices WHERE id=NEW.invoice_id) <> NEW.tenant_id
BEGIN SELECT RAISE(ABORT,'cross_tenant_payment_allocation'); END;

CREATE TRIGGER IF NOT EXISTS trg_allocation_total
BEFORE INSERT ON payment_allocations
WHEN NEW.amount > (
  (SELECT amount FROM payments WHERE id=NEW.payment_id)
  - COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE payment_id=NEW.payment_id),0)
)
OR NEW.amount > (
  (SELECT total FROM invoices WHERE id=NEW.invoice_id)
  - COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE invoice_id=NEW.invoice_id),0)
)
BEGIN SELECT RAISE(ABORT,'payment_allocation_exceeds_balance'); END;
