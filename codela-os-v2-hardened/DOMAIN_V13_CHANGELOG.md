# Codela OS — Domain Foundation v13

## What changed

This build moves the application from loosely connected modules toward a shared operating model without deleting the existing production/security foundations.

### Identity & Organization
- Added employees, departments, positions and employee status history.
- Added tenant-scoped RBAC tables: roles, permissions, role_permissions, user_roles.
- Kept the legacy `users.role` field for compatibility.

### CRM / Clients
- Added client contacts, client users and addresses.
- Client users can now access a tenant-safe client portal read model.

### Projects / Delivery
- Added project members, milestones, deliverables, approvals and activities.
- Project creation automatically adds the project manager as a project member when an Employee profile exists.
- Tasks now carry milestone, creator, type and estimation fields.
- Added task time entries and project cost linkage.

### Requests
- Added requester identity/type, project linkage, assignment and resolution fields.
- Added explicit assign/resolve endpoints.
- Added client-originated request creation with strict project ownership checks.

### Finance
- Added project budgets, project costs, expenses and quotes.
- Added project financial summary endpoint calculating revenue, labor cost, other costs, profit and margin.

### Files / Communication
- Added tenant-scoped file records and entity links.
- Added conversation/participant foundations and message attachments.

### Academy
- Added student and instructor entities, course-instructor mapping, attendance and assessment tables.

### Content
- Added briefs, content versions, approvals and assets.

## Compatibility

- No legacy table is dropped.
- Migration is additive and versioned as `13`.
- Existing authentication, sessions, audit logging, automation engine, billing and security hardening remain in place.
- Existing legacy routes continue to work; new domain routes are additive.

## Validation performed

- Python syntax compilation passed for the project.
- Fresh SQLite database successfully initialized through migration v13.
- Static hardening checks passed.
- Production configuration checks passed.
- Full Flask runtime/API tests could not be executed in the build environment because Flask is not installed there.
