# ET Intelligence V2 - Setup Guide

Quick setup guide to get ET Intelligence V2 running on your local machine.

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 15 or higher
- Git

## Step-by-Step Setup

### 1. Install PostgreSQL

#### Windows
1. Download PostgreSQL from https://www.postgresql.org/download/windows/
2. Run installer and follow prompts
3. Remember your postgres user password

#### macOS
```bash
brew install postgresql@15
brew services start postgresql@15
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install postgresql-15 postgresql-contrib
sudo systemctl start postgresql
```

### 2. Create Database

```bash
# Connect to PostgreSQL
psql -U postgres

# In psql prompt:
CREATE DATABASE et_intel;
CREATE USER et_intel_user WITH PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;
\q
```

### 3. Clone Repository

```bash
git clone <repo-url>
cd et-intel-02
```

### 4. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 5. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### 6. Configure Environment

Create `.env` file in project root:

```bash
# Copy example
cp env.example .env

# Edit .env with your settings
# On Windows: notepad .env
# On macOS/Linux: nano .env
```

Update these values in `.env`:
```
DATABASE_URL=postgresql://et_intel_user:your_password_here@localhost:5432/et_intel
SENTIMENT_BACKEND=rule_based
LOG_LEVEL=INFO
```

### 7. Initialize Database

```bash
# Create tables
python cli.py init

# Verify
python cli.py status
```

You should see:
```
📊 Database Status
========================================
Posts:              0
Comments:           0
Monitored Entities: 0
Extracted Signals:  0
========================================
```

### 8. Test with Sample Data

```bash
# Ingest sample data
python cli.py ingest --source esuit --file data/sample_esuit.csv

# Check status again
python cli.py status
```

You should now see:
```
📊 Database Status
========================================
Posts:              2
Comments:           5
Monitored Entities: 0
Extracted Signals:  0
========================================
```

### 9. Run Tests

```bash
# Run all tests
pytest tests/ -v

# You should see all tests passing
```

## Verify Installation

Run this Python script to verify everything works:

```python
from et_intel_core.db import get_session
from et_intel_core.models import Post, Comment

session = get_session()

# Count records
post_count = session.query(Post).count()
comment_count = session.query(Comment).count()

print(f"✓ Database connection works!")
print(f"✓ Found {post_count} posts and {comment_count} comments")

session.close()
```

Save as `verify.py` and run:
```bash
python verify.py
```

## Common Setup Issues

### Issue: "ModuleNotFoundError: No module named 'et_intel_core'"

**Solution**: Make sure you're in the project directory and virtual environment is activated:
```bash
cd et-intel-02
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

### Issue: "psycopg2.OperationalError: could not connect to server"

**Solution**: PostgreSQL is not running. Start it:
```bash
# Windows: Use Services app to start PostgreSQL
# macOS: brew services start postgresql@15
# Linux: sudo systemctl start postgresql
```

### Issue: "FATAL: password authentication failed"

**Solution**: Check your DATABASE_URL in `.env` file has correct password.

### Issue: "ImportError: cannot import name 'BaseSettings'"

**Solution**: Update pydantic-settings:
```bash
pip install --upgrade pydantic-settings
```

### Issue: Tests fail with "no such table"

**Solution**: Initialize test database:
```bash
python cli.py init
```

## Next Steps

Now that you have ET Intelligence V2 set up:

1. **Read the documentation**:
   - [README.md](README.md) - Overview and features
   - [QUICK_REFERENCE.md](MD_DOCS/QUICK_REFERENCE.md) - Common commands
   - [WEEK_1_FOUNDATION.md](MD_DOCS/WEEK_1_FOUNDATION.md) - Detailed guide

2. **Try ingesting real data**:
   - Export comments from ESUIT or Apify
   - Place CSV in `data/` folder
   - Run `python cli.py ingest --source esuit --file data/your_file.csv`

3. **Explore the database**:
   ```bash
   psql -U et_intel_user -d et_intel
   ```
   ```sql
   SELECT * FROM posts LIMIT 5;
   SELECT * FROM comments LIMIT 5;
   ```

4. **Wait for Week 2** (NLP Layer):
   - Entity extraction with spaCy
   - Sentiment analysis
   - Intelligence signals

## Development Workflow

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Make code changes
# ... edit files ...

# 3. Run tests
pytest tests/ -v

# 4. Format code
black .

# 5. Test ingestion
python cli.py ingest --source esuit --file data/test.csv

# 6. Check results
python cli.py status
```

## Getting Help

- **Documentation**: Check `MD_DOCS/` folder
- **Architecture**: Read `ET_Intelligence_Rebuild_Architecture.md`
- **Progress**: See `PROGRESS.md` for what's implemented
- **Issues**: Check common issues above

## Uninstall / Clean Up

```bash
# Drop database
psql -U postgres -c "DROP DATABASE et_intel;"

# Remove virtual environment
rm -rf venv/  # or rmdir /s venv on Windows

# Remove project
cd ..
rm -rf et-intel-02/  # or rmdir /s et-intel-02 on Windows
```

---

**Setup complete!** You're ready to start using ET Intelligence V2.

