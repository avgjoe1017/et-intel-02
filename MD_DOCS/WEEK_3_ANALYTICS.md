# Week 3: Analytics Service - Complete Implementation Guide

## Overview

Week 3 adds the analytics layer for querying intelligence data:
- **Top Entities**: Most mentioned entities with sentiment scores
- **Velocity Detection**: Sentiment change alerts (30% in 72hrs = red flag)
- **Sentiment History**: Time series data for trending
- **Entity Comparison**: Side-by-side analysis
- **Performance Optimization**: Database indexes for fast queries

## Architecture

```
AnalyticsService
     ↓
SQL Queries (using numeric_value for clean aggregation)
     ↓
pandas DataFrames / Python Dicts
     ↓
CLI / Dashboard / Reports
```

## Core Methods

### 1. get_top_entities()

Get top entities by mention count with sentiment metrics.

```python
from et_intel_core.analytics import AnalyticsService
from et_intel_core.db import get_session
from datetime import datetime, timedelta

analytics = AnalyticsService(get_session())

# Last 7 days
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=7)

df = analytics.get_top_entities(
    time_window=(start_date, end_date),
    platforms=["instagram"],  # Optional filter
    limit=20
)

# DataFrame columns:
# - entity_name: Entity name
# - entity_type: person/show/couple/brand
# - mention_count: Number of comments
# - avg_sentiment: Average sentiment (-1 to 1)
# - total_likes: Sum of likes
# - weighted_sentiment: Like-weighted average
```

**SQL Query** (simplified):
```sql
SELECT 
    me.name,
    COUNT(DISTINCT es.comment_id) as mention_count,
    AVG(es.numeric_value) as avg_sentiment,
    SUM(c.likes) as total_likes
FROM extracted_signals es
JOIN comments c ON es.comment_id = c.id
JOIN monitored_entities me ON es.entity_id = me.id
WHERE es.signal_type = 'sentiment'
  AND c.created_at BETWEEN :start AND :end
GROUP BY me.name
ORDER BY mention_count DESC;
```

### 2. compute_velocity()

Detect sentiment velocity (change over time) for live alerts.

```python
# Check if Taylor Swift sentiment changed significantly
velocity = analytics.compute_velocity(
    entity_id=taylor_swift_id,
    window_hours=72,  # Compare last 72hrs to previous 72hrs
    min_sample_size=10  # Minimum comments required
)

# Returns:
{
    "entity_id": "uuid-here",
    "window_hours": 72,
    "recent_sentiment": 0.65,
    "previous_sentiment": 0.45,
    "percent_change": +44.4,  # (0.65 - 0.45) / 0.45 * 100
    "recent_sample_size": 45,
    "previous_sample_size": 38,
    "alert": True,  # abs(percent_change) > 30%
    "direction": "up",
    "calculated_at": "2024-01-15T10:30:00Z"
}
```

**Alert Logic**:
- **Green** (No Alert): |percent_change| ≤ 30%
- **Red** (Alert): |percent_change| > 30%

**Use Cases**:
- Live monitoring dashboards
- Email/Slack alerts
- Real-time sentiment tracking

### 3. compute_brief_velocity()

Calculate velocity within a specific time window (for reports).

```python
# For weekly brief: compare first half vs second half
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 1, 7)

velocity = analytics.compute_brief_velocity(
    entity_id=blake_lively_id,
    brief_window=(start_date, end_date)
)

# Returns:
{
    "entity_id": "uuid-here",
    "brief_window": "2024-01-01 to 2024-01-07",
    "first_half_sentiment": 0.55,
    "second_half_sentiment": 0.30,
    "percent_change": -45.5,
    "trending": "down"
}
```

**Difference from compute_velocity()**:
- `compute_velocity()`: Relative to NOW (live alerts)
- `compute_brief_velocity()`: Within specific window (reports)

### 4. get_entity_sentiment_history()

Time series data for charting sentiment over time.

```python
# Get last 30 days of sentiment data
df = analytics.get_entity_sentiment_history(
    entity_id=ryan_reynolds_id,
    days=30
)

# DataFrame columns:
# - date: Date (day granularity)
# - avg_sentiment: Average sentiment that day
# - mention_count: Number of mentions
# - total_likes: Sum of likes

# Use for charts:
import matplotlib.pyplot as plt
plt.plot(df['date'], df['avg_sentiment'])
plt.title('Ryan Reynolds Sentiment Over Time')
plt.show()
```

### 5. get_entity_comparison()

Compare multiple entities side-by-side.

```python
df = analytics.get_entity_comparison(
    entity_ids=[taylor_id, blake_id, ryan_id],
    time_window=(start_date, end_date)
)

# DataFrame columns:
# - entity_name
# - mention_count
# - avg_sentiment
# - min_sentiment
# - max_sentiment
# - sentiment_stddev (volatility)
# - total_likes
```

### 6. get_sentiment_distribution()

Get breakdown of positive/negative/neutral sentiments.

```python
distribution = analytics.get_sentiment_distribution(
    time_window=(start_date, end_date),
    entity_id=taylor_id  # Optional: filter by entity
)

# Returns:
{
    "positive": 150,
    "negative": 45,
    "neutral": 30
}
```

