#!/bin/bash
# Threads Growth DB Backup
set -e
BACKUP_DIR="/home/ubuntu/backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
PGDATA="/home/ubuntu/pgdata"
SQLITE_DB="/home/ubuntu/saas/saas.db"
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

# Try PostgreSQL first (production)
if [ -f "$PGDATA/PG_VERSION" ] && /usr/lib/postgresql/16/bin/pg_isready -h /tmp -q 2>/dev/null; then
    /usr/lib/postgresql/16/bin/pg_dump -h /tmp -U saas_user -d threads_saas -Fc > "$BACKUP_DIR/threads_saas-$TIMESTAMP.dump"
    echo "✅ PostgreSQL backup: threads_saas-$TIMESTAMP.dump"
# Fallback to SQLite
elif [ -f "$SQLITE_DB" ]; then
    cp "$SQLITE_DB" "$BACKUP_DIR/saas-$TIMESTAMP.db"
    echo "✅ SQLite backup: saas-$TIMESTAMP.db"
else
    echo "⚠️  No database found to backup"
    exit 0
fi

# Prune old backups (older than RETENTION_DAYS)
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete 2>/dev/null
find "$BACKUP_DIR" -name "*.db" -mtime +$RETENTION_DAYS -delete 2>/dev/null
echo "🧹 Pruned backups older than $RETENTION_DAYS days"
echo "✅ Backup complete"
