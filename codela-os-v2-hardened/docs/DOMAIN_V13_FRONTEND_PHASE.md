# Codela OS v13 — Frontend & Domain Workflow Phase

Implemented after the v13 domain foundation.

## Frontend
- Added People & Organization screen backed by `/employees` and `/departments`.
- Enhanced Clients screen with Client → Contacts → Projects drill-down.
- Enhanced Project detail with project team, milestones, deliverables, financial summary, and tasks.
- Added Client Portal navigation for users linked through `client_users`.
- Added Client Portal project overview and request creation.
- Enhanced Requests screen with client/project context and domain resolve action.

## Contract checks
- `domain_frontend_e2e_check.py` validates frontend/backend endpoint contracts, route coverage, and a clean v13 migration/schema smoke test without requiring Flask.
- `node --check frontend/app.js` passes.
- `hardening_static_test.py` passes.
- `production_check.py` passes.

## Runtime note
Full Flask HTTP E2E execution requires the pinned Python dependencies from `requirements.txt`. The current execution sandbox has no network access and Flask is not preinstalled, so dependency installation could not be completed here. No claim of live HTTP E2E execution is made.