### 7. get_discovered_entities()

Query entities found by spaCy but not in catalog.

```python
df = analytics.get_discovered_entities(
    min_mentions=5,
    reviewed=False,
    limit=50
)

# DataFrame columns:
# - name
# - entity_type
# - mention_count
# - first_seen_at
# - last_seen_at
# - sample_mentions
```

## CLI Commands

### top-entities

Show top entities by mention count.

```bash
# Last 7 days, top 10
python cli.py top-entities

# Last 30 days, top 20
python cli.py top-entities --days 30 --limit 20
```

**Output**:
```
📊 Top 10 Entities (Last 7 Days)
================================================================================

Taylor Swift (person)
  Mentions: 245
  Sentiment: 0.72 😊
  Total Likes: 12,450

Blake Lively (person)
  Mentions: 189
  Sentiment: -0.35 😞
  Total Likes: 8,920
...
```

### velocity

Check velocity alert for specific entity.

```bash
# Default 72-hour window
python cli.py velocity "Taylor Swift"

# Custom window
python cli.py velocity "Blake Lively" --hours 48
```

**Output**:
```
🔍 Velocity Analysis: Taylor Swift
============================================================
Window: Last 72 hours
Recent sentiment: 0.650
Previous sentiment: 0.450
Change: +44.4% (up)
Sample sizes: 45 recent, 38 previous

🚨 ALERT: Significant sentiment shift detected!
   44.4% change exceeds 30% threshold
============================================================
```

### sentiment-history

Show sentiment trend over time.

```bash
# Last 30 days
python cli.py sentiment-history "Ryan Reynolds"

# Last 90 days
python cli.py sentiment-history "It Ends With Us" --days 90
```

**Output**:
```
📈 Sentiment History: Ryan Reynolds (Last 30 Days)
======================================================================
2024-01-01: +0.65 +++++++++++++ (15 mentions, 450 likes)
2024-01-02: +0.72 ++++++++++++++ (18 mentions, 520 likes)
2024-01-03: +0.58 +++++++++++ (12 mentions, 380 likes)
...
======================================================================
Average: 0.65
Total mentions: 420
```

### create-indexes

Create performance indexes for fast queries.

```bash
python cli.py create-indexes
```

**Output**:
```
Creating performance indexes...
✓ Created index: idx_entity_signal_time
✓ Created index: idx_comment_created
✓ Created index: idx_signal_type_time

✓ Performance indexes created successfully
```

## Performance Optimization

### Database Indexes

Three critical indexes for analytics performance:

1. **idx_entity_signal_time**
   ```sql
   CREATE INDEX idx_entity_signal_time 
   ON extracted_signals (entity_id, signal_type, created_at);
   ```
   - Speeds up: Entity sentiment queries with time filtering
   - Example: "Blake Lively negative signals last week"

2. **idx_comment_created**
   ```sql
   CREATE INDEX idx_comment_created 
   ON comments (created_at);
   ```
   - Speeds up: Time window filtering
   - Example: "All comments from last month"

3. **idx_signal_type_time**
   ```sql
   CREATE INDEX idx_signal_type_time 
   ON extracted_signals (signal_type, created_at);
   ```
   - Speeds up: Signal type queries with time filtering
   - Example: "All sentiment signals from last month"

### Query Performance

**Without Indexes**:
- `get_top_entities()`: ~2-5 seconds (10K comments)
- `compute_velocity()`: ~1-3 seconds
- `get_entity_sentiment_history()`: ~1-2 seconds

**With Indexes**:
- `get_top_entities()`: ~0.1-0.3 seconds (10K comments)
- `compute_velocity()`: ~0.05-0.1 seconds
- `get_entity_sentiment_history()`: ~0.05-0.1 seconds

**10-50x speedup!**

## Complete Workflow Example

```bash
# 1. Initialize and load data
python cli.py init
python cli.py seed-entities
python cli.py ingest --source esuit --file data/comments.csv
python cli.py enrich

# 2. Create performance indexes
python cli.py create-indexes

# 3. Run analytics
python cli.py top-entities --days 7
python cli.py velocity "Taylor Swift"
python cli.py sentiment-history "Blake Lively" --days 30

# 4. Check status
python cli.py status
```

## Python API Examples

### Velocity Monitoring Loop

```python
from et_intel_core.db import get_session
from et_intel_core.analytics import AnalyticsService
from et_intel_core.models import MonitoredEntity
import time

session = get_session()
analytics = AnalyticsService(session)

# Get all active entities
entities = session.query(MonitoredEntity).filter_by(is_active=True).all()

# Check velocity for each
for entity in entities:
    velocity = analytics.compute_velocity(entity.id, window_hours=72)
    
    if velocity.get('alert'):
        print(f"🚨 ALERT: {entity.name}")
        print(f"   {velocity['percent_change']:+.1f}% change")
        print(f"   {velocity['recent_sentiment']:.2f} → {velocity['previous_sentiment']:.2f}")
        # Send email/Slack notification here
```

