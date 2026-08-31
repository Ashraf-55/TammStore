#!/usr/bin/env sh
set -eu
: "${CODELA_ENV:=staging}"
python -m compileall -q .
node --check frontend/app.js
python production_check.py
python manage.py migrate
python manage.py version
python tenant_idor_matrix_test.py
printf '%s\n' 'staging security gate: static checks and migration gate PASS'
printf '%s\n' 'NOTE: full IDOR/runtime/load/backup tests require PostgreSQL + Redis staging services.'
