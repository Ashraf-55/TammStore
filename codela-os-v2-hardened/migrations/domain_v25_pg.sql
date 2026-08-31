-- Codela OS v25 (PostgreSQL): Audit Log Immutability (P2).
-- Same reasoning as the SQLite version: UPDATE is blocked unconditionally;
-- DELETE is left alone because of the tenant ON DELETE CASCADE relationship
-- (see domain_v25.sql for the full explanation).
CREATE OR REPLACE FUNCTION block_audit_log_update() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log rows are immutable and cannot be modified';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log;
CREATE TRIGGER trg_audit_log_immutable
BEFORE UPDATE ON audit_log
FOR EACH ROW EXECUTE FUNCTION block_audit_log_update();
