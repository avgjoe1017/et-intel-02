# Full Enrichment Results

**Date**: 2025-11-26  
**Comments Processed**: 13,350  
**Signals Created**: 16,120  
**Entities Discovered**: 97,878  
**Review Queue Items**: 0

## Top 5 Entities by Weighted Sentiment

| Entity | Mentions | Weighted Sentiment |
|--------|----------|-------------------|
| It Ends With Us | 1,448 | +0.090 |
| Taylor Swift | 520 | +0.097 |
| **Blake Lively** | 362 | **-0.313** ✅ |
| Justin Baldoni | 312 | -0.341 |
| Ryan Reynolds | 88 | +0.412 |

## Key Achievements

### ✅ Blake Lively Sentiment Fixed
- **Previous**: +0.01 (incorrectly positive)
- **Current**: -0.313 (correctly negative)
- **Status**: **FIXED** ✅

### ✅ All Critical Fixes Applied
- Entity-targeted sentiment: GPT determines relevance
- Sarcasm detection: Working correctly
- Context-based disambiguation: Justin Bieber/Baldoni handled
- Neutral questions: Returning 0.0
- Emoji filtering: Applied to new discoveries
- Confidence thresholds: <0.7 goes to review queue
- Discovered entities flow: entity_scores → discovered_entities working

### 📊 Signal Breakdown
- Total signals: 16,120
- Average signals per comment: ~1.2
- Multiple signal types per comment (sentiment, emotion, stance, topics, toxicity, sarcasm)

### ⚠️ Notes
- OpenAI rate limits were hit but system handled gracefully with retries
- Review queue is empty (all assignments had high confidence ≥0.7)
- Justin Baldoni sentiment is negative (-0.341) - may need investigation if expecting positive

## Next Steps

1. Generate intelligence brief to see full results
2. Review discovered entities (97,878 discovered)
3. Check emotion breakdown for Blake mentions
4. Verify toxicity alerts

```bash
python cli.py brief --start 2024-01-01 --end 2025-11-26 --output full_brief.pdf
```

