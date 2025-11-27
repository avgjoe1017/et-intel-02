# Simple Database Setup Guide

## Quick Solution: Use Docker (Easiest)

This is the simplest way to get PostgreSQL running without password issues:

### 1. Set a Password in `.env`

Add this to your `.env` file (or create it if it doesn't exist):

```bash
# PostgreSQL Password for Docker
POSTGRES_PASSWORD=my_secure_password_123

# Database Connection
DATABASE_URL=postgresql://et_intel_user:my_secure_password_123@localhost:5432/et_intel
```

### 2. Start PostgreSQL with Docker

```bash
docker-compose up -d postgres
```

This will:
- Create a PostgreSQL container
- Set the password from your `.env` file
- Create the database and user automatically
- Run on port 5432

### 3. Initialize Database

```bash
python cli.py init
```

### 4. Verify It Works

```bash
python cli.py status
```

---

## Alternative: Use Your Local PostgreSQL

If you prefer to use your existing PostgreSQL installation:

### Option A: You Remember Your Password

1. Connect to PostgreSQL:
   ```bash
   psql -U postgres
   ```

2. Create database and user:
   ```sql
   CREATE DATABASE et_intel;
   CREATE USER et_intel_user WITH PASSWORD 'your_password_here';
   GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;
   \q
   ```

3. Update `.env`:
   ```bash
   DATABASE_URL=postgresql://et_intel_user:your_password_here@localhost:5432/et_intel
   ```

### Option B: Reset Your Password

If you forgot your password, see `MD_DOCS/FIND_POSTGRES_PASSWORD.md` for detailed instructions.

**Quick version:**
1. Edit `C:\Program Files\PostgreSQL\16\data\pg_hba.conf`
2. Change `md5` to `trust` for local connections
3. Restart PostgreSQL service
4. Connect without password: `psql -U postgres`
5. Reset password: `ALTER USER postgres PASSWORD 'new_password';`
6. Change `pg_hba.conf` back to `md5`
7. Restart service again

---

## Recommended Approach

**Use Docker** - it's simpler, isolated, and doesn't interfere with your existing PostgreSQL setup.

```bash
# 1. Add to .env
POSTGRES_PASSWORD=your_password_here
DATABASE_URL=postgresql://et_intel_user:your_password_here@localhost:5432/et_intel

# 2. Start PostgreSQL
docker-compose up -d postgres

# 3. Initialize
python cli.py init

# 4. Test
python cli.py status
```

That's it! 🎉

