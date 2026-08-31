-- Codela OS v14: operational workflow completion
-- Additive only. No destructive changes.
CREATE INDEX IF NOT EXISTS idx_requests_project ON requests(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_requests_assigned ON requests(tenant_id, assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_tasks_milestone ON tasks(tenant_id, milestone_id);
CREATE INDEX IF NOT EXISTS idx_invoices_project_status ON invoices(tenant_id, project_id, status);
CREATE INDEX IF NOT EXISTS idx_payments_tenant_invoice ON payments(tenant_id, invoice_id);
CREATE INDEX IF NOT EXISTS idx_project_activities_event ON project_activities(tenant_id, project_id, event_type, created_at);
