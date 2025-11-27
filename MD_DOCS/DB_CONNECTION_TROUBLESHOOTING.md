# Database Connection Troubleshooting

## Current Status

- **Docker Container**: Running on port 5433 (mapped from container port 5432)
- **Local PostgreSQL**: Running on port 5432 (blocking Docker)
- **Password**: `simplepass123`
- **Issue**: Password authentication failing from outside container, but works inside

## Next Steps

1. **Option 1: Stop Local PostgreSQL** (Requires Admin)
   - Open PowerShell as Administrator
   - Run: `Stop-Service postgresql-x64-16,postgresql-x64-17`
   - Change Docker back to port 5432
   - Update .env to use port 5432

2. **Option 2: Use Different Port**
   - Keep Docker on 5433 (already configured)
   - Update .env: `DATABASE_URL=postgresql://et_intel_user:simplepass123@localhost:5433/et_intel`
   - The password authentication issue needs to be resolved

3. **Option 3: Use Local PostgreSQL Instead**
   - Create the database and user in your local PostgreSQL
   - Use your local PostgreSQL credentials

## Testing Connection

```powershell
# Test from inside container (works)
docker exec et-intel-db psql -U et_intel_user -d et_intel -c "SELECT current_user;"

# Test from outside (fails)
$env:PGPASSWORD='simplepass123'
psql -h 127.0.0.1 -p 5433 -U et_intel_user -d et_intel -c "SELECT current_user;"
```

## Known Issues

- Password authentication fails from outside Docker container
- Local PostgreSQL services are blocking port 5432
- Container password works internally but not externally

