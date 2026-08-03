#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${DB_NAME:-nae}"
BACKUP_DIR="${BACKUP_DIR:-/srv/nae/backups}"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
PREFIX="${BACKUP_PREFIX:-nae_backup}"
DUMP_FILE="${BACKUP_DIR}/${PREFIX}_${TIMESTAMP}.dump"
SQL_FILE="${BACKUP_DIR}/${PREFIX}_${TIMESTAMP}.sql"

mkdir -p "${BACKUP_DIR}"

pg_dump -d "${DB_NAME}" -Fc -f "${DUMP_FILE}"
pg_dump -d "${DB_NAME}" -f "${SQL_FILE}"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${DUMP_FILE}" "${SQL_FILE}" > "${BACKUP_DIR}/${PREFIX}_${TIMESTAMP}.sha256"
fi

ls -lh "${DUMP_FILE}" "${SQL_FILE}"
echo "Backup completado: ${BACKUP_DIR}/${PREFIX}_${TIMESTAMP}"
