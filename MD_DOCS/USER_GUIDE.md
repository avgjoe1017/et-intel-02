# ET Intelligence V2 - User Guide

Complete guide for using the ET Intelligence system.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [CLI Commands](#cli-commands)
3. [Dashboard Usage](#dashboard-usage)
4. [Workflows](#workflows)
5. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Initial Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   ```

2. **Configure environment**:
   ```bash
   cp env.example .env
   # Edit .env with your database credentials
   ```

3. **Initialize database**:
   ```bash
   python cli.py init
   python cli.py seed-entities
   ```

### Quick Start Workflow

```bash
# 1. Ingest data
python cli.py ingest --source esuit --file data/comments.csv

# 2. Enrich with entities and sentiment
python cli.py enrich

# 3. Check status
python cli.py status

# 4. Generate brief
python cli.py brief --start 2024-01-01 --end 2024-01-07

# 5. Launch dashboard
streamlit run dashboard.py
```

---

## CLI Commands

### Database Management

#### `init`
Initialize database schema.

```bash
python cli.py init
python cli.py init --force  # Skip confirmation
```

#### `status`
Show database statistics.

```bash
python cli.py status
python cli.py status --detailed  # Show more details
```

### Data Ingestion

#### `ingest`
Ingest comments from CSV files.

```bash
# ESUIT format
python cli.py ingest --source esuit --file data/esuit_export.csv

# Apify format
python cli.py ingest --source apify --file data/apify_export.csv
```

**Options**:
- `--source`: Source format (`esuit` or `apify`)
- `--file`: Path to CSV file

### Entity Management

#### `seed-entities`
Load seed entity catalog.

```bash
python cli.py seed-entities
```

#### `add-entity`
Add entity to monitoring.

```bash
python cli.py add-entity "Taylor Swift" --type person --aliases "T-Swift" "Tay"
```

**Options**:
- `--type`: Entity type (`person`, `show`, `couple`, `brand`)
- `--aliases`: Alternate names (can specify multiple)

#### `review-entities`
Review discovered entities.

```bash
python cli.py review-entities
python cli.py review-entities --min-mentions 10
```

**Options**:
- `--min-mentions`: Minimum mentions to show (default: 5)

### Enrichment

#### `enrich`
Extract entities and score sentiment.

```bash
# Enrich all unprocessed comments
python cli.py enrich

# Enrich comments from last 7 days
python cli.py enrich --days 7

# Enrich comments since specific date
python cli.py enrich --since 2024-01-01
```

**Options**:
- `--days`: Number of days to look back
- `--since`: Only enrich comments after this date

### Analytics

#### `top-entities`
Show top entities by mentions.

```bash
python cli.py top-entities
python cli.py top-entities --days 30 --limit 20
python cli.py top-entities --export entities.csv
```

**Options**:
- `--days`: Number of days to analyze (default: 30)
- `--limit`: Maximum entities to show (default: 20)
- `--export`: Export to CSV file

#### `velocity`
Check velocity alert for entity.

```bash
python cli.py velocity "Taylor Swift"
python cli.py velocity "Blake Lively" --window-hours 48
```

**Options**:
- `--window-hours`: Hours to look back (default: 72)

#### `sentiment-history`
Show sentiment trend for entity.

```bash
python cli.py sentiment-history "Taylor Swift"
python cli.py sentiment-history "Blake Lively" --days 60 --export trend.csv
```

**Options**:
- `--days`: Number of days of history (default: 30)
- `--export`: Export to CSV file

### Reporting

#### `brief`
Generate intelligence brief.

```bash
python cli.py brief --start 2024-01-01 --end 2024-01-07
python cli.py brief --start 2024-01-01 --end 2024-01-07 --output weekly_brief.pdf
python cli.py brief --start 2024-01-01 --end 2024-01-07 --json  # Also save JSON
```

**Options**:
- `--start`: Start date (YYYY-MM-DD)
- `--end`: End date (YYYY-MM-DD)
- `--output`: Output filename
- `--json`: Also save JSON data file

### Database Maintenance

#### `create-indexes`
Create performance indexes.

```bash
python cli.py create-indexes
```

#### `version`
Show version and system information.

```bash
python cli.py version
```

---

## Dashboard Usage

### Starting the Dashboard

```bash
streamlit run dashboard.py
```

Dashboard opens at `http://localhost:8501`

### Navigation

1. **Overview Tab**: Key metrics and top entities
2. **Top Entities Tab**: Full entity list with charts
3. **Entity Deep Dive Tab**: Detailed entity analysis
4. **Discovered Entities Tab**: Review new entities

### Filters

- **Time Range**: Slider (1-90 days)
- **Platforms**: Multi-select (Instagram, YouTube, TikTok)
- **Entity Types**: Optional filter

### Features

- **Interactive Charts**: Zoom, pan, hover for details
- **CSV Export**: Download data from tables
- **Velocity Alerts**: Visual indicators for sentiment changes
- **Entity Comparison**: Compare multiple entities side-by-side

---

## Workflows

### Daily Ingestion Workflow

```bash
# 1. Ingest new data
python cli.py ingest --source esuit --file /data/daily_export.csv

# 2. Enrich new comments
python cli.py enrich --days 1

# 3. Check for alerts
python cli.py velocity "Taylor Swift"
python cli.py velocity "Blake Lively"

# 4. Review discovered entities
python cli.py review-entities --min-mentions 10
```

### Weekly Brief Generation

```bash
# Generate weekly brief
python cli.py brief \
  --start $(date -d "7 days ago" +%Y-%m-%d) \
  --end $(date +%Y-%m-%d) \
  --output weekly_brief.pdf

# Review in dashboard
streamlit run dashboard.py
```

### Entity Discovery Workflow

```bash
# 1. Review discovered entities
python cli.py review-entities --min-mentions 10

# 2. Add important entities
python cli.py add-entity "New Entity" --type person --aliases "Alias1"

# 3. Re-enrich to pick up new entity
python cli.py enrich --days 7
```

### Performance Optimization

```bash
# 1. Create indexes
python cli.py create-indexes

# 2. Check database status
python cli.py status --detailed

# 3. Review query performance in dashboard
streamlit run dashboard.py
```

---

## Troubleshooting

### Common Issues

#### Database Connection Failed

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U et_intel_user -d et_intel -h localhost

# Verify DATABASE_URL in .env
cat .env | grep DATABASE_URL
```

#### No Entities Found

```bash
# Check if entities are seeded
python cli.py status

# Re-seed if needed
python cli.py seed-entities

# Check enrichment ran
python cli.py enrich --days 1
```

#### Slow Queries

```bash
# Create indexes
python cli.py create-indexes

# Check database size
python cli.py status --detailed

# Review in dashboard for performance
streamlit run dashboard.py
```

#### Import Errors

```bash
# Verify dependencies
pip install -r requirements.txt

# Check spaCy model
python -m spacy download en_core_web_sm

# Verify Python version
python --version  # Should be 3.11+
```

### Getting Help

1. **Check logs**: Look for error messages in console output
2. **Use verbose mode**: Add `--verbose` flag to CLI commands
3. **Check status**: Run `python cli.py status` to verify system state
4. **Review documentation**: See `MD_DOCS/` for detailed guides

### Debug Mode

Enable debug logging:

```bash
# In .env file
LOG_LEVEL=DEBUG

# Or set environment variable
export LOG_LEVEL=DEBUG
python cli.py status
```

---

## Best Practices

1. **Regular Backups**: Run backup script daily
2. **Monitor Disk Space**: Check database size regularly
3. **Review Discovered Entities**: Weekly review of new entities
4. **Index Maintenance**: Create indexes after large imports
5. **Error Monitoring**: Check logs for warnings/errors

---

## Advanced Usage

### Custom Scripts

```python
from et_intel_core.db import get_session
from et_intel_core.analytics import AnalyticsService
from datetime import datetime, timedelta

session = get_session()
analytics = AnalyticsService(session)

# Custom analysis
end = datetime.utcnow()
start = end - timedelta(days=30)

df = analytics.get_top_entities((start, end))
print(df.head(10))
```

### Scheduled Jobs (Cron)

```bash
# Daily ingestion at 2 AM
0 2 * * * cd /opt/et-intel-02 && python cli.py ingest --source esuit --file /data/daily.csv

# Daily enrichment at 3 AM
0 3 * * * cd /opt/et-intel-02 && python cli.py enrich --days 1

# Weekly brief on Monday at 9 AM
0 9 * * 1 cd /opt/et-intel-02 && python cli.py brief --start "7 days ago" --end "today"
```

---

*Last Updated: 2025-11-24*

