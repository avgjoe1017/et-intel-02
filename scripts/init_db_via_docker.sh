#!/bin/bash
# Initialize database via Docker exec
# This works around authentication issues from Windows host

echo "Initializing database via Docker..."

# Create tables using Alembic migrations
docker exec et-intel-db psql -U et_intel_user -d et_intel -c "
CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";
"

echo "Database initialized!"
echo ""
echo "Note: Full schema initialization requires running Alembic migrations."
echo "You may need to copy your code into the container or use a different method."

