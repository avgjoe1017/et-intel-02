# Database Initialization Workaround

## Current Issue

Password authentication is failing when connecting to Docker PostgreSQL from Windows host, even though it works from inside the container.

## Workaround: Initialize Database Inside Container

Since the database connection works inside the Docker container, you can initialize it there:

### Option 1: Use Docker exec with Python

```bash
# Copy your code into the container
docker cp . et-intel-db:/app
docker exec -it et-intel-db bash
cd /app
python cli.py init
```

### Option 2: Create Tables via SQLAlchemy Script

Create a script that connects from inside the container or uses a different connection method.

### Option 3: Use Local PostgreSQL

Instead of Docker, use your local PostgreSQL:
1. Create database and user in your local PostgreSQL
2. Update .env to use local PostgreSQL credentials
3. Initialize normally: `python cli.py init`

## Current Status

- ✅ Docker container is running
- ✅ Database `et_intel` exists
- ✅ User `et_intel_user` exists  
- ✅ Password works inside container
- ❌ Password authentication fails from Windows host

## Next Steps

1. Fix authentication issue, OR
2. Use workaround to initialize tables inside container, OR
3. Switch to using local PostgreSQL directly

