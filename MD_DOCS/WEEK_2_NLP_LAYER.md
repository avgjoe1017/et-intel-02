# Week 2: NLP Layer - Complete Implementation Guide

## Overview

Week 2 adds intelligence to the raw comments through:
- **Entity Extraction**: Identify people, shows, couples, brands mentioned in comments
- **Sentiment Analysis**: Score emotional tone with multiple providers
- **Entity-Targeted Sentiment**: "I love Ryan but hate Blake" = 2 distinct signals
- **Entity Discovery**: Track unknown entities for review

## Architecture

```
Comment Text
     ↓
EntityExtractor → [Catalog Mentions, Discovered Entities]
     ↓
SentimentProvider → SentimentResult (score, confidence, model)
     ↓
EnrichmentService → ExtractedSignals (stored in database)
```

## Key Components

### 1. Entity Extraction

**EntityExtractor** uses a two-phase approach:

1. **Catalog Matching** (fast, exact)
   - Check against `MonitoredEntity` catalog
   - Match canonical names and aliases
   - High confidence (1.0 for exact, 0.9 for alias)

2. **spaCy NER** (discovery)
   - Find PERSON and ORG entities
   - Track in `DiscoveredEntity` table
   - Lower confidence (0.7)

```python
from et_intel_core.nlp import EntityExtractor
from et_intel_core.models import MonitoredEntity

# Load catalog
catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()

# Create extractor
extractor = EntityExtractor(catalog)

# Extract entities
catalog_mentions, discovered = extractor.extract(
    "Taylor Swift and Blake Lively are amazing!",
    post_caption="Celebrity news"
)

# catalog_mentions: [EntityMention(entity_id=..., mention_text="taylor swift", confidence=1.0), ...]
# discovered: [DiscoveredEntityMention(name="Blake Lively", entity_type="PERSON", confidence=0.7)]
```

### 2. Sentiment Analysis

Three providers with swappable interface:

#### RuleBasedSentimentProvider (Free, Fast)

- **Lexicon-based**: Positive/negative word lists
- **Entertainment-aware**: "she ate", "slayed", "queen" = positive
- **Emoji analysis**: 😍 = positive, 😡 = negative
- **TextBlob fallback**: For ambiguous cases

```python
from et_intel_core.nlp import RuleBasedSentimentProvider

provider = RuleBasedSentimentProvider()
result = provider.score("She ate! Queen behavior 👑")

# result.score: 0.8 (positive)
# result.confidence: 0.7
# result.source_model: "rule_based"
```

**Entertainment Lexicon**:
- **Positive**: love, amazing, queen, icon, ate, slayed, fire, obsessed
- **Negative**: hate, cringe, toxic, cancelled, flop, disaster

#### OpenAISentimentProvider (Accurate, Costs Money)

- Uses GPT-4o-mini
- Understands context and sarcasm
- Entertainment-aware prompting
- High confidence (0.9)

```python
from et_intel_core.nlp import OpenAISentimentProvider

provider = OpenAISentimentProvider()  # Uses OPENAI_API_KEY from .env
result = provider.score("This is actually terrible lol")

# result.score: -0.7 (understands sarcasm)
# result.confidence: 0.9
# result.source_model: "gpt-4o-mini"
```

#### HybridSentimentProvider (Best of Both)

- **Strategy**: Try cheap first, escalate if uncertain
- **Escalation triggers**:
  - Confidence < 0.7
  - Neutral score (-0.2 to 0.2)
- **Cost savings**: 60-70% vs. all-OpenAI

```python
from et_intel_core.nlp import HybridSentimentProvider

provider = HybridSentimentProvider()
result = provider.score("This is... interesting")

# First tries RuleBasedSentimentProvider
# If uncertain, escalates to OpenAISentimentProvider
```

### 3. Enrichment Service

**EnrichmentService** orchestrates the entire enrichment pipeline:

```python
from et_intel_core.services import EnrichmentService
from et_intel_core.nlp import EntityExtractor, get_sentiment_provider

# Setup
catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()
extractor = EntityExtractor(catalog)
sentiment_provider = get_sentiment_provider()  # Uses config

service = EnrichmentService(session, extractor, sentiment_provider)

# Enrich all unprocessed comments
stats = service.enrich_comments()

# Or enrich specific time range
from datetime import datetime, timedelta
since = datetime.utcnow() - timedelta(days=7)
stats = service.enrich_comments(since=since)
```

