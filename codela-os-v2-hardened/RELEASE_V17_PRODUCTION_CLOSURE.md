# Codela OS v17 — Production Closure

This release closes the remaining platform-integrity gaps after the domain and workflow refactors.

## Added
- Tenant-scoped API idempotency store.
- Webhook event deduplication ledger.
- Payment intents for retry-safe payment initiation.
- Database-level cross-tenant integrity triggers for project members, tasks, invoices, payments, and allocations.
- Positive-payment and payment-allocation balance guards.
- Production indexes for common tenant/project/client/task/request/invoice/audit queries.
- Dependency-light production integrity test.
- Updated domain/frontend contract check for migration v17.

## Verification
- Fresh SQLite migration to v17: PASS
- Migration idempotency: PASS
- Cross-tenant DB trigger gate: PASS
- Static hardening: PASS
- Production configuration primitives: PASS
- Domain/frontend contract: PASS
- Frontend syntax: PASS
- Python compilation: PASS

## Runtime E2E note
The current build environment does not include Flask runtime dependencies and has no package-network access, so the HTTP application test suite cannot be executed here. The repository includes `security_regression_test.py` for execution in the real deployment environment after installing `requirements.txt`.
