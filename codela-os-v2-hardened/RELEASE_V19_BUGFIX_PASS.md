# v19 — Bug-fix pass

This pass focused on finding and fixing real, reproducible defects by
actually *running* the app and its full local test suite (migrations,
seed, `smoke_test.py`, and every `*_test.py`/`*_check.py`/`*_gate.py`
script in the repo) rather than a read-through alone.

## Bugs found and fixed

1. **`routes/billing_routes.py` was an empty file (0 bytes).** It is
   imported by `app.py`, `auth.py` (`/auth/register`, `/auth/invite`),
   and `routes/crm_routes.py` (`create_lead`) — the app could not start
   at all. Rebuilt the full SaaS Subscription Engine: public plan
   catalog, `GET/POST /billing/subscription` + `/subscribe` + `/cancel`,
   `GET /billing/invoices`, `POST /billing/check-trials`, the
   `check_usage_limit()` / `create_trial_subscription()` helpers other
   modules import, and a mock/live `PaymentGatewayAdapter` following the
   same pattern already used in `routes/communication_routes.py` and
   `routes/publish_routes.py`.

2. **`routes/enterprise_routes.py` did not exist**, despite being
   imported by `app.py` and required by `domain_frontend_e2e_check.py`
   (which asserts `/search`, `/reports/overview`, and `/client/dashboard`
   are present). Rebuilt it: global search across
   clients/projects/tasks/requests/invoices, `/reports/overview` +
   `/reports/projects` (KPI + per-project profitability, consumed by the
   Ops dashboard in `frontend/app.js`), and the client-portal read model
   (`/client/dashboard`, `/client/deliverables` + approval action,
   `/client/invoices`).

3. **Tenant suspension was never enforced at login.** `check-trials` (in
   the billing engine above) sets `tenants.is_active=0` once a trial
   expires, but neither `auth.login()` nor `auth.login_required` ever
   checked `tenants.is_active` — only `users.is_active`. A suspended
   workspace's users could still log in and use the product normally.
   Both now return `403 tenant_suspended` for a suspended tenant.

4. **Duplicate imports of `tenant_resource_exists`** (same name imported
   twice from `database` in the same `from ... import` line) in
   `routes/finance_routes.py`, `routes/projects_routes.py`, and
   `routes/crm_routes.py`. Harmless at runtime but a lint failure and a
   sign of a bad merge; cleaned up.

5. **`migrations/runner.py.tmp`** — a stray, empty temp file committed by
   mistake alongside the real `migrations/runner.py`. Removed.

## Verified locally (this pass)

- `python3 -m py_compile` on all backend files: PASS
- Fresh SQLite `manage.py migrate` (v18) + `seed.py`: PASS
- `smoke_test.py` (26 checks across Auth, CRM, Automation, Follow-up,
  Communication, Finance/Commission, Invoicing, and the now-working SaaS
  Billing engine): PASS
- `domain_frontend_e2e_check.py` (frontend/backend route contract,
  including the new enterprise layer): PASS
- `hardening_static_test.py`, `production_check.py`,
  `security_regression_test.py`, `tenant_idor_matrix_test.py`,
  `production_integrity_test.py`, `production_final_gate.py`,
  `concurrency_test.py`, `backup_restore_test.py`,
  `runtime_e2e_test.py`: all PASS
- AST-level sweep of every `.py` file for duplicate imports, duplicate
  top-level function definitions, and duplicate/colliding Flask routes;
  cross-checked the one apparent collision (`GET /notifications` defined
  in both `users_routes.py` and `completion_routes.py`) against the
  actual running `app.url_map` — confirmed **not** a real collision,
  since `users_bp` is mounted under `/api/users` and resolves to a
  different final path (`/api/users/notifications` vs
  `/api/notifications`).

## Still requires real staging infrastructure

Unchanged from `docs/SECURITY_NOTES.md` — PostgreSQL runtime/migration
testing, Redis multi-worker concurrency testing, load/soak testing, a
real backup/restore disaster-recovery exercise, and real payment
gateway / WhatsApp / email / SMS / social / AI provider integrations
were not exercised here (no network access in this environment).
