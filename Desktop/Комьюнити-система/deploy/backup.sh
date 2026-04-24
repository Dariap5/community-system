#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="/var/www/community-system-new"
BACKUP_DIR="/var/backups/community-bot"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$PROJECT_DIR/.env"
    set +a
fi

: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

cd "$PROJECT_DIR"
DATE="$(date +%Y%m%d_%H%M%S)"
docker compose exec -T db env PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h 127.0.0.1 -U "${POSTGRES_USER:-community_user}" "${POSTGRES_DB:-community_db}" | gzip > "$BACKUP_DIR/db_${DATE}.sql.gz"

find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$RETENTION_DAYS" -delete