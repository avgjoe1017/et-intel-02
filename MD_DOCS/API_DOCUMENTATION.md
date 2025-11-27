# ET Intelligence V2 - API Documentation

**Note**: This is a library-first architecture. Services are imported directly, not accessed via HTTP API. For Phase 2, a FastAPI wrapper can be added.

## Service Layer API

All services are in the `et_intel_core` package and can be imported directly.

---

## AnalyticsService

**Location**: `et_intel_core.analytics.service.AnalyticsService`

### Initialization

```python
from et_intel_core.db import get_session
from et_intel_core.analytics import AnalyticsService

session = get_session()
analytics = AnalyticsService(session)
```

### Methods

#### `get_top_entities(time_window, platforms=None, limit=20)`

Get top entities by mention count and sentiment.

**Parameters**:
- `time_window`: `Tuple[datetime, datetime]` - Start and end dates
- `platforms`: `Optional[List[str]]` - Filter by platform (e.g., ["instagram"])
- `limit`: `int` - Maximum number of entities to return (default: 20)

**Returns**: `pd.DataFrame` with columns:
- `entity_name`: Entity name
- `entity_type`: Entity type (person, show, couple, brand)
- `mention_count`: Number of comments mentioning entity
- `avg_sentiment`: Average sentiment score (-1.0 to 1.0)
- `total_likes`: Sum of likes on comments
- `weighted_sentiment`: Like-weighted average sentiment

**Example**:
```python
from datetime import datetime, timedelta

end = datetime.utcnow()
start = end - timedelta(days=30)

df = analytics.get_top_entities(
    (start, end),
    platforms=["instagram"],
    limit=10
)
print(df.head())
```

#### `compute_velocity(entity_id, window_hours=72, min_sample_size=10)`

Calculate sentiment velocity for live alerts.

**Parameters**:
- `entity_id`: `uuid.UUID` - Entity to analyze
- `window_hours`: `int` - Hours to look back (default: 72)
- `min_sample_size`: `int` - Minimum comments required (default: 10)

**Returns**: `Dict` with:
- `entity_id`: Entity UUID (as string)
- `window_hours`: Window size
- `recent_sentiment`: Average sentiment in recent window
- `previous_sentiment`: Average sentiment in previous window
- `percent_change`: Percent change
- `recent_sample_size`: Number of comments in recent window
- `previous_sample_size`: Number of comments in previous window
- `alert`: `bool` - True if |percent_change| > 30%
- `direction`: "up" or "down"
- `calculated_at`: Timestamp

Or `{"error": "message"}` if insufficient data.

**Example**:
```python
import uuid

entity_id = uuid.UUID("...")
velocity = analytics.compute_velocity(entity_id, window_hours=72)

if velocity.get('alert'):
    print(f"Alert! {velocity['percent_change']:+.1f}% change")
```

#### `compute_brief_velocity(entity_id, brief_window)`

Calculate velocity within a brief window (first half vs second half).

**Parameters**:
- `entity_id`: `uuid.UUID` - Entity to analyze
- `brief_window`: `Tuple[datetime, datetime]` - Brief time window

**Returns**: `Dict` with velocity metrics or `{"error": "message"}`

**Example**:
```python
start = datetime(2024, 1, 1)
end = datetime(2024, 1, 7)

velocity = analytics.compute_brief_velocity(entity_id, (start, end))
```

#### `get_entity_sentiment_history(entity_id, days=30)`

Get time series sentiment data for charts.

**Parameters**:
- `entity_id`: `uuid.UUID` - Entity to analyze
- `days`: `int` - Number of days to look back (default: 30)

**Returns**: `pd.DataFrame` with columns:
- `date`: Date (day granularity)
- `avg_sentiment`: Average sentiment for that day
- `mention_count`: Number of mentions that day
- `total_likes`: Sum of likes that day

**Example**:
```python
history_df = analytics.get_entity_sentiment_history(entity_id, days=30)
print(history_df.head())
```

#### `get_comment_count(time_window)`

Get count of comments in time window.

**Parameters**:
- `time_window`: `Tuple[datetime, datetime]` - Start and end dates

**Returns**: `int` - Number of comments

#### `get_discovered_entities(min_mentions=5, reviewed=False, limit=50)`

Get entities discovered by spaCy but not in monitoring.

**Parameters**:
- `min_mentions`: `int` - Minimum mention count (default: 5)
- `reviewed`: `bool` - Include only reviewed entities (default: False)
- `limit`: `int` - Maximum number to return (default: 50)

**Returns**: `pd.DataFrame` with discovered entity information

#### `get_entity_comparison(entity_ids, time_window)`

Compare multiple entities side-by-side.

**Parameters**:
- `entity_ids`: `List[uuid.UUID]` - Entities to compare
- `time_window`: `Tuple[datetime, datetime]` - Start and end dates

**Returns**: `pd.DataFrame` with comparison metrics

#### `get_sentiment_distribution(time_window, entity_id=None)`

Get distribution of sentiment labels.

**Parameters**:
- `time_window`: `Tuple[datetime, datetime]` - Start and end dates
- `entity_id`: `Optional[uuid.UUID]` - Optional entity filter

**Returns**: `Dict[str, int]` - Counts by label (e.g., {"positive": 100, "negative": 50})

