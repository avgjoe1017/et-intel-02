# ET Intelligence V2 - Quick Reference

## Common Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Initialize database
python cli.py init
```

### Data Ingestion
```bash
# ESUIT format
python cli.py ingest --source esuit --file data/comments.csv

# Apify format
python cli.py ingest --source apify --file data/apify_export.csv

# Check status
python cli.py status
```

### Entity Management (Week 2)
```bash
# Load seed entities
python cli.py seed-entities

# Load custom entities
python cli.py seed-entities --file data/my_entities.json

# Add entity manually
python cli.py add-entity "Celebrity Name" --type person --aliases "Nickname"

# Review discovered entities
python cli.py review-entities --min-mentions 5
```

### Enrichment (Week 2)
```bash
# Enrich all unprocessed comments
python cli.py enrich

# Enrich last 7 days
python cli.py enrich --days 7

# Enrich since specific date
python cli.py enrich --since 2024-01-01
```

### Analytics (Week 3)
```bash
# Show top entities
python cli.py top-entities --days 7 --limit 10

# Export top entities to CSV
python cli.py top-entities --days 7 --export top_entities.csv

# Check velocity alert
python cli.py velocity "Taylor Swift" --hours 72

# Show sentiment history
python cli.py sentiment-history "Blake Lively" --days 30

# Export sentiment history
python cli.py sentiment-history "Blake Lively" --export history.csv

# Create performance indexes
python cli.py create-indexes
```

### Reporting (Week 5)
```bash
# Generate intelligence brief
python cli.py brief --start 2024-01-01 --end 2024-01-07

# Brief with platform filter
python cli.py brief --start 2024-01-01 --end 2024-01-07 \
    --platforms instagram --platforms youtube

# Brief with custom filename
python cli.py brief --start 2024-01-01 --end 2024-01-07 \
    --output weekly_brief.pdf

# Brief with JSON export
python cli.py brief --start 2024-01-01 --end 2024-01-07 --json
```

### System Information (Week 4)
```bash
# Show version and system info
python cli.py version

# Detailed database status
python cli.py status --detailed

# Verbose mode for debugging
python cli.py enrich --days 7 --verbose

# Force reinitialize database
python cli.py init --force
```

### Database Operations
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Check current version
alembic current

# View history
alembic history
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=et_intel_core --cov-report=html

# Run specific test file
pytest tests/test_models.py -v

# Run specific test
pytest tests/test_models.py::test_create_post -v
```

### Development
```bash
# Format code
black .

# Lint
flake8 et_intel_core/

# Type check
mypy et_intel_core/
```

## Database Schema Quick Reference

### Posts
```sql
SELECT id, platform, external_id, subject_line, posted_at
FROM posts
ORDER BY posted_at DESC
LIMIT 10;
```

### Comments
```sql
SELECT c.id, c.author_name, c.text, c.likes, c.created_at, p.subject_line
FROM comments c
JOIN posts p ON c.post_id = p.id
ORDER BY c.created_at DESC
LIMIT 10;
```

### Extracted Signals
```sql
-- Sentiment by entity
SELECT 
    me.name as entity_name,
    AVG(es.numeric_value) as avg_sentiment,
    COUNT(*) as signal_count
FROM extracted_signals es
JOIN monitored_entities me ON es.entity_id = me.id
WHERE es.signal_type = 'sentiment'
GROUP BY me.name
ORDER BY avg_sentiment DESC;
```

### Monitored Entities
```sql
SELECT id, name, canonical_name, entity_type, is_active
FROM monitored_entities
WHERE is_active = true
ORDER BY name;
```

### Discovered Entities
```sql
SELECT name, entity_type, mention_count, first_seen_at, last_seen_at
FROM discovered_entities
WHERE reviewed = false
ORDER BY mention_count DESC
LIMIT 20;
```

## Python API Quick Reference

### Database Session
```python
from et_intel_core.db import get_session

session = get_session()
try:
    # Do work
    session.commit()
except Exception:
    session.rollback()
    raise
finally:
    session.close()
```

### Ingestion
```python
from pathlib import Path
from et_intel_core.db import get_session
from et_intel_core.services import IngestionService
from et_intel_core.sources import ESUITSource

# Create source
source = ESUITSource(Path("data/comments.csv"))

# Ingest
session = get_session()
service = IngestionService(session)
stats = service.ingest(source)

print(f"Created {stats['comments_created']} comments")
session.close()
```

### Query Models
```python
from et_intel_core.db import get_session
from et_intel_core.models import Post, Comment, MonitoredEntity

session = get_session()

# Get all posts
posts = session.query(Post).all()

# Get comments for a post
post = session.query(Post).first()
comments = post.comments

# Get entity by name
entity = session.query(MonitoredEntity).filter_by(
    name="Taylor Swift"
).first()

session.close()
```

