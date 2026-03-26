#!/usr/bin/env bash
# Manual backup script — run from the project root.
# Usage: ./deploy/backup.sh [backup_dir]
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTFILE="$BACKUP_DIR/cc_$TIMESTAMP.sql.gz"

docker compose exec -T db pg_dump -U postgres capability_commons | gzip > "$OUTFILE"

echo "Backup saved: $OUTFILE ($(du -h "$OUTFILE" | cut -f1))"

# Prune backups older than 14 days
find "$BACKUP_DIR" -name "cc_*.sql.gz" -mtime +14 -delete
