# Week 1: Foundation - Complete Implementation Guide

## Overview

Week 1 establishes the foundational architecture for ET Intelligence V2:
- PostgreSQL database schema with SQLAlchemy 2.0 models
- Source-agnostic ingestion system
- Idempotent data loading
- Comprehensive test coverage

## Architecture Decisions

### 1. The Signals Table - The Killer Feature

Instead of storing sentiment as a column in comments:

```python
# ❌ V1 Approach
class Comment:
    sentiment: float
    weighted_sentiment: float
    emotion: str  # Adding this requires migration!

# ✅ V2 Approach
class Comment:
    # Just the facts
    text: str
    author: str
    created_at: datetime

class ExtractedSignal:
    comment_id: UUID
    signal_type: SignalType  # sentiment, emotion, storyline, risk
    value: str               # "negative", "anger", "lawsuit"
    numeric_value: float     # -0.9 (for sentiment/scores)
    source_model: str        # "textblob", "gpt-4o-mini"
```

**Benefits:**
- Multiple models can score the same comment
- Entity-targeted sentiment ("I love Ryan but hate Blake" = 2 signals)
- Add new signal types without schema migrations
- Clean SQL queries using `numeric_value` column

### 2. Library-First Architecture

No HTTP/API layer in MVP. Services are imported directly:

```python
# CLI imports services directly
from et_intel_core.services import IngestionService
from et_intel_core.db import get_session

session = get_session()
service = IngestionService(session)
stats = service.ingest(source)
```

**Benefits:**
- Simpler development (no auth, CORS, deployment complexity)
- Direct debugging (function calls, not HTTP requests)
- Faster iteration (no server to restart)
- Can add FastAPI wrapper later when needed

### 3. Synchronous by Default

CSV ingestion is synchronous:

```python
def iter_records(self) -> Iterator[RawComment]:
    """Synchronous CSV reading - no async needed"""
    df = pd.read_csv(self.csv_path)
    for _, row in df.iterrows():
        yield RawComment(...)
```

**Why?**
- CSV files are local (no network latency to hide)
- Volumes are modest (<10K comments typical)
- Simpler debugging (no async/await ceremony)
- Add async only when fetching from APIs with rate limits

### 4. Idempotent Ingestion

Re-running ingestion doesn't create duplicates:

```python
# Check if comment exists
existing = session.query(Comment).filter(
    Comment.post_id == post.id,
    Comment.author_name == record.comment_author,
    Comment.text == record.comment_text,
    Comment.created_at == record.comment_timestamp
).first()

if existing:
    # Update metrics (likes might have changed)
    existing.likes = record.like_count
else:
    # Create new comment
    comment = Comment(...)
```

## Database Schema

### Core Tables

