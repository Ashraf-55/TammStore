-- Codela OS v25: Audit Log Immutability (P2).
-- No application route ever updates or deletes audit_log rows (verified: only
-- INSERT via write_audit() and SELECT for display). This adds a DB-level
-- guarantee so a bug or a future direct-DB script can't quietly rewrite
-- history either.
--
-- UPDATE is blocked unconditionally — there is no legitimate reason to ever
-- edit an audit entry after it's written.
--
-- DELETE is intentionally NOT blocked here: audit_log.tenant_id has
-- ON DELETE CASCADE, so deleting a tenant must be able to cascade-delete its
-- audit rows. A blanket delete-blocking trigger would also block that
-- cascade and silently break tenant deletion. Real DELETE protection needs
-- to distinguish "cascade from tenant deletion" from "someone deleting rows
-- directly" — that requires the Tenant Deletion lifecycle (P5, not yet
-- built) to be designed first, e.g. archiving audit rows before a tenant is
-- removed. Tracked as a follow-up, not silently closed here.
CREATE TRIGGER IF NOT EXISTS trg_audit_log_immutable
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log rows are immutable and cannot be modified');
END;
