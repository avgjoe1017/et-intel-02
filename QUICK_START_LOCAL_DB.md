# Quick Start: Local PostgreSQL Setup

## Prerequisites

You need to know your PostgreSQL `postgres` user password.

## 3-Step Setup

### 1. Create Database and User

Open PowerShell and run:

```powershell
# You'll be prompted for postgres password
psql -U postgres
```

Then in the psql prompt:

```sql
CREATE DATABASE et_intel;
CREATE USER et_intel_user WITH PASSWORD 'simplepass123';
GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;
\q
```

### 2. Update .env File

Add this line to your `.env` file:

```bash
DATABASE_URL=postgresql://et_intel_user:simplepass123@localhost:5432/et_intel
```

### 3. Initialize and Test

```bash
# Initialize database
python cli.py init

# Check status
python cli.py status

# Test Apify scraping
python cli.py apify-scrape \
    --urls "https://www.instagram.com/p/DRSz8XLgVCC" \
    --cookies data/apify_cookies.json \
    --max-comments 2000
```

That's it! 🎉

## If You Don't Know Your Postgres Password

See `MD_DOCS/SETUP_LOCAL_POSTGRES.md` for password reset instructions.

