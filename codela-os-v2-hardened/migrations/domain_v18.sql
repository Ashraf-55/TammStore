-- Codela OS v18: final production hardening.
-- Additive only. Strengthens write-time integrity, idempotency and operational indexes.
CREATE INDEX IF NOT EXISTS idx_jobs_claim_v18 ON jobs(status,run_after,lease_until,id);
CREATE INDEX IF NOT EXISTS idx_messages_tenant_created_v18 ON messages(tenant_id,created_at);
CREATE INDEX IF NOT EXISTS idx_files_tenant_created_v18 ON files(tenant_id,created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_tenant_user_read_v18 ON notifications(tenant_id,user_id,is_read,created_at);
CREATE INDEX IF NOT EXISTS idx_finance_transactions_tenant_date_v18 ON finance_transactions(tenant_id,date,created_at);

-- Payment amount and allocation updates must remain tenant-safe and cannot
-- retroactively over-allocate an invoice/payment.
CREATE TRIGGER IF NOT EXISTS trg_payment_tenant_update
BEFORE UPDATE OF tenant_id,invoice_id,amount ON payments
WHEN (SELECT tenant_id FROM invoices WHERE id=NEW.invoice_id) <> NEW.tenant_id OR NEW.amount <= 0
BEGIN SELECT RAISE(ABORT,'invalid_payment_update'); END;

CREATE TRIGGER IF NOT EXISTS trg_allocation_tenant_update
BEFORE UPDATE OF tenant_id,payment_id,invoice_id,amount ON payment_allocations
WHEN (SELECT tenant_id FROM payments WHERE id=NEW.payment_id) <> NEW.tenant_id
  OR (SELECT tenant_id FROM invoices WHERE id=NEW.invoice_id) <> NEW.tenant_id
  OR NEW.amount <= 0
  OR NEW.amount > ((SELECT amount FROM payments WHERE id=NEW.payment_id) - COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE payment_id=NEW.payment_id AND id<>NEW.id),0))
  OR NEW.amount > ((SELECT total FROM invoices WHERE id=NEW.invoice_id) - COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE invoice_id=NEW.invoice_id AND id<>NEW.id),0))
BEGIN SELECT RAISE(ABORT,'invalid_payment_allocation_update'); END;

CREATE TRIGGER IF NOT EXISTS trg_allocation_tenant_delete
BEFORE DELETE ON payment_allocations
WHEN (SELECT tenant_id FROM payments WHERE id=OLD.payment_id) <> OLD.tenant_id
  OR (SELECT tenant_id FROM invoices WHERE id=OLD.invoice_id) <> OLD.tenant_id
BEGIN SELECT RAISE(ABORT,'invalid_payment_allocation_delete'); END;

-- Prevent negative/over-collected invoice balances at the database edge.
CREATE TRIGGER IF NOT EXISTS trg_invoice_amount_paid_update
BEFORE UPDATE OF amount_paid,total ON invoices
WHEN NEW.amount_paid < 0 OR NEW.amount_paid > NEW.total + 0.000001
BEGIN SELECT RAISE(ABORT,'invalid_invoice_amount_paid'); END;

-- Explicit API idempotency records are tenant-scoped; keep hashes immutable.
CREATE TRIGGER IF NOT EXISTS trg_idempotency_immutable
BEFORE UPDATE OF tenant_id,scope,idem_key,request_hash ON api_idempotency_keys
BEGIN SELECT RAISE(ABORT,'idempotency_record_immutable'); END;

-- Webhook identity is provider + event id; payload hash cannot silently change.
CREATE TRIGGER IF NOT EXISTS trg_webhook_identity_immutable
BEFORE UPDATE OF provider,event_id,payload_hash ON webhook_events
BEGIN SELECT RAISE(ABORT,'webhook_identity_immutable'); END;
