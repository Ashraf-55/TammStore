-- Codela OS v24: DB-level Defense-in-Depth (P2).
-- SQLite cannot ALTER TABLE to add CHECK constraints to existing tables
-- without a full table rebuild, so these rules are enforced via triggers
-- instead. They are a second line of defense — the application layer
-- already enforces all of this; these exist so a bug or a future
-- direct-DB write can't silently corrupt data.

-- ---- Positive monetary values ----
CREATE TRIGGER IF NOT EXISTS trg_payments_amount_positive_ins
BEFORE INSERT ON payments
WHEN NEW.amount <= 0
BEGIN
    SELECT RAISE(ABORT, 'payments.amount must be positive');
END;
CREATE TRIGGER IF NOT EXISTS trg_payments_amount_positive_upd
BEFORE UPDATE ON payments
WHEN NEW.amount <= 0
BEGIN
    SELECT RAISE(ABORT, 'payments.amount must be positive');
END;

CREATE TRIGGER IF NOT EXISTS trg_invoices_totals_nonneg_ins
BEFORE INSERT ON invoices
WHEN NEW.subtotal < 0 OR NEW.total < 0 OR NEW.amount_paid < 0
BEGIN
    SELECT RAISE(ABORT, 'invoice monetary fields must not be negative');
END;
CREATE TRIGGER IF NOT EXISTS trg_invoices_totals_nonneg_upd
BEFORE UPDATE ON invoices
WHEN NEW.subtotal < 0 OR NEW.total < 0 OR NEW.amount_paid < 0
BEGIN
    SELECT RAISE(ABORT, 'invoice monetary fields must not be negative');
END;

CREATE TRIGGER IF NOT EXISTS trg_quote_items_nonneg_ins
BEFORE INSERT ON quote_items
WHEN NEW.quantity <= 0 OR NEW.unit_price < 0 OR NEW.total < 0
BEGIN
    SELECT RAISE(ABORT, 'quote_items.quantity must be positive and prices must not be negative');
END;
CREATE TRIGGER IF NOT EXISTS trg_quote_items_nonneg_upd
BEFORE UPDATE ON quote_items
WHEN NEW.quantity <= 0 OR NEW.unit_price < 0 OR NEW.total < 0
BEGIN
    SELECT RAISE(ABORT, 'quote_items.quantity must be positive and prices must not be negative');
END;

CREATE TRIGGER IF NOT EXISTS trg_employees_hourly_cost_nonneg_ins
BEFORE INSERT ON employees
WHEN NEW.hourly_cost < 0
BEGIN
    SELECT RAISE(ABORT, 'employees.hourly_cost must not be negative');
END;
CREATE TRIGGER IF NOT EXISTS trg_employees_hourly_cost_nonneg_upd
BEFORE UPDATE ON employees
WHEN NEW.hourly_cost < 0
BEGIN
    SELECT RAISE(ABORT, 'employees.hourly_cost must not be negative');
END;

-- ---- Task <-> Milestone <-> Project consistency ----
CREATE TRIGGER IF NOT EXISTS trg_tasks_milestone_project_ins
BEFORE INSERT ON tasks
WHEN NEW.milestone_id IS NOT NULL AND NEW.milestone_id NOT IN (
    SELECT id FROM project_milestones WHERE id = NEW.milestone_id AND project_id = NEW.project_id
)
BEGIN
    SELECT RAISE(ABORT, 'tasks.milestone_id must belong to the same project as the task');
END;
CREATE TRIGGER IF NOT EXISTS trg_tasks_milestone_project_upd
BEFORE UPDATE ON tasks
WHEN NEW.milestone_id IS NOT NULL AND NEW.milestone_id NOT IN (
    SELECT id FROM project_milestones WHERE id = NEW.milestone_id AND project_id = NEW.project_id
)
BEGIN
    SELECT RAISE(ABORT, 'tasks.milestone_id must belong to the same project as the task');
END;

-- ---- Deliverable <-> Milestone <-> Project consistency ----
CREATE TRIGGER IF NOT EXISTS trg_deliverables_milestone_project_ins
BEFORE INSERT ON project_deliverables
WHEN NEW.milestone_id IS NOT NULL AND NEW.milestone_id NOT IN (
    SELECT id FROM project_milestones WHERE id = NEW.milestone_id AND project_id = NEW.project_id
)
BEGIN
    SELECT RAISE(ABORT, 'project_deliverables.milestone_id must belong to the same project as the deliverable');
END;
CREATE TRIGGER IF NOT EXISTS trg_deliverables_milestone_project_upd
BEFORE UPDATE ON project_deliverables
WHEN NEW.milestone_id IS NOT NULL AND NEW.milestone_id NOT IN (
    SELECT id FROM project_milestones WHERE id = NEW.milestone_id AND project_id = NEW.project_id
)
BEGIN
    SELECT RAISE(ABORT, 'project_deliverables.milestone_id must belong to the same project as the deliverable');
END;
