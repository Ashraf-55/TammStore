# Codela OS Production Runbook

## Pre-deploy

- Provision PostgreSQL and a dedicated application database user.
- Set `CODELA_ENV=production`.
- Set a 32+ character random `CODELA_SECRET_KEY`.
- Set `CODELA_CORS_ORIGINS` to exact HTTPS frontend origins.
- Set `CODELA_METRICS_TOKEN`.
- Set `CODELA_TRUSTED_PROXY_COUNT` only when the proxy chain is known.
- Store secrets in a secret manager or protected environment, never Git.

## Deploy

1. Take a database backup.
2. Run `python manage.py migrate`.
3. Start the API with Gunicorn.
4. Start at least one worker.
5. Check `/api/health` and `/api/ready`.
6. Run authentication, tenant-isolation and job smoke tests.

## Rollback

- Roll back application code first only if the database schema remains backward compatible.
- Do not downgrade destructive migrations without a verified backup and an explicit maintenance window.
- Revert the deployment and restore the database only when required.

## Secret rotation

Set `CODELA_SECRET_KEY_PREVIOUS` to the old key, deploy, then rotate clients/sessions as needed. After the overlap window, remove the previous key.

## Backups

- SQLite: `scripts/backup_sqlite.sh` for development/small deployments.
- PostgreSQL: `scripts/backup_postgres.sh` for PostgreSQL environments.
- Store backups outside the application host and test restoration regularly.

## Monitoring

Alert on:
- readiness failures
- HTTP 5xx rate
- sustained 429 rate
- dead jobs
- database connection failures
- authentication failures
- unusual cross-tenant authorization failures

## Important

The in-process rate limiter is only a local safety net. Multi-instance deployments should enforce rate limiting at an API gateway/load balancer or use a shared store such as Redis.


## Mandatory deployment invariants
- Run `docker compose run --rm migrate` (or the dedicated `migrate` service) before API/worker startup; application containers never run migrations.
- `REDIS_PASSWORD`, `REDIS_URL`, and `CODELA_ENCRYPTION_KEY` are mandatory in production.
- All `platform_connections.access_token` values must begin with `enc:v1:` before go-live.
- Put TLS/reverse proxy in front of the API; the Compose API binds to localhost only.
- Run `python tenant_idor_matrix_test.py` in the fully provisioned staging environment before go-live.

## Mandatory production invariants
- `DATABASE_URL` must be PostgreSQL; SQLite is rejected in production.
- `REDIS_URL` must include authentication and use `redis://` or `rediss://`.
- `CODELA_ENCRYPTION_KEY` is required whenever legacy plaintext integration secrets need migration.
- Run `python manage.py migrate` as the dedicated migration step before API/worker startup.
- Never expose Redis or Gunicorn directly to the public internet; terminate TLS at a trusted reverse proxy/load balancer.
