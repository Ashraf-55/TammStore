# Backup / Restore Production Gate

A release is not production-ready until this procedure is executed against a disposable PostgreSQL staging database.

1. Run `scripts/backup_postgres.sh`.
2. Record the backup checksum and timestamp.
3. Destroy the staging database/volume.
4. Restore the backup into a clean PostgreSQL instance.
5. Run `python manage.py migrate`.
6. Start API and workers.
7. Run `security_regression_test.py` and `tenant_idor_matrix_test.py`.
8. Verify health/readiness, login/2FA, tenant isolation, job processing and encrypted integration secrets.
9. Only then promote the image/configuration.

This runbook is intentionally a gate rather than a claim that an external PostgreSQL backup was executed inside this code-only environment.
