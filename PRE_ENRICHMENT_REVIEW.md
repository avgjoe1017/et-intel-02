# Pre-Enrichment Review - Critical Files

**Purpose:** Review these 10 files before running full enrichment to ensure all fixes are correct.

---

## 1. `et_intel_core/services/enrichment.py` ⭐⭐⭐
**Why:** Core enrichment logic with 6 major fixes applied
**What to check:**
- Lines 144-162: Entity name validation (`_is_valid_entity_name()`)
- Lines 204-230: Emotion signals now linked to entities (Fix 6)
- Lines 232-250: Stance signals disabled (Fix 7)
- Lines 295-325: Double-counting prevention (Fix 8)
- Lines 423-448: Alias resolution with cache (Fix 9)
- Lines 475-555: `_is_valid_entity_name()` and `_is_valid_discovered_entity()` filters

**Key question:** Does the enrichment flow correctly validate, link, and track entities?

---

## 2. `et_intel_core/nlp/sentiment.py` ⭐⭐⭐
**Why:** GPT prompt controls what entities get scored
**What to check:**
- Lines 129-169: System prompt with sarcasm rules
- Lines 257-285: User prompt with entity scoring rules (Fix 5)
- Line 265: "Score ONLY entities that are ACTUALLY MENTIONED"
- Line 268: "If a monitored entity is NOT mentioned, do NOT include it"

**Key question:** Will GPT stop hallucinating entity mentions?

---

## 3. `et_intel_core/analytics/service.py` ⭐⭐⭐
**Why:** Report data comes from here
**What to check:**
- Lines 907-956: `get_top_posts()` with caption-first entity detection (Fix 1)
- Lines 1099-1134: `get_dynamic_entities()` with garbage filtering (Fix 3B)
- Lines 1115-1124: Blocklist for discovered entities

**Key question:** Will reports show correct top entity per post and filter garbage?

---

## 4. `et_intel_core/models/extracted_signal.py` ⭐⭐
**Why:** Database schema with new indexes
**What to check:**
- Lines 75-92: 4 new performance indexes (Fix 10)
- Indexes: `ix_signals_type`, `ix_signals_entity_type`, `ix_signals_comment`, `ix_signals_numeric`

**Key question:** Are indexes properly defined for migration?

---

## 5. `et_intel_core/reporting/pdf_renderer.py` ⭐⭐
**Why:** Sentiment labels displayed in brief
**What to check:**
- Lines 752-763: `_get_sentiment_label()` with corrected logic (Fix 4)
- Line 758: `elif sentiment > -0.3:` (ensures -0.44 = "Negative")

**Key question:** Will sentiment labels be correct in the PDF?

---

## 6. `data/seed_entities.json` ⭐⭐
**Why:** Defines monitored entities and their aliases
**What to check:**
- All entities have proper aliases (e.g., "JLo" for Jennifer Lopez)
- Colleen Hoover is present
- Harry and Meghan are present (added per user feedback)

**Key question:** Are all important entities and aliases defined?

---

## 7. `et_intel_core/reporting/brief_builder.py` ⭐
**Why:** Assembles brief sections and calls analytics
**What to check:**
- Lines 200-250: `_get_emotion_analysis()` - will it work with entity-linked emotions?
- Lines 907-956: `get_top_posts()` integration
- Lines 1055-1210: `get_dynamic_entities()` integration

**Key question:** Will brief builder correctly use new entity-linked emotion signals?

---

## 8. `alembic/versions/b3d3384be058_add_signal_indexes_for_performance.py` ⭐
**Why:** Database migration for indexes
**What to check:**
- Migration creates 4 indexes correctly
- No errors in migration logic

**Key question:** Did the migration apply successfully?

---

## 9. `et_intel_core/models/enums.py` ⭐
**Why:** Defines SignalType enum
**What to check:**
- All signal types defined: SENTIMENT, EMOTION, STANCE, TOPIC, TOXICITY, SARCASM
- STANCE still defined (even though disabled in enrichment)

**Key question:** Are all signal types available for future use?

---

## 10. `.env` ⭐
**Why:** Contains API keys and configuration
**What to check:**
- `OPENAI_API_KEY` is set
- `DATABASE_URL` is correct
- `APIFY_TOKEN` is set (if using Apify sources)

**Key question:** Are all credentials configured?

---

## Quick Verification Commands

Before enrichment, run these to verify state:

```bash
# 1. Check database is ready
python -c "from et_intel_core.db import get_session; from et_intel_core.models import ExtractedSignal; s = get_session(); print(f'Signals in DB: {s.query(ExtractedSignal).count()}')"

# 2. Check discovered entities are clean
python -c "from et_intel_core.db import get_session; from et_intel_core.models import DiscoveredEntity; s = get_session(); print(f'Discovered entities: {s.query(DiscoveredEntity).count()}'); garbage = [e.name for e in s.query(DiscoveredEntity).all() if '■' in e.name or e.name.lower() in ['getty', 'swipe', 'getty images']]; print(f'Garbage found: {len(garbage)}')"

# 3. Check monitored entities loaded
python -c "from et_intel_core.db import get_session; from et_intel_core.models import MonitoredEntity; s = get_session(); entities = s.query(MonitoredEntity).filter_by(is_active=True).all(); print(f'Monitored entities: {len(entities)}'); print('Names:', [e.name for e in entities])"

# 4. Check indexes exist
python -c "from et_intel_core.db import get_session; from sqlalchemy import inspect; s = get_session(); inspector = inspect(s.bind); indexes = inspector.get_indexes('extracted_signals'); print(f'Indexes on extracted_signals: {len(indexes)}'); print('Index names:', [i['name'] for i in indexes])"

# 5. Test alias resolution
python -c "from et_intel_core.services.enrichment import EnrichmentService; from et_intel_core.db import get_session; from et_intel_core.nlp import get_sentiment_provider; s = get_session(); provider = get_sentiment_provider('openai'); enricher = EnrichmentService(s, None, provider); enricher._build_alias_cache(); print('Alias cache size:', len(enricher._alias_cache)); print('Sample aliases:', list(enricher._alias_cache.keys())[:10])"
```

---

## Expected Outcomes After Enrichment

1. **No garbage entities** in signals (no "■", "OMG", "Getty Images")
2. **Correct top entity** per post (Meghan post shows Meghan, not "It Ends With Us")
3. **Emotion signals linked** to entities (can query "emotions about Blake")
4. **Alias resolution works** ("JLo" matches "Jennifer Lopez")
5. **Sentiment labels correct** (-0.44 shows "Negative")
6. **No double-counting** (accurate mention counts)
7. **No stance signals** (disabled until proper implementation)
8. **Fast queries** (indexes in use)

---

## Red Flags to Watch For

- ❌ Enrichment creates signals for entities like "■■■" or "OMG"
- ❌ Post about Meghan shows "It Ends With Us" as top entity
- ❌ Emotion signals have `entity_id=None` for all comments
- ❌ GPT returns "JLo" but no signal created (alias not resolved)
- ❌ Brief shows "Neutral sentiment (-0.44)"
- ❌ Same entity counted twice in discovered entities
- ❌ Stance signals being created (should be disabled)
- ❌ Queries taking >5 seconds (indexes not working)

If any red flags appear, STOP enrichment and investigate.

