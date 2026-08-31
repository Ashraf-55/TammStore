#!/usr/bin/env sh
set -eu
DB_PATH="${CODELA_DB_PATH:-./codela.db}"
OUT_DIR="${CODELA_BACKUP_DIR:-./backups}"
mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
sqlite3 "$DB_PATH" ".backup '$OUT_DIR/codela-$STAMP.db'"
find "$OUT_DIR" -type f -name 'codela-*.db' -mtime +7 -delete
printf '%s\n' "$OUT_DIR/codela-$STAMP.db"
