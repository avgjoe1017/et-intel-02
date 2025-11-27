#!/bin/bash
# Health check script for ET Intelligence system
# Checks database connectivity, application status, and key metrics

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DATABASE_URL="${DATABASE_URL:-postgresql://et_intel_user:password@localhost:5432/et_intel}"

echo "ET Intelligence Health Check"
echo "=============================="
echo ""

# Extract connection details
DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

export PGPASSWORD="$DB_PASS"

# Check 1: Database connectivity
echo -n "1. Database connectivity... "
if psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
    echo "   Cannot connect to database"
    exit 1
fi

# Check 2: Required tables exist
echo -n "2. Database schema... "
TABLES=$(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT COUNT(*) FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name IN ('posts', 'comments', 'monitored_entities', 'extracted_signals', 'discovered_entities');
")

if [ "$TABLES" -eq 5 ]; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
    echo "   Missing required tables (found $TABLES/5)"
    exit 1
fi

# Check 3: Python application
echo -n "3. Python application... "
if python -c "from et_intel_core.db import get_session; get_session().execute('SELECT 1')" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
    echo "   Cannot import application modules"
    exit 1
fi

# Check 4: Database statistics
echo ""
echo "Database Statistics:"
echo "--------------------"

# Count records
POSTS=$(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM posts;")
COMMENTS=$(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM comments;")
ENTITIES=$(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM monitored_entities;")
SIGNALS=$(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM extracted_signals;")

echo "  Posts:              $(echo $POSTS | xargs)"
echo "  Comments:           $(echo $COMMENTS | xargs)"
echo "  Monitored Entities: $(echo $ENTITIES | xargs)"
echo "  Extracted Signals:   $(echo $SIGNALS | xargs)"

# Check 5: Recent activity
echo ""
echo -n "5. Recent activity... "
LAST_COMMENT=$(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT MAX(created_at) FROM comments;
")

if [ -n "$LAST_COMMENT" ] && [ "$LAST_COMMENT" != "" ]; then
    echo -e "${GREEN}✓ OK${NC}"
    echo "   Last comment: $(echo $LAST_COMMENT | xargs)"
else
    echo -e "${YELLOW}⚠ No recent activity${NC}"
fi

# Check 6: Database size
echo ""
echo -n "6. Database size... "
DB_SIZE=$(psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT pg_size_pretty(pg_database_size('$DB_NAME'));
")
echo -e "${GREEN}✓ OK${NC}"
echo "   Size: $(echo $DB_SIZE | xargs)"

# Check 7: Disk space (if on same host)
if [ "$DB_HOST" = "localhost" ] || [ "$DB_HOST" = "127.0.0.1" ]; then
    echo ""
    echo -n "7. Disk space... "
    DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -lt 80 ]; then
        echo -e "${GREEN}✓ OK${NC}"
        echo "   Usage: ${DISK_USAGE}%"
    elif [ "$DISK_USAGE" -lt 90 ]; then
        echo -e "${YELLOW}⚠ WARNING${NC}"
        echo "   Usage: ${DISK_USAGE}% (approaching limit)"
    else
        echo -e "${RED}✗ CRITICAL${NC}"
        echo "   Usage: ${DISK_USAGE}% (disk nearly full)"
        exit 1
    fi
fi

# Summary
echo ""
echo "=============================="
echo -e "${GREEN}Health check passed!${NC}"
echo ""

# Unset PGPASSWORD
unset PGPASSWORD

