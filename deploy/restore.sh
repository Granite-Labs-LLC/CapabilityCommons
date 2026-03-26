#!/usr/bin/env bash
# Restore a database backup.
# Usage: ./deploy/restore.sh <backup_file>
# Example: ./deploy/restore.sh backups/cc_20260325_020000.sql.gz
set -euo pipefail

BACKUP_FILE="${1:?Usage: $0 <backup_file.sql.gz>}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: File not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will drop and recreate the capability_commons database."
echo "Press Ctrl-C to cancel, or Enter to continue."
read -r

# Drop and recreate database
docker compose exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS capability_commons;"
docker compose exec -T db psql -U postgres -c "CREATE DATABASE capability_commons;"

# Restore
gunzip -c "$BACKUP_FILE" | docker compose exec -T db psql -U postgres capability_commons

echo "Restore complete from: $BACKUP_FILE"
echo "Run 'docker compose exec api alembic upgrade head' if migrations are newer than the backup."
