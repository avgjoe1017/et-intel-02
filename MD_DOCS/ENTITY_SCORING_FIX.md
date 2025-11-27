# Entity Scoring Fix: Context-Based Instead of Forced

## Problem

The previous approach was forcing GPT to score entities that might not be relevant:

1. **Extract entities from comment** using catalog matching
2. **Pass as "target_entities"** to GPT
3. **Force GPT to score them** even if comment is about a different person

**Example Bug:**
- Comment: "Justin didn't attend her birthday" (on Hailey Bieber post)
- Catalog finds: "Justin" → matches "Justin Baldoni" (monitored)
- GPT forced to score: "Justin Baldoni" = -0.5 ❌
- **Reality**: Comment is about Justin Bieber, not Justin Baldoni

## Solution

**New Approach:**
1. **Pass ALL monitored entities as context** (not targets)
2. **Let GPT determine** which ones are actually mentioned
3. **Only score entities** GPT identifies as relevant
4. **Track discovered entities** from both `entity_scores` and `other_entities`

## Implementation

### Before:
```python
# Extract entities from comment
catalog_mentions = extractor.extract(comment.text)
target_entities = [entity.name for entity in catalog_mentions]

# Force GPT to score them
analysis = sentiment_provider.analyze_comment(
    target_entities=target_entities  # Forces scoring
)
```

### After:
```python
# Get ALL monitored entities as context
all_monitored = session.query(MonitoredEntity).filter_by(is_active=True).all()
monitored_list = [f"{e.name} (the director, not Justin Bieber)" for e in all_monitored]

# Let GPT determine which are relevant
analysis = sentiment_provider.analyze_comment(
    monitored_entities=monitored_list  # Context, not forced
)
```

## Prompt Changes

### Old Prompt:
```
Target entities: ["Justin Baldoni", "Blake Lively"]
Score each.
```

### New Prompt:
```
Monitored entities (for reference): [full list with disambiguation]

CRITICAL INSTRUCTIONS:
- Score ONLY entities that are ACTUALLY mentioned in this comment
- Use post caption context to disambiguate
- If a monitored entity is NOT mentioned, do NOT include it in entity_scores
- If an entity is mentioned but not in monitored list, include it in other_entities
```

## Example Behavior

### Scenario: Hailey Bieber Birthday Post

**Comment**: "It's so crazy how justin didn't even attend her birthday"

**Old Behavior:**
- Catalog finds "Justin" → matches "Justin Baldoni"
- GPT forced to score: `{"Justin Baldoni": -0.5}` ❌ (wrong person)

**New Behavior:**
- GPT sees: "Hailey Bieber birthday post" + "justin didn't attend"
- GPT determines: This is about Justin Bieber, not Justin Baldoni
- GPT returns: `{"Justin Bieber": -0.5}` in `entity_scores` or `other_entities`
- System: "Justin Bieber not monitored, track as discovered"
- System: "Justin Baldoni not mentioned, no signal created" ✅

## Benefits

1. **No more false matches**: "Justin" on Bieber post won't score Baldoni
2. **Context-aware**: GPT uses post caption to disambiguate
3. **Discover new entities**: Entities GPT finds go to `discovered_entities`
4. **Cleaner signals**: Only score entities actually discussed

## Files Changed

1. **et_intel_core/services/enrichment.py**
   - Changed from extracting entities to passing all monitored entities
   - Updated to pass `monitored_entities` instead of `target_entities`

2. **et_intel_core/nlp/sentiment.py**
   - Updated `analyze_comment()` signature: `target_entities` → `monitored_entities`
   - Updated prompt to let GPT determine relevance
   - Removed forced scoring logic

## Testing

Test with:
- Hailey Bieber post → "Justin" should NOT score "Justin Baldoni"
- Colleen Hoover post → "Justin" should score "Justin Baldoni"
- Comments mentioning unmonitored entities → should appear in `other_entities`