---

## IngestionService

**Location**: `et_intel_core.services.ingestion.IngestionService`

### Initialization

```python
from et_intel_core.services.ingestion import IngestionService
from et_intel_core.sources.esuit import ESUITSource

session = get_session()
ingestion = IngestionService(session)
```

### Methods

#### `ingest(source)`

Ingest comments from any source.

**Parameters**:
- `source`: `IngestionSource` - Source adapter (ESUITSource, ApifySource, etc.)

**Returns**: `Dict` with statistics:
- `posts_created`: Number of new posts
- `posts_updated`: Number of updated posts
- `comments_created`: Number of new comments
- `comments_updated`: Number of updated comments

**Example**:
```python
from pathlib import Path

source = ESUITSource(Path("data/comments.csv"))
stats = ingestion.ingest(source)

print(f"Created {stats['comments_created']} comments")
```

---

## EnrichmentService

**Location**: `et_intel_core.services.enrichment.EnrichmentService`

### Initialization

```python
from et_intel_core.services.enrichment import EnrichmentService
from et_intel_core.nlp.entity_extractor import EntityExtractor
from et_intel_core.nlp.sentiment import get_sentiment_provider

session = get_session()
entity_catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()
extractor = EntityExtractor(entity_catalog)
sentiment_provider = get_sentiment_provider()

enrichment = EnrichmentService(session, extractor, sentiment_provider)
```

### Methods

#### `enrich_comments(comment_ids=None, since=None)`

Enrich comments with entities and sentiment.

**Parameters**:
- `comment_ids`: `Optional[List[uuid.UUID]]` - Specific comments to enrich
- `since`: `Optional[datetime]` - Only enrich comments after this date

**Returns**: `Dict` with statistics:
- `comments_processed`: Number of comments processed
- `signals_created`: Number of signals created
- `entities_discovered`: Number of new entities discovered

**Example**:
```python
from datetime import datetime, timedelta

since = datetime.utcnow() - timedelta(days=1)
stats = enrichment.enrich_comments(since=since)

print(f"Processed {stats['comments_processed']} comments")
```

---

## BriefBuilder

**Location**: `et_intel_core.reporting.brief_builder.BriefBuilder`

### Initialization

```python
from et_intel_core.reporting import BriefBuilder

builder = BriefBuilder(analytics)
```

### Methods

#### `build(start, end, platforms=None, focus_entities=None)`

Build intelligence brief from analytics.

**Parameters**:
- `start`: `datetime` - Start date
- `end`: `datetime` - End date
- `platforms`: `Optional[List[str]]` - Filter by platform
- `focus_entities`: `Optional[List[uuid.UUID]]` - Focus on specific entities

**Returns**: `IntelligenceBriefData` - Structured brief data

**Example**:
```python
from datetime import datetime

start = datetime(2024, 1, 1)
end = datetime(2024, 1, 7)

brief = builder.build(start, end, platforms=["instagram"])
print(brief.topline_summary)
```

---

## PDFRenderer

**Location**: `et_intel_core.reporting.pdf_renderer.PDFRenderer`

### Initialization

```python
from et_intel_core.reporting import PDFRenderer
from pathlib import Path

renderer = PDFRenderer(output_dir=Path("./reports"))
```

### Methods

#### `render(brief, filename=None)`

Render brief as PDF.

**Parameters**:
- `brief`: `IntelligenceBriefData` - Brief data to render
- `filename`: `Optional[str]` - Output filename (auto-generated if None)

**Returns**: `Path` - Path to generated PDF

**Example**:
```python
pdf_path = renderer.render(brief, filename="weekly_brief.pdf")
print(f"PDF generated: {pdf_path}")
```

---

## Error Handling

All services raise standard Python exceptions:

- `ValueError`: Invalid parameters
- `sqlalchemy.exc.SQLAlchemyError`: Database errors
- `FileNotFoundError`: Missing files
- `KeyError`: Missing configuration

**Example**:
```python
try:
    df = analytics.get_top_entities((start, end))
except Exception as e:
    logger.error(f"Error getting top entities: {e}")
    raise
```

---

## Best Practices

1. **Always use context managers or try/finally for sessions**:
   ```python
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

2. **Use timezone-aware datetimes**:
   ```python
   from datetime import datetime, timezone
   
   now = datetime.now(timezone.utc)
   ```

3. **Handle empty results gracefully**:
   ```python
   df = analytics.get_top_entities((start, end))
   if len(df) == 0:
       print("No entities found")
   ```

4. **Use logging for debugging**:
   ```python
   from et_intel_core.logging_config import get_logger
   
   logger = get_logger(__name__)
   logger.info("Processing entities...")
   ```

---

## Future: FastAPI Wrapper (Phase 2)

When external integrations are needed, wrap services in FastAPI:

```python
from fastapi import FastAPI, Depends
from et_intel_core.db import get_session
from et_intel_core.analytics import AnalyticsService

app = FastAPI()

@app.get("/api/v1/entities")
def list_entities(session = Depends(get_session)):
    analytics = AnalyticsService(session)
    df = analytics.get_top_entities(...)
    return df.to_dict('records')
```

---

*Last Updated: 2025-11-24*

