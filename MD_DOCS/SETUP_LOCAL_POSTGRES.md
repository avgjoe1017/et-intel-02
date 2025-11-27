# Setup Local PostgreSQL for ET Intelligence

## Step 1: Find or Set Your PostgreSQL Password

Your local PostgreSQL requires a password for the `postgres` user. Here are your options:

### Option A: You Know Your Password
If you remember the password you set during PostgreSQL installation, proceed to Step 2.

### Option B: Reset Your Password

**Windows Method (requires admin):**

1. Open PowerShell as Administrator
2. Find your PostgreSQL data directory:
   ```
   Get-Content "C:\Program Files\PostgreSQL\16\data\postgresql.conf" | Select-String "data_directory"
   ```
   Usually: `C:\Program Files\PostgreSQL\16\data\`

3. Edit `pg_hba.conf` (in data directory):
   - Find line: `host all all 127.0.0.1/32 md5`
   - Temporarily change to: `host all all 127.0.0.1/32 trust`
   - Save file

4. Restart PostgreSQL service:
   ```powershell
   Restart-Service postgresql-x64-16
   ```

5. Connect without password:
   ```bash
   psql -U postgres
   ```

6. Reset password:
   ```sql
   ALTER USER postgres PASSWORD 'your_new_password';
   \q
   ```

7. Restore `pg_hba.conf`:
   - Change back to: `host all all 127.0.0.1/32 md5`
   - Restart service again

## Step 2: Create Database and User

Once you can connect to PostgreSQL:

### Method 1: Using PowerShell Script

```powershell
# Run the setup script
.\scripts\setup_local_db.ps1
```

### Method 2: Manual SQL Commands

```bash
# Connect to PostgreSQL
psql -U postgres

# In psql prompt, run:
CREATE DATABASE et_intel;
CREATE USER et_intel_user WITH PASSWORD 'simplepass123';
GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;
\q
```

## Step 3: Update .env File

Update your `.env` file:

```bash
DATABASE_URL=postgresql://et_intel_user:simplepass123@localhost:5432/et_intel
```

## Step 4: Initialize Database

```bash
python cli.py init
python cli.py status
```

## Step 5: Test Apify Scraping

```bash
python cli.py apify-scrape \
    --urls "https://www.instagram.com/p/DRSz8XLgVCC https://www.instagram.com/p/DRS626nE0Yv https://www.instagram.com/p/DRS8CkaD1vC/ https://www.instagram.com/p/DRTBoTgD8Z5" \
    --cookies data/apify_cookies.json \
    --max-comments 2000
```

## Quick Command Reference

```bash
# Test connection
psql -U postgres -d et_intel -c "SELECT version();"

# List databases
psql -U postgres -c "\l"

# Connect to database
psql -U et_intel_user -d et_intel

# Check if database exists
psql -U postgres -c "\l" | Select-String "et_intel"
```

