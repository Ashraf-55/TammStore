# Codela OS v16 — Complete Gap Closure

This release closes the remaining domain gaps identified after v15/v16 review. It is additive and preserves legacy tables and data.

## Closed areas

- Employee lifecycle: update/status history, contracts, documents, reporting history.
- Project/task lifecycle: project-member-only assignment, task status events, deliverable versioning.
- Finance: quote items/events, quote lifecycle, payment allocations, refunds, credit notes.
- Client portal: client messaging with project-scoped tenant checks, notifications/read state.
- Communication/files: file versioning and access audit.
- Academy: assessment attempt endpoint with tenant-scoped student/assessment checks.
- Workflow engine foundation: tenant-scoped workflow definitions/transitions.
- Audit/activity timeline endpoint.
- System health checks persisted for tenant diagnostics.
- Backup control-plane records for scheduled/external backup integrations; no fake cloud backup is claimed.
- Frontend Operations Control Center now exposes quotes, user notifications, and system health.
- Expanded permission vocabulary and tenant allow-listing for all new tables.

## Migration

Schema migration version: **16**.

- SQLite: `migrations/domain_v16.sql`
- PostgreSQL: `migrations/domain_v16_pg.sql`
- Migration runner is idempotent and remains additive.

## Important integrity rules

1. Every new resource is tenant-scoped.
2. Task assignment requires the target employee to be a member of the same project.
3. Quote/deal/project/client/payment/invoice/file references are validated against the active tenant.
4. Client portal queries are restricted to the authenticated client relationship.
5. File access is explicitly logged.
6. Audit/activity is read-only from the UI/API surface.

## Verification performed in this build environment

- `python -m compileall -q .` — PASS
- Fresh SQLite migration to v16 — PASS
- Migration rerun/idempotency — PASS
- Required v16 tables — PASS
- Static hardening checks — PASS
- Production configuration checks — PASS
- Frontend `node --check frontend/app.js` — PASS

The full Flask HTTP/IDOR suite could not be executed in this build environment because Flask dependencies are not installed. Those tests must be run in the project's normal dependency environment before production deployment.
