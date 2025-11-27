#!/bin/bash
# Database restore script for ET Intelligence
# Restores from a backup file

set -euo pipefail

# Check if backup file is provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file> [--force]"
    echo ""
    echo "Example:"
    echo "  $0 /backups/et-intel/et_intel_20240101_120000.sql.gz"
    echo ""
    echo "Options:"
    echo "  --force    Skip confirmation prompt"
    exit 1
fi

BACKUP_FILE="$1"
FORCE="${2:-}"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Extract connection details from DATABASE_URL
DATABASE_URL="${DATABASE_URL:-postgresql://et_intel_user:password@localhost:5432/et_intel}"

DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

# Set PGPASSWORD
export PGPASSWORD="$DB_PASS"

# Confirmation prompt (unless --force)
if [ "$FORCE" != "--force" ]; then
    echo "WARNING: This will restore the database from backup."
    echo "Database: $DB_NAME"
    echo "Backup file: $BACKUP_FILE"
    echo ""
    echo "This will DELETE all existing data in the database!"
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

# Check if database exists
DB_EXISTS=$(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -w "$DB_NAME" | wc -l)

if [ "$DB_EXISTS" -eq 0 ]; then
    echo "Database $DB_NAME does not exist. Creating..."
    createdb -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME"
fi

# Determine if backup is compressed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Restoring from compressed backup..."
    gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME"
else
    echo "Restoring from uncompressed backup..."
    psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE"
fi

# Check restore status
if [ $? -eq 0 ]; then
    echo "✓ Database restored successfully"
    
    # Run ANALYZE to update statistics
    echo "Updating database statistics..."
    psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -c "ANALYZE;"
    
    echo "Restore process completed."
else
    echo "✗ Restore failed!"
    exit 1
fi

# Unset PGPASSWORD
unset PGPASSWORD