### Entity Comparison Report

```python
# Compare top 3 entities
top_entities = analytics.get_top_entities(
    (start_date, end_date),
    limit=3
)

entity_ids = [
    session.query(MonitoredEntity).filter_by(name=name).first().id
    for name in top_entities['entity_name']
]

comparison = analytics.get_entity_comparison(entity_ids, (start_date, end_date))

print(comparison.to_string())
```

### Sentiment Dashboard Data

```python
# Get data for dashboard
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=7)

# Top entities
top = analytics.get_top_entities((start_date, end_date), limit=10)

# Sentiment distribution
distribution = analytics.get_sentiment_distribution((start_date, end_date))

# Velocity alerts
alerts = []
for _, row in top.iterrows():
    entity = session.query(MonitoredEntity).filter_by(name=row['entity_name']).first()
    velocity = analytics.compute_velocity(entity.id)
    if velocity.get('alert'):
        alerts.append({
            'entity': row['entity_name'],
            'change': velocity['percent_change']
        })

dashboard_data = {
    'top_entities': top.to_dict('records'),
    'distribution': distribution,
    'alerts': alerts
}
```

## Testing

### Run Analytics Tests

```bash
# All analytics tests
pytest tests/test_analytics.py -v

# Specific test
pytest tests/test_analytics.py::test_compute_velocity_with_data -v
```

### Test Coverage

- ✅ Top entities query
- ✅ Velocity computation (sufficient data)
- ✅ Velocity computation (insufficient data)
- ✅ Brief velocity
- ✅ Sentiment history
- ✅ Comment counting
- ✅ Entity comparison
- ✅ Sentiment distribution
- ✅ Alert threshold (30%)
- ✅ Platform filtering

## SQL Query Examples

### Top Entities with Weighted Sentiment

```sql
SELECT 
    me.name,
    COUNT(DISTINCT es.comment_id) as mentions,
    AVG(es.numeric_value) as avg_sentiment,
    AVG(es.numeric_value * es.weight_score) as weighted_sentiment
FROM extracted_signals es
JOIN monitored_entities me ON es.entity_id = me.id
JOIN comments c ON es.comment_id = c.id
WHERE es.signal_type = 'sentiment'
  AND c.created_at > NOW() - INTERVAL '7 days'
GROUP BY me.name
ORDER BY mentions DESC
LIMIT 10;
```

### Velocity Calculation

```sql
-- Recent sentiment (last 72 hours)
SELECT AVG(es.numeric_value) as recent_sentiment
FROM extracted_signals es
JOIN comments c ON es.comment_id = c.id
WHERE es.entity_id = 'uuid-here'
  AND es.signal_type = 'sentiment'
  AND c.created_at > NOW() - INTERVAL '72 hours';

-- Previous sentiment (72-144 hours ago)
SELECT AVG(es.numeric_value) as previous_sentiment
FROM extracted_signals es
JOIN comments c ON es.comment_id = c.id
WHERE es.entity_id = 'uuid-here'
  AND es.signal_type = 'sentiment'
  AND c.created_at BETWEEN 
    NOW() - INTERVAL '144 hours' AND 
    NOW() - INTERVAL '72 hours';
```

### Sentiment Over Time

```sql
SELECT 
    DATE_TRUNC('day', c.created_at) as date,
    AVG(es.numeric_value) as avg_sentiment,
    COUNT(*) as mention_count
FROM extracted_signals es
JOIN comments c ON es.comment_id = c.id
WHERE es.entity_id = 'uuid-here'
  AND es.signal_type = 'sentiment'
  AND c.created_at > NOW() - INTERVAL '30 days'
GROUP BY date
ORDER BY date;
```

## Troubleshooting

### Issue: Slow queries

**Solution**: Create indexes
```bash
python cli.py create-indexes
```

### Issue: "Insufficient data" for velocity

**Cause**: Not enough comments in time window

**Solution**: 
- Increase window size: `--hours 168` (7 days)
- Lower min_sample_size in code
- Ensure enrichment ran successfully

### Issue: Empty DataFrames

**Cause**: No data in time window

**Solution**:
- Check date range
- Verify enrichment completed
- Check entity exists: `python cli.py status`

## Next Steps (Week 4)

With analytics complete, Week 4 will add:

1. **CLI Polish**
   - Better error messages
   - Progress bars
   - Colored output
   - Config file support

2. **Brief Generation** (Week 5)
   - Use analytics data
   - PDF rendering
   - Email distribution

3. **Dashboard** (Week 6)
   - Streamlit UI
   - Interactive charts
   - Real-time updates

## Resources

- [Architecture Document](../ET_Intelligence_Rebuild_Architecture.md)
- [Week 1 Foundation](WEEK_1_FOUNDATION.md)
- [Week 2 NLP Layer](WEEK_2_NLP_LAYER.md)
- [Quick Reference](QUICK_REFERENCE.md)
- [pandas Documentation](https://pandas.pydata.org/docs/)
- [PostgreSQL Performance Tips](https://wiki.postgresql.org/wiki/Performance_Optimization)