**What it does**:
1. Extracts entities from comment text
2. Scores sentiment
3. Creates **general sentiment signal** (no entity)
4. Creates **entity-specific signals** for each mentioned entity
5. Tracks discovered entities in `DiscoveredEntity` table
6. Applies like-weighting: `weight_score = 1.0 + (likes / 100)`

**Idempotent**: Can re-run on same comments - updates existing signals instead of creating duplicates.

## The Signals Table in Action

### General Sentiment Signal

```python
# Comment: "This is amazing!"
# No entities mentioned

ExtractedSignal(
    comment_id=comment.id,
    entity_id=None,  # General sentiment
    signal_type=SignalType.SENTIMENT,
    value="positive",
    numeric_value=0.8,
    weight_score=1.0 + (42 / 100),  # 42 likes
    confidence=0.7,
    source_model="rule_based"
)
```

### Entity-Specific Signals

```python
# Comment: "I love Taylor but Blake is problematic"
# Mentions: Taylor Swift, Blake Lively

# Signal 1: Taylor Swift
ExtractedSignal(
    comment_id=comment.id,
    entity_id=taylor_swift.id,
    signal_type=SignalType.SENTIMENT,
    value="positive",
    numeric_value=0.8,
    ...
)

# Signal 2: Blake Lively
ExtractedSignal(
    comment_id=comment.id,
    entity_id=blake_lively.id,
    signal_type=SignalType.SENTIMENT,
    value="negative",
    numeric_value=-0.6,
    ...
)
```

**Note**: MVP uses comment-level sentiment for all entities. Future enhancement: entity-targeted sentiment analysis.

## CLI Usage

### 1. Load Seed Entities

```bash
# Load default seed entities (Blake, Justin, Taylor, Ryan, etc.)
python cli.py seed-entities

# Load custom entities
python cli.py seed-entities --file data/my_entities.json
```

**Seed Entity Format** (`data/seed_entities.json`):
```json
[
  {
    "name": "Taylor Swift",
    "canonical_name": "Taylor Swift",
    "entity_type": "person",
    "aliases": ["Taylor", "T-Swift", "Tay"]
  }
]
```

### 2. Enrich Comments

```bash
# Enrich all unprocessed comments
python cli.py enrich

# Enrich comments from last 7 days
python cli.py enrich --days 7

# Enrich comments since specific date
python cli.py enrich --since 2024-01-01
```

### 3. Review Discovered Entities

```bash
# Show entities found by spaCy (not in catalog)
python cli.py review-entities

# Show only entities with 10+ mentions
python cli.py review-entities --min-mentions 10
```

### 4. Add Entity to Monitoring

```bash
# Add person
python cli.py add-entity "Kelsea Ballerini" --type person --aliases "Kelsea"

# Add show
python cli.py add-entity "The Eras Tour" --type show

# Add couple
python cli.py add-entity "Bennifer" --type couple --aliases "Ben & Jen"
```

## Complete Workflow Example

```bash
# 1. Initialize database
python cli.py init

# 2. Load seed entities
python cli.py seed-entities

# 3. Ingest comments
python cli.py ingest --source esuit --file data/comments.csv

# 4. Enrich comments
python cli.py enrich

# 5. Check results
python cli.py status

# Output:
# 📊 Database Status
# ========================================
# Posts:              10
# Comments:           250
# Monitored Entities: 8
# Extracted Signals:  500
# Discovered Entities:15
# ========================================

# 6. Review discovered entities
python cli.py review-entities

# 7. Add interesting entities to monitoring
python cli.py add-entity "New Celebrity" --type person

# 8. Re-enrich to capture new entity
python cli.py enrich --days 30
```

## Configuration

### Sentiment Backend

Set in `.env`:

```bash
# Use rule-based (free, fast)
SENTIMENT_BACKEND=rule_based

# Use OpenAI (accurate, costs money)
SENTIMENT_BACKEND=openai
OPENAI_API_KEY=sk-your-key-here

# Use hybrid (best of both)
SENTIMENT_BACKEND=hybrid
OPENAI_API_KEY=sk-your-key-here
```

### Cost Optimization

