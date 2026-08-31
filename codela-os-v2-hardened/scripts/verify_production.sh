#!/usr/bin/env sh
set -eu
: "${CODELA_ENV:?Set CODELA_ENV=production}"
[ "$CODELA_ENV" = "production" ]
: "${CODELA_SECRET_KEY:?CODELA_SECRET_KEY is required}"
[ "${#CODELA_SECRET_KEY}" -ge 32 ]
: "${CODELA_CORS_ORIGINS:?CODELA_CORS_ORIGINS is required}"
: "${REDIS_URL:?REDIS_URL is required}"
case "$REDIS_URL" in redis://:*@*|rediss://:*@*) ;; *) echo "ERROR: REDIS_URL must contain authentication" >&2; exit 1;; esac
: "${DATABASE_URL:?DATABASE_URL is required}"
case "$DATABASE_URL" in postgresql://*|postgres://*) ;; *) echo "ERROR: production DATABASE_URL must be PostgreSQL" >&2; exit 1;; esac
: "${CODELA_ENCRYPTION_KEY:?CODELA_ENCRYPTION_KEY is required}"
: "${CODELA_PLATFORM_ADMIN_EMAILS:?CODELA_PLATFORM_ADMIN_EMAILS is required}"
case "$CODELA_CORS_ORIGINS" in
  *http://*) echo 'ERROR: production CORS must use HTTPS' >&2; exit 1;;
esac
printf '%s\n' 'production environment sanity check: PASS'
