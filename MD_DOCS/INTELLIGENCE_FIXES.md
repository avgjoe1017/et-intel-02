# Intelligence Layer Fixes

## Issues Identified

### 1. ✅ FIXED: Weighted Sentiment Calculation
**Problem**: `AVG(es.numeric_value * es.weight_score)` is incorrect - multiplies instead of proper weighted average.

**Fix**: Changed to `SUM(es.numeric_value * es.weight_score) / SUM(es.weight_score)` in `et_intel_core/analytics/service.py` line 74.

**Impact**: Blake's sentiment should now properly reflect high-like negative comments.

### 2. 🔄 IN PROGRESS: Entity Extraction Under-counting
**Problem**: Only matches full names/aliases. Missing:
- "Blake" alone (without "Lively")
- Pronouns referring to entities
- Partial matches

**Current Logic**: `if name_lower in text_lower` - too simple.

**Fix Needed**: 
- Add word boundary matching for partial names
- Use spaCy coreference resolution for pronouns
- Improve alias matching

### 3. 🔄 IN PROGRESS: LLM Narrative Hallucination
**Problem**: Narratives mention "upcoming tour" and "new music" - generic guesses not in data.

**Current**: Only passes aggregated metrics to LLM.

**Fix Needed**: Include actual comment samples in prompt to ground narratives.

### 4. 🔄 IN PROGRESS: Discovered Entities Rendering
**Problem**: Page 13 shows "■" (black squares) instead of entity names.

**Fix Needed**: Check PDF renderer encoding for discovered entities table.

### 5. ✅ VERIFIED: Like-weighting Applied
**Status**: Like-weighting IS being applied in enrichment (`weight_score = 1.0 + (likes / 100)`), but the aggregation was wrong (now fixed).

## Next Steps

1. Re-run enrichment to get corrected weighted sentiment
2. Improve entity extraction to catch partial matches
3. Update narrative generator to include comment samples
4. Fix discovered entities PDF encoding
5. Regenerate brief with fixes

