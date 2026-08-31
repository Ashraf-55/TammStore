# Codela OS — v14 Operational Workflow Phase

This release completes the next operational layer on top of the v13 domain foundation.

## Implemented

- Won Deal -> delivery Project handoff (idempotent by tenant/client/name)
- Project workspace read model aggregating members, milestones, deliverables, tasks, requests, approvals and financials
- Project member assignment with employee membership validation
- Task assignment restricted to project members
- Task completion/assignment domain events
- Request assignment that can attach a request to the client's Project and create/reuse a linked Task
- Client portal request -> selected Project -> Request workflow
- Project budgets and project expenses
- Time entry -> Project Cost integration (existing endpoint retained)
- Project invoice creation from the project UI for finance roles
- Deliverable approval lookup and decision workflow
- Employee/Position/Workspace user selectors for operational UI
- Migration v14 with additive indexes only

## Intentionally preserved

- Authentication, 2FA, tenant isolation foundation, audit logging, billing/subscription, automation engine and legacy tables.
- No destructive database migration.

## Validation

- JavaScript syntax check
- Python compile/static checks
- Fresh SQLite migration through v14
- Existing security/hardening/static checks where the local runtime dependencies permit them
