-- Codela OS v24 (PostgreSQL): DB-level Defense-in-Depth (P2).
-- Postgres supports real CHECK constraints for single-table rules; cross-table
-- consistency (milestone must belong to the same project) still needs triggers.

-- ---- Positive monetary values ----
ALTER TABLE payments ADD CONSTRAINT chk_payments_amount_positive CHECK (amount > 0);
ALTER TABLE invoices ADD CONSTRAINT chk_invoices_totals_nonneg CHECK (subtotal >= 0 AND total >= 0 AND amount_paid >= 0);
ALTER TABLE quote_items ADD CONSTRAINT chk_quote_items_nonneg CHECK (quantity > 0 AND unit_price >= 0 AND total >= 0);
ALTER TABLE employees ADD CONSTRAINT chk_employees_hourly_cost_nonneg CHECK (hourly_cost >= 0);

-- ---- Task <-> Milestone <-> Project consistency ----
CREATE OR REPLACE FUNCTION chk_task_milestone_project() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.milestone_id IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM project_milestones WHERE id = NEW.milestone_id AND project_id = NEW.project_id) THEN
            RAISE EXCEPTION 'tasks.milestone_id must belong to the same project as the task';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tasks_milestone_project ON tasks;
CREATE TRIGGER trg_tasks_milestone_project
BEFORE INSERT OR UPDATE ON tasks
FOR EACH ROW EXECUTE FUNCTION chk_task_milestone_project();

-- ---- Deliverable <-> Milestone <-> Project consistency ----
CREATE OR REPLACE FUNCTION chk_deliverable_milestone_project() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.milestone_id IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM project_milestones WHERE id = NEW.milestone_id AND project_id = NEW.project_id) THEN
            RAISE EXCEPTION 'project_deliverables.milestone_id must belong to the same project as the deliverable';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_deliverables_milestone_project ON project_deliverables;
CREATE TRIGGER trg_deliverables_milestone_project
BEFORE INSERT OR UPDATE ON project_deliverables
FOR EACH ROW EXECUTE FUNCTION chk_deliverable_milestone_project();