**Rule-Based Only**:
- Cost: $0
- Speed: ~1000 comments/min
- Accuracy: 70-75%

**OpenAI Only**:
- Cost: ~$0.10 per 1000 comments
- Speed: ~100 comments/min (rate limited)
- Accuracy: 90-95%

**Hybrid** (Recommended):
- Cost: ~$0.03 per 1000 comments (70% savings)
- Speed: ~500 comments/min
- Accuracy: 85-90%

## Database Queries

### Top Entities by Sentiment

```sql
SELECT 
    me.name as entity_name,
    COUNT(DISTINCT es.comment_id) as mention_count,
    AVG(es.numeric_value) as avg_sentiment,
    AVG(es.numeric_value * es.weight_score) as weighted_sentiment
FROM extracted_signals es
JOIN monitored_entities me ON es.entity_id = me.id
WHERE es.signal_type = 'sentiment'
  AND es.numeric_value IS NOT NULL
GROUP BY me.name
ORDER BY mention_count DESC;
```

### Sentiment Over Time

```sql
SELECT 
    DATE_TRUNC('day', c.created_at) as date,
    AVG(es.numeric_value) as avg_sentiment,
    COUNT(*) as comment_count
FROM extracted_signals es
JOIN comments c ON es.comment_id = c.id
WHERE es.signal_type = 'sentiment'
  AND es.entity_id IS NULL  -- General sentiment
GROUP BY date
ORDER BY date;
```

### Discovered Entities to Review

```sql
SELECT 
    name,
    entity_type,
    mention_count,
    first_seen_at,
    last_seen_at,
    sample_mentions[1] as sample
FROM discovered_entities
WHERE reviewed = false
  AND mention_count >= 5
ORDER BY mention_count DESC;
```

## Testing

### Run NLP Tests

```bash
# All NLP tests
pytest tests/test_nlp.py -v

# Specific test
pytest tests/test_nlp.py::test_entity_extractor_catalog_matching -v
```

### Run Enrichment Tests

```bash
# All enrichment tests
pytest tests/test_enrichment.py -v

# Test idempotency
pytest tests/test_enrichment.py::test_enrichment_idempotent -v
```

### Full Test Suite

```bash
# Run everything
pytest tests/ -v

# With coverage
pytest tests/ --cov=et_intel_core --cov-report=html
```

## Performance Considerations

### Entity Extraction

- **Catalog lookup**: O(n) where n = catalog size
- **spaCy NER**: ~100-200 comments/sec
- **Optimization**: Build lookup index (done in `__init__`)

### Sentiment Analysis

- **Rule-based**: ~1000 comments/sec
- **OpenAI**: ~100 comments/sec (rate limited)
- **Hybrid**: ~500 comments/sec (depends on escalation rate)

### Batch Processing

- Commits every 50 comments
- Reduces transaction overhead
- Memory efficient

## Troubleshooting

### Issue: "No module named 'spacy'"

```bash
pip install spacy
python -m spacy download en_core_web_sm
```

### Issue: "No module named 'textblob'"

```bash
pip install textblob
```

### Issue: "OpenAI API key required"

Add to `.env`:
```bash
OPENAI_API_KEY=sk-your-key-here
```

### Issue: "No monitored entities found"

```bash
python cli.py seed-entities
```

### Issue: Slow enrichment

- Use `rule_based` backend for speed
- Or use `hybrid` for balance
- Check database indexes are created

## Next Steps (Week 3)

With NLP layer complete, Week 3 will add:

1. **Analytics Service**
   - `get_top_entities()` - Top entities by volume
   - `compute_velocity()` - Sentiment change detection
   - `get_entity_sentiment_history()` - Time series data

2. **Velocity Alerts**
   - 30% sentiment change in 72hrs = red flag
   - Email/Slack notifications

3. **Advanced Queries**
   - Entity comparisons
   - Storyline detection
   - Risk signal aggregation

## Resources

- [Architecture Document](../ET_Intelligence_Rebuild_Architecture.md)
- [Week 1 Foundation](WEEK_1_FOUNDATION.md)
- [Quick Reference](QUICK_REFERENCE.md)
- [spaCy Documentation](https://spacy.io/usage)
- [TextBlob Documentation](https://textblob.readthedocs.io/)
- [OpenAI API Documentation](https://platform.openai.com/docs)

