# Cleanup Fixes Applied

## ✅ 1. Discovered Entities Filtering

**Problem**: Caption boilerplate like "Getty Images", "Swipe", "Harper", "Bazaar" appearing as discovered entities.

**Fix**: Enhanced `_is_valid_discovered_entity()` filter to exclude:
- Getty Images, swipe-related phrases
- Magazine names (Harper, Bazaar, Vogue, People, etc.)
- Instagram caption boilerplate (link in bio, see more, etc.)
- Rendering artifacts (■■ characters)

**Location**: `et_intel_core/services/enrichment.py` lines 511-570

## ✅ 2. New Negative vs Top Riser Logic

**Problem**: Justin Baldoni showing as both "New Negative" (-0.35) and "Top Riser" (+121.5%), creating confusion.

**Fix**: Updated `_get_what_changed()` to check if entity is already in risers before marking as "New Negative". If sentiment is improving (positive velocity), it shows as "Top Riser" (recovery), not "New Negative".

**Location**: `et_intel_core/reporting/brief_builder.py` lines 649-656

**Logic**: 
- Entity is negative overall BUT improving → Shows as "Top Riser" (recovery)
- Entity is negative overall AND declining → Shows as "New Negative" (worsening)

## ✅ 3. Colleen Hoover Added

**Problem**: Colleen Hoover was in `seed_entities.json` but not in database.

**Fix**: Ran `python cli.py seed-entities` to add Colleen Hoover.

**Status**: ✅ Added to database

## ⚠️ 4. Date Range

**Problem**: Brief showing "January 01, 2024 to November 26, 2025" (almost 2 years) instead of recent week.

**Note**: The `brief` command requires explicit `--start` and `--end` dates. Use:

```bash
# Recent week (Nov 20-26, 2025)
python cli.py brief --start 2025-11-20 --end 2025-11-26 --output recent_brief.pdf

# Or use --days flag in other commands (brief doesn't have --days)
```

**Recommendation**: Could add `--days` flag to brief command for convenience.

---

## Next Steps

1. **Re-run enrichment** to capture Colleen Hoover mentions:
   ```bash
   python cli.py enrich
   ```

2. **Generate new brief** with correct date range:
   ```bash
   python cli.py brief --start 2025-11-20 --end 2025-11-26 --output recent_brief.pdf
   ```

3. **Verify fixes**:
   - Discovered entities should exclude caption boilerplate
   - Justin Baldoni should show as "Top Riser" only (if improving)
   - Colleen Hoover should appear in entity list

---

*All fixes applied and ready to test!*