### Create Models
```python
from datetime import datetime
from et_intel_core.db import get_session
from et_intel_core.models import MonitoredEntity, EntityType

session = get_session()

# Create entity
entity = MonitoredEntity(
    name="Taylor Swift",
    canonical_name="Taylor Swift",
    entity_type=EntityType.PERSON,
    is_active=True,
    aliases=["T-Swift", "Tay"]
)

session.add(entity)
session.commit()
session.close()
```

## File Locations

### Configuration
- `.env` - Environment variables (create from `env.example`)
- `alembic.ini` - Alembic configuration
- `requirements.txt` - Python dependencies

### Code
- `et_intel_core/` - Core library
- `et_intel_core/models/` - Database models
- `et_intel_core/services/` - Business logic
- `et_intel_core/sources/` - Data source adapters
- `cli.py` - Command-line interface

### Data
- `data/` - CSV input files
- `reports/` - Generated reports (PDF, JSON)
- `alembic/versions/` - Database migrations

### Documentation
- `README.md` - Quick start guide
- `PROGRESS.md` - Build progress log
- `PRODUCTION_INSTRUCTIONS.md` - Deployment guide
- `MD_DOCS/` - Supplemental documentation
- `ET_Intelligence_Rebuild_Architecture.md` - Full architecture

### Tests
- `tests/` - Unit tests
- `tests/conftest.py` - Pytest fixtures
- `tests/test_models.py` - Model tests
- `tests/test_ingestion.py` - Ingestion tests

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/et_intel

# OpenAI API (optional)
OPENAI_API_KEY=sk-your-key-here

# Sentiment Backend
SENTIMENT_BACKEND=rule_based  # or "openai" or "hybrid"

# Logging
LOG_LEVEL=INFO  # or DEBUG, WARNING, ERROR
```

## Common Patterns

### Idempotent Ingestion
```python
# Check if record exists
existing = session.query(Comment).filter(
    Comment.post_id == post.id,
    Comment.author_name == author,
    Comment.text == text,
    Comment.created_at == timestamp
).first()

if existing:
    # Update
    existing.likes = new_likes
else:
    # Create
    comment = Comment(...)
    session.add(comment)
```

### Batch Processing
```python
for i, record in enumerate(records):
    # Process record
    ...
    
    # Commit every 100 records
    if (i + 1) % 100 == 0:
        session.commit()

# Final commit
session.commit()
```

### Protocol-Based Design
```python
from typing import Protocol, Iterator

class IngestionSource(Protocol):
    def iter_records(self) -> Iterator[RawComment]:
        ...

# Any class implementing this protocol works
class MySource:
    def iter_records(self) -> Iterator[RawComment]:
        # Implementation
        yield RawComment(...)
```

## Troubleshooting

### Database Connection Issues
```python
# Test connection
from et_intel_core.db import engine
with engine.connect() as conn:
    result = conn.execute("SELECT 1")
    print(result.scalar())
```

### Check Table Exists
```sql
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public';
```

### Reset Database (DANGER!)
```python
from et_intel_core.db import drop_db, init_db

drop_db()  # WARNING: Deletes all data!
init_db()
```

### View Logs
```bash
# Application logs (if configured)
tail -f /var/log/et-intel/app.log

# PostgreSQL logs
tail -f /var/log/postgresql/postgresql-15-main.log
```

## Performance Tips

1. **Batch Commits**: Commit every 100-1000 records, not per record
2. **Use Indexes**: Already configured on `created_at` and `external_id`
3. **Connection Pooling**: Already configured (pool_size=5, max_overflow=10)
4. **VACUUM**: Run `VACUUM ANALYZE` periodically on large tables
5. **Monitor Query Performance**: Use `EXPLAIN ANALYZE` for slow queries

## Security Checklist

- [ ] Strong database password (16+ characters)
- [ ] `.env` file has 600 permissions
- [ ] OpenAI API key rotated regularly
- [ ] Database backups enabled
- [ ] PostgreSQL only accepts local connections (or SSL for remote)
- [ ] Application runs as non-root user
- [ ] Logs don't contain sensitive data

## Resources

- [Architecture Document](../ET_Intelligence_Rebuild_Architecture.md)
- [Week 1 Foundation Guide](WEEK_1_FOUNDATION.md)
- [Production Instructions](../PRODUCTION_INSTRUCTIONS.md)
- [Progress Log](../PROGRESS.md)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Click Docs](https://click.palletsprojects.com/)

