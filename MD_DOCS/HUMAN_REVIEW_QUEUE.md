# Human Review Queue for Ambiguous Entity Mentions

## Problem

When GPT encounters ambiguous entity mentions (e.g., "Justin" could be Justin Bieber or Justin Baldoni), it should not make a guess. Instead, it should queue the mention for human review.

## Solution

**Confidence Threshold: 0.7**
- If confidence >= 0.7: Create signal automatically
- If confidence < 0.7: Queue for human review

## Implementation

### 1. ReviewQueue Model

New database table `review_queue` tracks ambiguous mentions:

```python
class ReviewQueue:
    - comment_id: Which comment
    - entity_mention: The ambiguous name (e.g., "Justin")
    - context: Comment text + post caption
    - confidence: GPT's confidence (0.0-1.0)
    - possible_entities: List of possible matches
    - reason: Why it's ambiguous
    - reviewed: Has human reviewed it?
    - assigned_entity_id: Human's decision
```

### 2. GPT Response Format

GPT now returns:
```json
{
  "entity_scores": {"Blake Lively": -0.8},  // Only if confidence >= 0.7
  "entity_confidence": {"Blake Lively": 0.9},
  "ambiguous_mentions": [
    {
      "name": "Justin",
      "possible_entities": ["Justin Bieber", "Justin Baldoni"],
      "confidence": 0.5,
      "reason": "First name only, multiple Justins in monitored list"
    }
  ]
}
```

### 3. Enrichment Logic

```python
# Check confidence for each entity
for entity_name, score in entity_scores.items():
    confidence = entity_confidence.get(entity_name, 0.8)
    
    if confidence < 0.7:
        # Queue for review instead of creating signal
        _queue_for_review(comment, entity_name, confidence, possible_entities, reason)
    else:
        # High confidence - create signal
        _create_signal(...)
```

## Confidence Guidelines

- **0.9-1.0**: Full name mentioned (e.g., "Justin Baldoni") or clear context
- **0.7-0.9**: First name + strong context (e.g., "Justin" on Colleen Hoover post)
- **0.5-0.7**: First name + weak context → **Queue for review**
- **< 0.5**: Cannot determine → **Queue for review**

## Workflow

1. **Enrichment runs** → GPT identifies ambiguous mentions
2. **Low confidence mentions** → Queued to `review_queue` table
3. **Human reviews** → Assigns to correct entity (or creates new)
4. **System processes** → Creates signals based on human decisions

## Query Review Queue

```python
from et_intel_core.models import ReviewQueue

# Get unreviewed items
unreviewed = session.query(ReviewQueue).filter(
    ReviewQueue.reviewed == False
).order_by(ReviewQueue.created_at).all()

# Review an item
item.assigned_entity_id = correct_entity_id
item.reviewed = True
item.reviewed_by = "human@example.com"
item.decision = "assign"
session.commit()
```

## Benefits

1. **No false assignments**: Low confidence mentions don't pollute data
2. **Human oversight**: Ambiguous cases get human review
3. **Quality control**: Only high-confidence signals are created automatically
4. **Audit trail**: All ambiguous mentions are tracked

## Files Changed

1. **et_intel_core/models/review_queue.py** - New model
2. **et_intel_core/services/enrichment.py** - Queue logic
3. **et_intel_core/nlp/sentiment.py** - Confidence tracking
4. **et_intel_core/models/comment.py** - Relationship added
5. **et_intel_core/models/monitored_entity.py** - Relationship added

