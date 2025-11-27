# Local PostgreSQL Setup Guide

## Quick Setup

### Option 1: Using PowerShell Script

```powershell
.\scripts\setup_local_db.ps1
```

The script will:
1. Ask for your postgres password
2. Ask for et_intel_user password (default: simplepass123)
3. Create the database and user
4. Show you the DATABASE_URL to add to .env

### Option 2: Manual Setup

1. **Connect to PostgreSQL**:
   ```bash
   psql -U postgres
   ```

2. **Create database and user**:
   ```sql
   CREATE DATABASE et_intel;
   CREATE USER et_intel_user WITH PASSWORD 'simplepass123';
   GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;
   \q
   ```

3. **Update your `.env` file**:
   ```bash
   DATABASE_URL=postgresql://et_intel_user:simplepass123@localhost:5432/et_intel
   ```

4. **Initialize the database**:
   ```bash
   python cli.py init
   ```

5. **Verify**:
   ```bash
   python cli.py status
   ```

## Testing Apify Scraping

Once the database is initialized, you can test the Apify scraping:

```bash
python cli.py apify-scrape \
    --urls "https://www.instagram.com/p/DRSz8XLgVCC https://www.instagram.com/p/DRS626nE0Yv https://www.instagram.com/p/DRS8CkaD1vC/ https://www.instagram.com/p/DRTBoTgD8Z5" \
    --cookies data/apify_cookies.json \
    --max-comments 2000
```

