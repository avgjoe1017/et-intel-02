# Fresh PostgreSQL Database Setup

## Manual Setup Steps (No Password Required)

Since the script needs admin privileges, here's a manual approach:

### Step 1: Modify pg_hba.conf (Already Done ✓)

The script already modified your `pg_hba.conf` to enable passwordless authentication. If you need to do this manually:

1. Open `C:\Program Files\PostgreSQL\17\data\pg_hba.conf` as Administrator
2. Find lines with `127.0.0.1/32` and `::1/128`
3. Change `md5` or `scram-sha-256` to `trust`
4. Save the file

### Step 2: Restart PostgreSQL Service (Requires Admin)

**Option A: PowerShell as Administrator**
```powershell
Restart-Service postgresql-x64-17
```

**Option B: Services GUI**
1. Press `Win + R`, type `services.msc`
2. Find "PostgreSQL Server 17"
3. Right-click → Restart

### Step 3: Create Database and User

Once restarted, run:

```bash
psql -U postgres
```

Then in psql:

```sql
-- Create database
CREATE DATABASE et_intel;

-- Create user with password
CREATE USER et_intel_user WITH PASSWORD 'simplepass123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;

-- Verify
\l
\du

-- Exit
\q
```

### Step 4: Restore Secure Authentication

Edit `pg_hba.conf` again and change `trust` back to `md5`, then restart the service.

### Step 5: Update .env File

```bash
DATABASE_URL=postgresql://et_intel_user:simplepass123@localhost:5432/et_intel
```

### Step 6: Initialize Database

```bash
python cli.py init
python cli.py status
```

## Quick Alternative: Run SQL Directly

If you can't restart the service, try creating the database via SQL file:

1. Create `create_db.sql`:
```sql
CREATE DATABASE et_intel;
CREATE USER et_intel_user WITH PASSWORD 'simplepass123';
GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;
```

2. Run it (once service is restarted or if you can connect):
```bash
psql -U postgres -f create_db.sql
```

