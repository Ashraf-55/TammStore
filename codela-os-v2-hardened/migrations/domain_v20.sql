-- Codela OS v20: Invitation System.
-- Additive only. Replaces the old "/auth/invite creates an active user with a
-- temp password returned in the API response" pattern with a proper
-- pending -> accept lifecycle: an invitation carries a hashed, expiring,
-- single-use token, and no `users` row is created until the invitee accepts.
CREATE TABLE IF NOT EXISTS invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    name TEXT,
    role TEXT NOT NULL,
    invited_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    token_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','revoked','expired')),
    expires_at TEXT NOT NULL,
    accepted_at TEXT,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_invitations_token_hash ON invitations(token_hash);
CREATE INDEX IF NOT EXISTS idx_invitations_tenant_email_status ON invitations(tenant_id, email, status);