1. **posts** - Container for comments
   - `id` (UUID, PK)
   - `platform` (instagram/youtube/tiktok)
   - `external_id` (platform's post ID)
   - `url` (link to post)
   - `subject_line` (editorial context)
   - `posted_at` (timestamp)
   - `raw_data` (JSONB - safety net for API changes)

2. **comments** - Atomic unit of data
   - `id` (UUID, PK)
   - `post_id` (FK to posts)
   - `author_name` (username)
   - `text` (comment content)
   - `created_at` (timestamp, indexed)
   - `likes` (engagement metric)
   - `reply_count` (threading)
   - `parent_id` (FK to comments, for threading)
   - `context_type` (direct/reply/thread)
   - `metadata` (JSONB for extensions)

3. **monitored_entities** - Dynamic configuration
   - `id` (UUID, PK)
   - `name` (unique)
   - `canonical_name` ("JLO" → "Jennifer Lopez")
   - `entity_type` (person/show/couple/brand)
   - `is_active` (boolean)
   - `aliases` (JSONB array of alternate names)

4. **extracted_signals** - Intelligence layer
   - `id` (UUID, PK)
   - `comment_id` (FK to comments)
   - `entity_id` (FK to monitored_entities, nullable)
   - `signal_type` (sentiment/emotion/storyline/risk_flag)
   - `value` (human-readable: "negative", "anger")
   - `numeric_value` (for scores: -0.9, nullable)
   - `weight_score` (like-weighted importance)
   - `confidence` (model confidence)
   - `source_model` (which algorithm)
   - `created_at` (timestamp)
   - Unique constraint: (comment_id, entity_id, signal_type, source_model)

5. **discovered_entities** - Tracking unknowns
   - `id` (UUID, PK)
   - `name` (unique)
   - `entity_type` (from spaCy: PERSON, ORG)
   - `first_seen_at` / `last_seen_at`
   - `mention_count`
   - `sample_mentions` (JSONB array)
   - `reviewed` (boolean)
   - `reviewed_at` / `action_taken`

## File Structure

```
et-intel-02/
├── et_intel_core/              # Core library
│   ├── __init__.py
│   ├── config.py               # Pydantic settings
│   ├── db.py                   # Database connection
│   ├── schemas.py              # Pydantic validation models
│   ├── models/                 # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── enums.py
│   │   ├── post.py
│   │   ├── comment.py
│   │   ├── monitored_entity.py
│   │   ├── extracted_signal.py
│   │   └── discovered_entity.py
│   ├── sources/                # Ingestion adapters
│   │   ├── __init__.py
│   │   ├── base.py             # Protocol
│   │   ├── esuit.py            # ESUIT CSV adapter
│   │   └── apify.py            # Apify CSV adapter
│   └── services/               # Business logic
│       ├── __init__.py
│       └── ingestion.py        # IngestionService
├── alembic/                    # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/                      # Unit tests
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_models.py
│   └── test_ingestion.py
├── data/                       # CSV files
│   └── sample_esuit.csv
├── reports/                    # Generated reports
├── cli.py                      # Command-line interface
├── requirements.txt
├── alembic.ini
└── README.md
```

## Usage Examples

### Initialize Database

```bash
python cli.py init
```

### Ingest Data

```bash
# ESUIT format
python cli.py ingest --source esuit --file data/sample_esuit.csv

# Apify format
python cli.py ingest --source apify --file data/apify_export.csv
```

### Check Status

```bash
python cli.py status
```

### Run Tests

```bash
pytest tests/ -v
```

## Key Implementation Patterns

### 1. Protocol-Based Interfaces

```python
class IngestionSource(Protocol):
    """Every CSV/API adapter implements this"""
    def iter_records(self) -> Iterator[RawComment]:
        ...

# Implementations
class ESUITSource(IngestionSource): ...
class ApifySource(IngestionSource): ...
class InstagramAPISource(IngestionSource): ...  # Future
```

### 2. Pydantic Validation

```python
class RawComment(BaseModel):
    """Validates and normalizes data from any source"""
    platform: str
    external_post_id: str
    post_url: str
    comment_author: str
    comment_text: str
    comment_timestamp: datetime
    like_count: int = 0
    raw: dict = Field(default_factory=dict)
```

### 3. Batch Commits

```python
for record in source.iter_records():
    # Process record
    ...
    
    # Commit every 100 records
    if (stats["comments_created"] + stats["comments_updated"]) % 100 == 0:
        session.commit()

# Final commit
session.commit()
```

## Testing Strategy

### Unit Tests

- **test_models.py**: SQLAlchemy model creation and relationships
- **test_ingestion.py**: Source parsing and ingestion service

### Test Database

Uses in-memory SQLite for fast, isolated tests:

```python
@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    # ... return session
```

### Test Coverage

- ✅ Model creation (all 5 tables)
- ✅ Relationships (post→comments, comment→signals)
- ✅ CSV parsing (ESUIT and Apify formats)
- ✅ Idempotent ingestion (no duplicates)
- ✅ Like count updates

## Next Steps (Week 2)

1. **NLP Layer**
   - EntityExtractor with spaCy
   - SentimentProvider interface
   - RuleBasedSentimentProvider
   - OpenAISentimentProvider
   - HybridSentimentProvider
   - EnrichmentService

2. **Initial Entity Catalog**
   - Load seed entities (Blake Lively, Justin Baldoni, Taylor Swift, etc.)
   - CLI command to add entities

3. **Entity Discovery**
   - spaCy NER for unknown entities
   - Track in discovered_entities table

## Validation Checklist

- [x] Can create all 5 model types
- [x] Relationships work correctly
- [x] Can parse ESUIT CSV format
- [x] Can parse Apify CSV format
- [x] Ingestion creates posts and comments
- [x] Ingestion is idempotent (no duplicates)
- [x] Like counts update on re-ingestion
- [x] CLI commands work
- [x] Tests pass

## Performance Considerations

### Batch Commits
- Commit every 100 records (configurable)
- Balance between memory usage and transaction overhead

### Indexes
- `comments.created_at` (indexed) - for time-based queries
- `posts.external_id` (indexed) - for upsert lookups
- Composite index on `extracted_signals` (comment_id, entity_id, signal_type, source_model)

### Connection Pooling
- Pool size: 5
- Max overflow: 10
- Pre-ping enabled (verify connections before use)

## Troubleshooting

### Common Issues

1. **PostgreSQL connection fails**
   - Check DATABASE_URL in .env
   - Ensure PostgreSQL is running
   - Verify credentials

2. **CSV parsing errors**
   - Check column names match expected format
   - Verify timestamp format
   - Ensure no missing required columns

3. **Duplicate key errors**
   - Should not happen (idempotent design)
   - Check unique constraints
   - Verify upsert logic

## Resources

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Architecture Document](../ET_Intelligence_Rebuild_Architecture.md)

