# Final Database Setup Instructions

## Current Configuration

- **Docker Container**: Running on port **5433** (container port 5432)
- **Password**: `simplepass123`
- **User**: `et_intel_user`
- **Database**: `et_intel`

## Update Your .env File

Make sure your `.env` file has:

```bash
DATABASE_URL=postgresql://et_intel_user:simplepass123@localhost:5433/et_intel
POSTGRES_PASSWORD=simplepass123
```

## Current Issue

The password authentication is failing from outside the Docker container. The connection works from inside the container but not from your Windows host.

**This might be due to:**
- Windows network routing to Docker
- PostgreSQL authentication configuration
- Port mapping issues

## Workaround: Use the Container Directly

Since the database works inside the container, you can:

1. **Initialize database via Docker**:
   ```bash
   docker exec -it et-intel-db psql -U et_intel_user -d et_intel
   ```

2. **Or run commands through Docker**:
   ```bash
   docker exec et-intel-db python cli.py init
   ```

## Alternative Solution

You may want to use your local PostgreSQL instead:

1. Create database and user in your local PostgreSQL
2. Update .env to use your local PostgreSQL credentials
3. Use port 5432 directly

