# Entity Filtering for Discovered Entities

## Problem

The `discovered_entities` table was being polluted with:
- Emojis: 🙏 (379 mentions), 🎂 (124 mentions), 😍 (86 mentions)
- Emoji combinations: 💚🩷 (72 mentions)
- Common words: "the", "a", "an"
- Single characters: "a", "1"

## Solution

Added `_is_valid_discovered_entity()` filter in `EnrichmentService` that:

### ✅ Filters Out:
1. **Emojis and emoji-only strings**
   - All emoji Unicode ranges (U+1F300-U+1F9FF, U+2600-U+26FF, etc.)
   - Examples: 🙏, 🎂, 😍, 💚🩷 → **FILTERED**

2. **Very short names** (< 2 characters)
   - Examples: "a", "1" → **FILTERED**

3. **Numbers/punctuation only**
   - Examples: "123", "!!!" → **FILTERED**

4. **Common words**
   - Examples: "the", "a", "an", "and", "or", "but", "in", "on", etc. → **FILTERED**

### ✅ Keeps:
1. **Valid entity names**
   - Examples: "Michael B. Jordan", "Colleen Hoover", "Kate", "Colleen" → **KEPT**

2. **Ambiguous but potentially valid names**
   - Examples: "Kate", "Harry", "Robert" → **KEPT**
   - Note: These might be ambiguous, but they could be valid (e.g., "Harry" = Prince Harry)
   - `mention_count` will help surface the important ones

## Implementation

The filter is applied in `_track_discovered_entity()` before any database operations:

```python
def _track_discovered_entity(self, name: str, entity_type: str, context: str):
    # Filter out invalid entities
    if not self._is_valid_discovered_entity(name, entity_type):
        return  # Skip tracking
    
    # ... rest of tracking logic
```

## Impact

**Before filtering:**
- Top discovered entities included emojis (🙏: 379, 🎂: 124)
- Noise made it hard to find real entities

**After filtering:**
- Emojis are excluded
- Only valid entity names are tracked
- Easier to review and promote relevant entities

## Testing

Run `test_entity_filtering.py` to verify filtering logic:

```bash
python test_entity_filtering.py
```

Expected results:
- ✅ Emojis: FILTERED
- ✅ Short names: FILTERED
- ✅ Common words: FILTERED
- ✅ Valid entities: KEPT

## Future Improvements

Consider adding:
- Minimum mention threshold (e.g., only track if mentioned 3+ times)
- Context-based validation (e.g., "Kate" in "Kate Middleton" context)
- Entity type validation (e.g., ensure PERSON entities have proper name structure)

But for now, the emoji/common word filtering solves the immediate problem.

