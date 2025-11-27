# How to Find Your PostgreSQL Password

## Quick Options

### Option 1: Try Connecting Without Password (Windows Authentication)
On Windows, PostgreSQL might use Windows authentication:

```bash
psql -U postgres -d postgres
```

If this works, you can then set a password or create the database.

### Option 2: Check If You Remember It
- The password was set during PostgreSQL installation
- Check your notes or password manager
- Common default passwords people use: `postgres`, `admin`, `password`, or what you set during install

### Option 3: Reset the Password (Windows)

If you can't remember the password, you can reset it:

1. **Edit pg_hba.conf** (usually in `C:\Program Files\PostgreSQL\16\data\`):
   - Find the line: `host all all 127.0.0.1/32 md5`
   - Temporarily change to: `host all all 127.0.0.1/32 trust`
   - Save the file

2. **Restart PostgreSQL service**:
   ```powershell
   # Run as Administrator
   Restart-Service postgresql-x64-16
   ```

3. **Connect and reset password**:
   ```bash
   psql -U postgres
   ```
   Then in psql:
   ```sql
   ALTER USER postgres PASSWORD 'your_new_password';
   ```

4. **Restore pg_hba.conf**:
   - Change back to: `host all all 127.0.0.1/32 md5`
   - Restart PostgreSQL service again

### Option 4: Use Docker Instead (Easier)

If you prefer, you can use Docker which simplifies this:

1. **Add to your `.env` file**:
   ```bash
   POSTGRES_PASSWORD=your_secure_password_here
   ```

2. **Start PostgreSQL with Docker**:
   ```bash
   docker-compose up -d postgres
   ```

3. **Your `.env` DATABASE_URL should be**:
   ```bash
   DATABASE_URL=postgresql://et_intel_user:your_secure_password_here@localhost:5432/et_intel
   ```

## Quick Test Commands

### Test Current Password
Try common passwords:
```bash
psql -U postgres -h localhost -W
# When prompted, try: postgres, admin, password, or what you remember
```

### Check PostgreSQL Service Status
```powershell
Get-Service postgresql*
```

### Find PostgreSQL Installation Directory
```powershell
Get-Service postgresql* | Select-Object Name, DisplayName, Status
```

## Recommended: Create Dedicated User

Instead of using `postgres` superuser, create a dedicated user:

```sql
-- Connect as postgres (however you can)
psql -U postgres

-- Create database and user
CREATE DATABASE et_intel;
CREATE USER et_intel_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;
\q
```

Then your `.env` would be:
```bash
DATABASE_URL=postgresql://et_intel_user:your_secure_password@localhost:5432/et_intel
```

