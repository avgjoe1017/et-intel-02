-- Create tables for ET Intelligence
-- This can be executed inside the Docker container

-- Create UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Note: For full table creation, we need to run the Python code
-- This is a workaround until authentication is fixed
-- Run: docker exec -it et-intel-db psql -U et_intel_user -d et_intel -f /tmp/create_tables_docker.sql

