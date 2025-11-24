# ET Intelligence V2 - Production Deployment Instructions

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended) or Windows Server
- **Python**: 3.11 or higher
- **PostgreSQL**: 15 or higher
- **Memory**: 4GB minimum, 8GB recommended
- **Storage**: 20GB minimum for database and logs

### Required Services
- PostgreSQL database server
- (Optional) Redis for caching (Phase 2)

## Initial Setup

### 1. Install System Dependencies

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv postgresql-15 postgresql-contrib
```

#### Windows
- Install Python 3.11+ from python.org
- Install PostgreSQL 15+ from postgresql.org

### 2. Create PostgreSQL Database

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE et_intel;
CREATE USER et_intel_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;
\q
```

### 3. Clone and Setup Application

```bash
# Clone repository
git clone <repo-url> /opt/et-intel-02
cd /opt/et-intel-02

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### 4. Configure Environment

Create `.env` file:

```bash
# Database
DATABASE_URL=postgresql://et_intel_user:secure_password_here@localhost:5432/et_intel

# OpenAI API (optional - for sentiment analysis)
OPENAI_API_KEY=sk-your-key-here

# Sentiment Backend: "rule_based", "openai", or "hybrid"
SENTIMENT_BACKEND=hybrid

# Logging
LOG_LEVEL=INFO
```

**Security Note**: Never commit `.env` to version control!

### 5. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Verify
python cli.py status
```

## Running the Application

### CLI Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Ingest data
python cli.py ingest --source esuit --file data/comments.csv

# Check status
python cli.py status
```

### Scheduled Jobs (Cron)

Create `/etc/cron.d/et-intel`:

```cron
# Daily ingestion at 2 AM
0 2 * * * etuser cd /opt/et-intel-02 && /opt/et-intel-02/venv/bin/python cli.py ingest --source esuit --file /data/daily_export.csv >> /var/log/et-intel/ingest.log 2>&1

# Daily enrichment at 3 AM (Week 2)
0 3 * * * etuser cd /opt/et-intel-02 && /opt/et-intel-02/venv/bin/python cli.py enrich >> /var/log/et-intel/enrich.log 2>&1

# Weekly brief generation on Monday at 9 AM (Week 5)
0 9 * * 1 etuser cd /opt/et-intel-02 && /opt/et-intel-02/venv/bin/python cli.py brief --start "7 days ago" --end "today" >> /var/log/et-intel/brief.log 2>&1
```

## Database Maintenance

### Backups

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/backups/et-intel"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U et_intel_user et_intel | gzip > "$BACKUP_DIR/et_intel_$DATE.sql.gz"

# Keep only last 30 days
find $BACKUP_DIR -name "et_intel_*.sql.gz" -mtime +30 -delete
```

Add to cron:
```cron
0 1 * * * root /opt/et-intel-02/scripts/backup.sh
```

### Restore from Backup

```bash
# Restore database
gunzip -c /backups/et-intel/et_intel_20240101_120000.sql.gz | psql -U et_intel_user et_intel
```

### Database Migrations

```bash
# Create new migration (after model changes)
alembic revision --autogenerate -m "description of changes"

# Review migration file in alembic/versions/

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

## Monitoring

### Log Files

Create log directory:
```bash
sudo mkdir -p /var/log/et-intel
sudo chown etuser:etuser /var/log/et-intel
```

### Health Checks

Create `/opt/et-intel-02/scripts/health_check.sh`:

```bash
#!/bin/bash
# Check database connectivity
python -c "from et_intel_core.db import get_session; get_session().execute('SELECT 1')"
if [ $? -eq 0 ]; then
    echo "✓ Database connection OK"
else
    echo "✗ Database connection FAILED"
    exit 1
fi

# Check record counts
python cli.py status
```

### Monitoring Metrics

- Database size: `SELECT pg_size_pretty(pg_database_size('et_intel'));`
- Comment count: `SELECT COUNT(*) FROM comments;`
- Signal count: `SELECT COUNT(*) FROM extracted_signals;`
- Recent ingestion: `SELECT MAX(created_at) FROM comments;`

## Security

### Database Security

1. **Use strong passwords**
   - Minimum 16 characters
   - Mix of uppercase, lowercase, numbers, symbols

2. **Restrict database access**
   ```bash
   # Edit /etc/postgresql/15/main/pg_hba.conf
   # Only allow local connections
   local   et_intel    et_intel_user    md5
   ```

3. **Enable SSL for remote connections** (if needed)

### API Keys

1. **OpenAI API Key**
   - Store in `.env` file (never in code)
   - Rotate periodically
   - Monitor usage to detect anomalies

2. **File Permissions**
   ```bash
   chmod 600 .env
   chown etuser:etuser .env
   ```

## Performance Tuning

### PostgreSQL Configuration

Edit `/etc/postgresql/15/main/postgresql.conf`:

```ini
# Memory
shared_buffers = 2GB
effective_cache_size = 6GB
work_mem = 64MB

# Connections
max_connections = 100

# Checkpoint
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# Query Planning
random_page_cost = 1.1  # For SSD
effective_io_concurrency = 200
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

### Application Performance

1. **Batch Size**: Adjust commit frequency in `IngestionService`
   - Default: 100 records
   - For large imports: 500-1000 records

2. **Connection Pooling**: Already configured in `db.py`
   - Pool size: 5
   - Max overflow: 10

## Troubleshooting

### Common Issues

1. **Database connection fails**
   ```bash
   # Check PostgreSQL is running
   sudo systemctl status postgresql
   
   # Check connection
   psql -U et_intel_user -d et_intel -h localhost
   ```

2. **Out of memory during ingestion**
   - Reduce batch size
   - Process files in smaller chunks
   - Increase system memory

3. **Slow queries**
   ```sql
   -- Check slow queries
   SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;
   
   -- Analyze tables
   ANALYZE comments;
   ANALYZE extracted_signals;
   ```

4. **Disk space issues**
   ```bash
   # Check disk usage
   df -h
   
   # Check database size
   du -sh /var/lib/postgresql/15/main/
   
   # Vacuum database
   VACUUM FULL ANALYZE;
   ```

## Upgrade Procedures

### Application Updates

```bash
cd /opt/et-intel-02

# Backup database first!
/opt/et-intel-02/scripts/backup.sh

# Pull latest code
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Update dependencies
pip install -r requirements.txt --upgrade

# Run migrations
alembic upgrade head

# Restart services (if running as daemon)
sudo systemctl restart et-intel
```

### Python Version Upgrade

```bash
# Install new Python version
sudo apt install python3.12

# Create new virtual environment
python3.12 -m venv venv-new

# Activate and install dependencies
source venv-new/bin/activate
pip install -r requirements.txt

# Test thoroughly
pytest tests/

# Switch to new environment
mv venv venv-old
mv venv-new venv
```

## Disaster Recovery

### Full System Restore

1. **Install system dependencies** (see Initial Setup)
2. **Restore database** from backup
3. **Clone application** code
4. **Restore `.env` file** from secure backup
5. **Run health checks**

### Data Loss Prevention

1. **Daily automated backups** (configured in cron)
2. **Off-site backup storage** (copy to S3/Azure/GCS)
3. **Test restore procedures** monthly
4. **Document recovery steps**

## Support Contacts

- **Database Issues**: DBA Team
- **Application Issues**: Development Team
- **Infrastructure**: DevOps Team

## Change Log

### 2025-11-24
- Initial production instructions created
- Week 1 Foundation deployment ready

---

*Last Updated: 2025-11-24*
*Version: 2.0.0*

