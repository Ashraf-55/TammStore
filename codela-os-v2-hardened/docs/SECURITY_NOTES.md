# Security & Hardening Notes

Consolidated summary of the current security posture. Replaces the earlier
`COMPREHENSIVE_SECURITY_REVIEW.md` / `FINAL_SECURITY_FIXES.md` /
`FINAL_SECURITY_FIXES_V3.md` snapshots, which tracked the same work across
several in-progress passes and had drifted out of sync with the code
(e.g. referencing migration v8 when the schema is now at v12).

## Current protections

- **Auth**: JWT access tokens + rotating refresh tokens (HttpOnly Secure
  cookie in production, `Authorization: Bearer` in development), revocation
  list for logout/logout-all, session listing/revocation, TOTP-based 2FA
  (RFC 6238) with bounded pending-confirmation attempts and expiry.
- **Multi-tenancy**: every tenant-owned table is scoped by `tenant_id`;
  foreign-key references supplied by API clients are validated against the
  caller's tenant via `tenant_resource_exists()`. Covered by
  `tenant_idor_matrix_test.py` and `security_regression_test.py`.
- **Rate limiting**: Redis-backed in production (fails closed if Redis is
  unavailable), in-memory sliding window in development.
- **CSRF**: separate readable CSRF cookie + `X-CSRF-Token` header required
  for cookie-authenticated state changes.
- **Headers**: CSP (`script-src-attr 'none'`, no inline `<script>`), HSTS in
  production, `X-Content-Type-Options`, `X-Frame-Options`, COOP/CORP,
  restrictive `Permissions-Policy`.
- **Secrets**: platform integration tokens encrypted with Fernet
  (`CODELA_ENCRYPTION_KEY`); production refuses plaintext integration
  secrets and refuses to boot without `CODELA_SECRET_KEY`,
  `CODELA_ENCRYPTION_KEY`, `REDIS_URL`, and `CODELA_PLATFORM_ADMIN_EMAILS`.
- **Billing/jobs**: subscription mutations require `Idempotency-Key` in
  production; background jobs use a lease token + heartbeat so stale jobs
  respect `max_attempts` instead of being double-picked-up.
- **Mock vs. live integrations**: payment, WhatsApp/email/SMS, and social
  publishing adapters fail closed in production when a real provider
  credential isn't configured — they never silently report a mock send as a
  real one. Live implementations are marked with `# TODO live:` comments in
  `routes/billing_routes.py`, `routes/communication_routes.py`, and
  `routes/publish_routes.py` — expected, not something to "clean up".

## Verified locally (this pass)

- `python3 -m py_compile` on all 42 backend files: PASS
- `hardening_static_test.py`: PASS
- `production_check.py`: PASS
- `tenant_idor_matrix_test.py`: PASS
- `security_regression_test.py` (tenant isolation, FK IDOR, refresh
  rotation, logout revocation, validation, security headers): PASS
- `seed.py` + `smoke_test.py` (Auth, CRM, Automation, Follow-up,
  Communication, Finance/Commission, Invoicing, SaaS Billing engines,
  end-to-end against a real Flask test client): PASS

## Bugs found and fixed in this pass

These were functional bugs blocking a working run, not just style issues:

1. `auth.py` shadowed the `datetime` module with `from datetime import
   datetime`, so every `datetime.datetime.utcnow()` call raised
   `AttributeError` — login, session issuance, 2FA, and logout were all
   broken. Fixed by using the imported `datetime`/`timedelta` names directly.
2. `auth.py` used `os.getenv(...)` in `_cookie_auth_enabled()` without
   importing `os`.
3. `routes/billing_routes.py`'s `PaymentGatewayAdapter.charge()` had no
   development mock path (unlike every other adapter in the codebase),
   so any subscribe/upgrade call in development failed a `CHECK` constraint.
4. The billing plan catalog (`trial`/`starter`/`pro`/`enterprise`) was only
   inserted by the demo `seed.py` script, not by the schema/migrations. Any
   deployment that ran migrations without the demo seeder had an empty
   `plans` table, so every new tenant's trial subscription silently failed
   to attach and all lead/user creation was denied with 402. Moved the plan
   catalog into migration 12 as system reference data.
5. `smoke_test.py` hardcoded the login password `"password123"` (11 chars),
   but the app enforces a 12-character minimum — the script could never
   have passed as shipped. It now reads `CODELA_SEED_PASSWORD` from the
   environment, same as `seed.py`.
6. `security_regression_test.py` reused the loop variable name `path`,
   shadowing the temp-database `path` set earlier in the same function, so
   the final cleanup `os.unlink(path)` tried to delete a URL string instead
   of the database file.
7. **The frontend was never actually served anywhere.** `frontend/index.html`
   / `app.js` use a relative `/api` path (same-origin assumption), the
   README told you to run them on a separate `http.server :8080`, and the
   production `docker-compose.yml` only runs the `api` container — no
   service in the whole stack ever served the frontend files. Fixed by
   having Flask serve `frontend/index.html` and `frontend/app.js` directly
   at `/` and `/app.js`, so the app is genuinely one deployable unit and the
   frontend's same-origin assumption is actually true. Verified end-to-end
   with a real headless-browser login (`founder@codela.com`) through to the
   dashboard and the CRM leads list.

## Still requires real staging infrastructure

- PostgreSQL runtime and migration testing (only exercised against SQLite
  here — no network access in this environment).
- Redis multi-worker concurrency testing.
- Load/soak testing.
- Backup/restore disaster-recovery exercise (see `BACKUP_RESTORE_RUNBOOK.md`).
- Real payment gateway and signed webhook implementation/testing.
- Real WhatsApp/email/SMS/social/AI provider integrations.
