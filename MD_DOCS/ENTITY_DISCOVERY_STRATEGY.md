# Entity Discovery Strategy

## Do You Need a Massive Celebrity Database?

**Short Answer: NO.**

## Current Architecture

Your system uses a **two-tier discovery approach**:

### 1. **Monitored Entities** (Small, Curated List)
- Currently: ~9 entities (Blake Lively, Justin Baldoni, Colleen Hoover, etc.)
- Purpose: Entities you're **actively tracking** and want sentiment scores for
- Behavior: Fast catalog matching, gets entity-targeted sentiment scores

### 2. **Discovered Entities** (Auto-Discovered)
- Found by: spaCy NER + GPT `other_entities` field
- Purpose: Entities mentioned in comments but not actively tracked
- Behavior: Tracked automatically with:
  - Mention counts
  - Sample contexts
  - First/last seen dates
  - Review workflow

## Why This Works Better Than a Massive Database

### ✅ **Dynamic Discovery**
- **spaCy NER** finds entities automatically (PERSON, ORG labels)
- **GPT** discovers entities in `other_entities` field
- **Both** track to `DiscoveredEntity` table automatically

### ✅ **GPT Can Score Any Entity**
GPT's `analyze_comment()` can provide sentiment scores for entities it finds, even if they're not in your catalog:

```json
{
  "entity_scores": {
    "Blake Lively": -0.7,      // Monitored entity
    "Colleen Hoover": -0.5,    // Discovered entity (now monitored)
    "Lily Jay": 0.3            // Discovered entity (not monitored)
  },
  "other_entities": ["Ariana Grande", "Cynthia Erivo"]
}
```

### ✅ **Promotion Workflow**
When a discovered entity becomes relevant:
1. Check `discovered_entities` table (sorted by mention_count)
2. Review sample contexts
3. Add to `monitored_entities` if needed
4. Future mentions get full tracking

### ✅ **Performance**
- Small catalog = fast matching
- spaCy/GPT handle discovery (no need to pre-index thousands of names)
- Only entities you care about get full sentiment tracking

## Current Discovery Sources

### 1. spaCy NER
```python
# In EntityExtractor.extract()
for ent in doc.ents:
    if ent.label_ in ["PERSON", "ORG"]:
        # Track as discovered entity
```

### 2. GPT `other_entities`
```python
# In enrichment.py
for discovered_name in analysis.get("other_entities", []):
    self._track_discovered_entity(discovered_name, "PERSON", comment.text)
```

### 3. GPT `entity_scores`
```python
# Entities scored by GPT but not in catalog
for entity_name_raw in analysis.get("entity_scores", {}).keys():
    entity_name = entity_name_raw.split(" (")[0].strip()
    entity = self._resolve_entity_by_name(entity_name)
    if not entity:
        # Track as discovered
        self._track_discovered_entity(entity_name, "PERSON", comment.text)
```

## Query Discovered Entities

```python
from et_intel_core.analytics import AnalyticsService

service = AnalyticsService(session)
discovered = service.get_discovered_entities(
    min_mentions=10,  # Only entities mentioned 10+ times
    reviewed=False,   # Unreviewed entities
    limit=50
)

# Returns DataFrame with:
# - name
# - entity_type
# - mention_count
# - first_seen_at
# - last_seen_at
# - sample_mentions
```

## When to Add to Monitored

Add entities to `monitored_entities` when:
- ✅ They're central to your coverage area
- ✅ You want entity-targeted sentiment tracking
- ✅ They're mentioned frequently (check `mention_count`)
- ✅ They're in the news/stories you're tracking

**Example**: Colleen Hoover was discovered automatically, then promoted to monitored when she became central to the Blake/Justin story.

## What NOT to Do

❌ **Don't** maintain a massive celebrity database:
- Hard to maintain
- Slow to match against
- Most entities won't be relevant
- Duplicates discovery work that spaCy/GPT already do

❌ **Don't** add every discovered entity to monitored:
- Only track entities relevant to your coverage
- Let discovery find new mentions automatically
- Review and promote when they become relevant

## Recommended Workflow

1. **Start Small**: Monitor 5-15 core entities
2. **Discover Automatically**: Let spaCy/GPT find new entities
3. **Review Monthly**: Check `discovered_entities` sorted by `mention_count`
4. **Promote Selectively**: Add to monitored only when relevant
5. **Track Mention Growth**: Use `mention_count` to identify emerging entities

## Example: Colleen Hoover

**Before**:
- Not in `monitored_entities`
- Mentioned in comments
- GPT scored her in `entity_scores`: `"Colleen Hoover": -0.5`
- Tracked to `discovered_entities`

**After**:
- Added to `seed_entities.json`
- Now in `monitored_entities`
- Gets full entity-targeted sentiment tracking
- Included in analytics queries

## Summary

**Your current approach is optimal:**
- Small, curated monitored list (~10-20 entities)
- Automatic discovery via spaCy + GPT
- Promotion workflow for relevant entities
- No need for massive pre-indexed database

The system is designed to scale by discovering entities dynamically, not by maintaining a huge static list.

