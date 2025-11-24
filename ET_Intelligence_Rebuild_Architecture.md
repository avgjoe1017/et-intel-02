# ET Social Intelligence System - V2 Rebuild Architecture

## Executive Summary

After analyzing the V1 codebase and incorporating architectural feedback, this document presents a **pragmatic rebuild** that maintains the system's intelligence while fixing its structural limitations. The core insight: **Intelligence is derived, not stored. Comments are atoms. Everything else is a view.**

---

## V1 Analysis: What Works, What Doesn't

### What V1 Got Right ✅

1. **Clear Business Value**
   - Converts ET's comment section into strategic intelligence
   - Velocity alerts (30% sentiment change in 72hrs = red flag)
   - Entity-level risk assessment for talent/IP
   - $100/mo vs. $50K+ traditional research

2. **Solid Intelligence Features**
   - Multi-source sentiment (OpenAI, Hugging Face, TextBlob, rule-based)
   - Entity extraction with spaCy
   - Like-weighted sentiment (high-engagement comments matter more)
   - Relationship graphs (couples, storylines)
   - Professional PDF reports + Streamlit dashboard

3. **Entertainment-Specific Tuning**
   - Understands stan culture ("she ate" = positive)
   - Tracks storyline fatigue
   - Handles sarcasm and entertainment language

### Where V1 Fights You at Scale 🔧

1. **Monolithic Pipeline**
   - `ETIntelligencePipeline` does: ingestion + entities + sentiment + velocity + brief prep
   - Hard to test components in isolation
   - Can't reuse parts for other workflows (like live alerting)

2. **Schema Designed Reactively**
   - Started with `comments`, added `sentiment`, then `weighted_sentiment`
   - Entities live partly in DB, partly in JSON files
   - No clear "dimension tables" for BI tools to query

3. **Coupling of Compute and Presentation**
   - Same code that calculates metrics also prepares PDF data
   - Can't easily add new output formats (Slack, email) without touching core logic

4. **CSV-Centric Ingestion**
   - Preprocessing scripts tied to specific vendor formats (ESUIT, Apify)
   - No abstraction for future API integrations

5. **LLM as a Feature Flag**
   - `USE_LLM_ENHANCEMENT` scattered through code
   - Should be: sentiment provider = swappable interface

**Bottom Line:** V1 proves the concept. V2 makes it production-ready.

---

## V2 Architecture: Pragmatic Intelligence Library

### Core Philosophy

> **Intelligence is derived, not stored. The comment is the atom. Everything else is a perspective.**

Instead of storing sentiment *in* comments, we store **signals** *about* comments. This allows:
- Multiple models to score the same comment (TextBlob + GPT both valid)
- Entity-targeted sentiment ("I love Ryan but hate Blake" = 2 signals)
- Extensibility without schema migrations (add emotion/toxicity/risk scores later)

### Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                   Core Library (Python)                     │
│                  et_intel_core package                      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │  Ingestion   │  │  Enrichment  │  │   Analytics     │ │
│  │  Service     │  │  Service     │  │   Service       │ │
│  └──────────────┘  └──────────────┘  └─────────────────┘ │
│                                                             │
│  • Source-agnostic ingestion (ESUIT, Apify, CSV)          │
│  • Entity extraction + sentiment scoring                    │
│  • Metric computation (velocity, fatigue, trends)          │
│  • Brief building + PDF rendering                          │
└────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────┐
│              Data Layer (PostgreSQL)                        │
│                                                             │
│  [Posts] ──→ [Comments] ──→ [ExtractedSignals]            │
│     ↓                             ↑                        │
│  [raw_data]              [MonitoredEntities]               │
│   JSONB                                                     │
│                                                             │
│  • Posts & Comments: Source of truth                       │
│  • ExtractedSignals: Intelligence layer (multi-perspective)│
│  • MonitoredEntities: Dynamic configuration                │
│  • DiscoveredEntities: Tracking unmapped entities          │
└────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────┐
│              Interfaces (Import Library Directly)           │
│                                                             │
│  ┌───────────────────┐  ┌───────────────────────────────┐ │
│  │       CLI         │  │   Streamlit Dashboard         │ │
│  │                   │  │                               │ │
│  │ from et_intel     │  │ from et_intel.analytics       │ │
│  │   import ingest   │  │   import AnalyticsService     │ │
│  └───────────────────┘  └───────────────────────────────┘ │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐│
│  │              PDF Reports (ReportLab)                   ││
│  │   BriefBuilder → BriefData → PDFRenderer              ││
│  └────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────┘
                              
                         (Future: Phase 2)
┌────────────────────────────────────────────────────────────┐
│              Optional API Layer (FastAPI)                   │
│  Add when you need: Slack bots, webhooks, external access  │
│  Thin wrapper around existing services                     │
└────────────────────────────────────────────────────────────┘
```

**Key Design Decisions:**
- **Library-first**: CLI and Streamlit import services directly (no HTTP overhead)
- **Synchronous by default**: CSV ingestion doesn't need async complexity
- **FastAPI is Phase 2**: Add only when external integrations are needed
- **PostgreSQL only**: Native partitioning sufficient, no TimescaleDB needed
- **Signals table**: The killer feature (extensibility without migrations)

---

## The Data Model (Heart of V2)

### Schema Design: Intelligence as Signals

```python
# models.py - SQLAlchemy 2.0
import uuid
from datetime import datetime
from typing import List, Optional
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, Float, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

# --- Enums ---
class PlatformType(str, PyEnum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"

class SignalType(str, PyEnum):
    SENTIMENT = "sentiment"       # -1.0 to 1.0
    EMOTION = "emotion"           # "anger", "joy", "excitement"
    STORYLINE = "storyline"       # "lawsuit", "divorce", "comeback"
    RISK_FLAG = "risk_flag"       # "threat", "doxxing", "harassment"

class ContextType(str, PyEnum):
    DIRECT = "direct"             # Top-level comment
    REPLY = "reply"               # Direct reply
    THREAD = "thread"             # Deep nested (context drift risk)

class EntityType(str, PyEnum):
    PERSON = "person"
    SHOW = "show"
    COUPLE = "couple"
    BRAND = "brand"

class Base(DeclarativeBase):
    pass

# --- 1. Posts: The Container ---
class Post(Base):
    """
    Parent container for comments.
    Key innovation: raw_data JSONB stores the entire API response.
    If Instagram adds a field next week, we can re-process without re-scraping.
    """
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    platform: Mapped[PlatformType] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(String)
    
    # Editorial context (what is this post about?)
    subject_line: Mapped[Optional[str]] = mapped_column(String) 
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    
    # The safety net: dump full JSON payload here
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    comments: Mapped[List["Comment"]] = relationship(
        back_populates="post", 
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        UniqueConstraint('platform', 'external_id', name='uq_platform_post'),
    )


# --- 2. Comments: The Atomic Unit ---
class Comment(Base):
    """
    The atomic unit of data.
    Notice: NO sentiment columns here. Just "what was said."
    Intelligence lives in ExtractedSignals.
    """
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id"))
    
    # Content
    author_name: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True  # For time-based queries
    )
    
    # Metrics (can be updated on re-ingest)
    likes: Mapped[int] = mapped_column(default=0)
    reply_count: Mapped[int] = mapped_column(default=0)
    
    # Threading
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("comments.id"), 
        nullable=True
    )
    context_type: Mapped[ContextType] = mapped_column(default=ContextType.DIRECT)

    # For future extensions (language, toxicity, etc.)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    post: Mapped["Post"] = relationship(back_populates="comments")
    replies: Mapped[List["Comment"]] = relationship(
        back_populates="parent",
        remote_side=[id]
    )
    parent: Mapped[Optional["Comment"]] = relationship(back_populates="replies")
    signals: Mapped[List["ExtractedSignal"]] = relationship(
        back_populates="comment",
        cascade="all, delete-orphan"
    )


# --- 3. Monitored Entities: Dynamic Configuration ---
class MonitoredEntity(Base):
    """
    Replaces hardcoded config.SEED_RELATIONSHIPS.
    Add 'Ryan Reynolds' via UI without deploying code.
    """
    __tablename__ = "monitored_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, unique=True)
    canonical_name: Mapped[str] = mapped_column(String)  # "JLO" -> "Jennifer Lopez"
    entity_type: Mapped[EntityType] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Keywords for matching (stored as JSON array)
    aliases: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Relationships
    signals: Mapped[List["ExtractedSignal"]] = relationship(back_populates="entity")


# --- 4. Extracted Signals: The Intelligence Layer ---
class ExtractedSignal(Base):
    """
    THE KILLER TABLE.
    
    Instead of comment.sentiment, we have rows here.
    Allows:
    - Multiple models to score same comment (TextBlob + GPT)
    - Entity-targeted sentiment ("I love Ryan but hate Blake" = 2 signals)
    - Extensibility without migrations (add emotion/toxicity later)
    
    Example rows:
    - Comment A -> SignalType.SENTIMENT -> value="-0.9" -> numeric_value=-0.9 -> entity="Blake Lively"
    - Comment A -> SignalType.EMOTION -> value="anger" -> numeric_value=None -> entity="Blake Lively"
    - Comment A -> SignalType.SENTIMENT -> value="+0.8" -> numeric_value=0.8 -> entity="Ryan Reynolds"
    """
    __tablename__ = "extracted_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    comment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comments.id"))
    
    # If signal is about a specific entity, link it
    # If it's general comment sentiment, this is NULL
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("monitored_entities.id"), 
        nullable=True
    )

    # What did we find?
    signal_type: Mapped[SignalType] = mapped_column(String(50)) 
    value: Mapped[str] = mapped_column(String)  # "negative", "anger", "divorce rumor"
    
    # CRITICAL: Dedicated numeric column for scores
    # Sentiment/toxicity/confidence go here for efficient querying
    # Emotion labels/storylines leave this NULL
    numeric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # V1's "like-weighted" logic lives here
    weight_score: Mapped[float] = mapped_column(Float, default=1.0) 
    
    # Algorithm metadata
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source_model: Mapped[str] = mapped_column(String)  # "textblob", "gpt-4o-mini"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )

    # Relationships
    comment: Mapped["Comment"] = relationship(back_populates="signals")
    entity: Mapped[Optional["MonitoredEntity"]] = relationship(back_populates="signals")
    
    # Indexes for fast querying
    __table_args__ = (
        # Prevent duplicate signals (same comment + entity + type + model)
        UniqueConstraint(
            'comment_id', 
            'entity_id', 
            'signal_type', 
            'source_model',
            name='uq_signal_identity'
        ),
        # Composite index for "Blake Lively negative signals last week"
        # Index('idx_entity_signal_time', 'entity_id', 'signal_type', 'created_at'),
    )


# --- 5. Discovered Entities: Tracking Unknowns ---
class DiscoveredEntity(Base):
    """
    Lightweight tracking for entities spaCy finds that aren't in MonitoredEntity.
    Helps answer: "Who are we missing?"
    
    Workflow:
    1. spaCy finds "Kelsea Ballerini" in comments
    2. Not in MonitoredEntity catalog
    3. Log to DiscoveredEntity
    4. Review monthly: "Should we add these to monitored list?"
    """
    __tablename__ = "discovered_entities"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, unique=True)
    entity_type: Mapped[str] = mapped_column(String)  # From spaCy: PERSON, ORG
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mention_count: Mapped[int] = mapped_column(default=0)
    # Sample contexts where this entity appeared
    sample_mentions: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Reviewed by human?
    reviewed: Mapped[bool] = mapped_column(default=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    # If reviewed, did we add to MonitoredEntity or ignore?
    action_taken: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    __table_args__ = (
        # Index for "show me top unreviewed entities"
        # Index('idx_discovered_unreviewed', 'reviewed', 'mention_count'),
    )
```

**Why numeric_value Matters:**

```sql
-- Clean queries (with numeric_value):
SELECT entity_id, AVG(numeric_value) as avg_sentiment
FROM extracted_signals
WHERE signal_type = 'sentiment'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY entity_id
ORDER BY avg_sentiment DESC;

-- Messy queries (without numeric_value):
SELECT entity_id, AVG(CAST(value AS FLOAT)) as avg_sentiment  -- Constant casting
FROM extracted_signals
WHERE signal_type = 'sentiment'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY entity_id
ORDER BY avg_sentiment DESC;
```

**Usage Pattern:**

```python
# When creating sentiment signal:
signal = ExtractedSignal(
    comment_id=comment_id,
    entity_id=entity_id,
    signal_type=SignalType.SENTIMENT,
    value="negative",          # Human-readable
    numeric_value=-0.7,        # For analytics/BI
    source_model="gpt-4o-mini",
    confidence=0.9
)

# When creating emotion signal:
signal = ExtractedSignal(
    comment_id=comment_id,
    entity_id=entity_id,
    signal_type=SignalType.EMOTION,
    value="anger",             # Human-readable
    numeric_value=None,        # Not applicable
    source_model="textblob",
    confidence=0.6
)
```
```

**Why This Schema Is Better:**

1. **`raw_data` JSONB in Posts**
   - Problem: APIs change. Instagram might add `is_verified` tomorrow.
   - Solution: Dump entire API response. Re-process later without re-scraping.

2. **Signals Instead of Columns**
   - V1 Problem: `sentiment`, `weighted_sentiment`, `emotion` = new columns
   - V2 Solution: Narrow table. Endless extensibility.
   ```
   Row 1: Comment A -> Sentiment -> -0.9
   Row 2: Comment A -> Emotion -> Anger  
   Row 3: Comment A -> Storyline -> "Casting Controversy"
   ```

3. **Entity-Targeted Sentiment**
   - V1 Problem: "Who is this negative about?"
   - V2 Solution: `entity_id` in signals
   ```
   "I love Ryan but hate Blake"
   -> Signal 1: entity=Ryan, sentiment=+0.8
   -> Signal 2: entity=Blake, sentiment=-0.9
   ```

4. **Context Type for Threading**
   - Problem: Deep thread comments refer to parent, not post subject
   - Solution: `context_type=THREAD` -> decrease attribution confidence

---

## Component Design

### 1. Ingestion Layer



**Source-Agnostic, Synchronous Ingestion**

```python
from typing import Protocol, Iterator  # Not AsyncIterator
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import pandas as pd

# --- Pydantic Models for Validation ---
class RawComment(BaseModel):
    """Normalized comment from any source"""
    platform: str
    external_post_id: str
    post_url: str
    post_caption: Optional[str] = None
    post_subject: Optional[str] = None  # Editorial: "Taylor Swift at Chiefs Game"
    comment_author: str
    comment_text: str
    comment_timestamp: datetime
    like_count: int = 0
    raw: dict  # Original row for debugging

# --- Source Adapter Interface ---
class IngestionSource(Protocol):
    """Every CSV/API adapter implements this"""
    
    def iter_records(self) -> Iterator[RawComment]:  # Synchronous!
        """Yield normalized comments"""
        ...

# --- Concrete Implementations ---
class ESUITSource(IngestionSource):
    """Adapter for ESUIT CSV exports"""
    
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
    
    def iter_records(self) -> Iterator[RawComment]:
        """Simple, synchronous CSV reading"""
        df = pd.read_csv(self.csv_path)
        
        for _, row in df.iterrows():
            yield RawComment(
                platform="instagram",
                external_post_id=row['Post URL'].split('/')[-2],
                post_url=row['Post URL'],
                post_caption=row.get('Caption', ''),
                post_subject=row.get('Subject', ''),
                comment_author=row['Username'],
                comment_text=row['Comment'],
                comment_timestamp=pd.to_datetime(row['Timestamp']),
                like_count=int(row.get('Likes', 0)),
                raw=row.to_dict()
            )

class ApifySource(IngestionSource):
    """Adapter for Apify CSV exports"""
    
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
    
    def iter_records(self) -> Iterator[RawComment]:
        """Similar synchronous implementation for Apify format"""
        df = pd.read_csv(self.csv_path)
        
        for _, row in df.iterrows():
            # Apify has different column names
            yield RawComment(
                platform="instagram",
                external_post_id=row['shortCode'],
                post_url=row['url'],
                post_caption=row.get('caption', ''),
                post_subject=None,  # Apify doesn't track this
                comment_author=row['ownerUsername'],
                comment_text=row['text'],
                comment_timestamp=pd.to_datetime(row['timestamp']),
                like_count=int(row.get('likesCount', 0)),
                raw=row.to_dict()
            )

# Future: Add async version only when needed for API calls
class InstagramAPISource(IngestionSource):
    """
    Future implementation for direct Instagram Graph API.
    This one WOULD be async, but we'd keep both interfaces:
    
    def iter_records(self) -> Iterator[RawComment]:
        # Synchronous wrapper that blocks on async calls
        ...
    
    async def aiter_records(self) -> AsyncIterator[RawComment]:
        # Async native version for API fetching
        ...
    """
    pass

# --- Ingestion Service ---
class IngestionService:
    """Orchestrates ingestion into database"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def ingest(self, source: IngestionSource) -> dict:
        """
        Ingest comments from any source.
        Idempotent: won't duplicate existing comments.
        Synchronous: simple, debuggable, sufficient for CSV volumes.
        """
        stats = {
            "posts_created": 0,
            "posts_updated": 0,
            "comments_created": 0,
            "comments_updated": 0
        }
        
        for record in source.iter_records():
            # Upsert post
            post, created = self._get_or_create_post(record)
            if created:
                stats["posts_created"] += 1
            else:
                stats["posts_updated"] += 1
            
            # Upsert comment
            existing = self.session.query(Comment).filter(
                Comment.post_id == post.id,
                Comment.author_name == record.comment_author,
                Comment.text == record.comment_text,
                Comment.created_at == record.comment_timestamp
            ).first()
            
            if existing:
                # Update metrics (likes might have changed)
                existing.likes = record.like_count
                stats["comments_updated"] += 1
            else:
                comment = Comment(
                    post_id=post.id,
                    author_name=record.comment_author,
                    text=record.comment_text,
                    created_at=record.comment_timestamp,
                    likes=record.like_count,
                    context_type=ContextType.DIRECT  # Top-level by default
                )
                self.session.add(comment)
                stats["comments_created"] += 1
            
            # Commit in batches for efficiency
            if (stats["comments_created"] + stats["comments_updated"]) % 100 == 0:
                self.session.commit()
        
        self.session.commit()
        return stats
    
    def _get_or_create_post(self, record: RawComment) -> tuple[Post, bool]:
        """
        Get existing post or create new one.
        Returns: (post, created_flag)
        """
        post = self.session.query(Post).filter(
            Post.platform == record.platform,
            Post.external_id == record.external_post_id
        ).first()
        
        if post:
            # Update raw_data in case API added new fields
            post.raw_data = record.raw
            return (post, False)
        
        post = Post(
            platform=record.platform,
            external_id=record.external_post_id,
            url=record.post_url,
            subject_line=record.post_subject,
            posted_at=record.comment_timestamp,  # Approximate from first comment
            raw_data=record.raw
        )
        self.session.add(post)
        self.session.flush()  # Get ID without committing
        return (post, True)
```

**Why Synchronous?**

1. **CSV files are local** - no network latency to hide
2. **Volumes are modest** - ESUIT exports are typically <10K comments
3. **Downstream enrichment is the bottleneck** - not ingestion
4. **Simpler debugging** - no async/await ceremony
5. **SQLAlchemy Session plays nicer** - no async session complexity

**When to add async**: When you're fetching from APIs with rate limits where concurrent requests help (Instagram Graph API, YouTube API).

### 2. NLP/Enrichment Layer

**Entity Extraction + Sentiment Scoring as Separate, Swappable Components**

```python
from typing import List
from dataclasses import dataclass

# --- Entity Extraction ---
@dataclass
class EntityMention:
    """Extracted entity mention"""
    entity_id: uuid.UUID
    mention_text: str
    confidence: float

class EntityExtractor:
    """
    Pure function: takes text, returns entities.
    No database coupling, easily testable.
    """
    
    def __init__(self, entity_catalog: List[MonitoredEntity]):
        self.catalog = entity_catalog
        # Load spaCy, build regex patterns, etc.
        self.nlp = spacy.load("en_core_web_sm")
    
    def extract(self, text: str, post_caption: Optional[str] = None) -> List[EntityMention]:
        """
        Extract entities from comment text.
        Optionally use post caption for context.
        """
        mentions = []
        
        # 1. Check catalog (fast exact/alias matching)
        for entity in self.catalog:
            if entity.name.lower() in text.lower():
                mentions.append(EntityMention(
                    entity_id=entity.id,
                    mention_text=entity.name,
                    confidence=1.0
                ))
                continue
            
            # Check aliases
            for alias in entity.aliases:
                if alias.lower() in text.lower():
                    mentions.append(EntityMention(
                        entity_id=entity.id,
                        mention_text=alias,
                        confidence=0.9
                    ))
                    break
        
        # 2. spaCy NER for discovery (people/orgs not in catalog)
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG"]:
                # Check if already found via catalog
                if not any(m.mention_text.lower() == ent.text.lower() for m in mentions):
                    # New entity discovered - would create later or flag for review
                    pass
        
        return mentions

# --- Sentiment Provider Interface ---
@dataclass
class SentimentResult:
    """Result from any sentiment model"""
    score: float  # -1.0 to 1.0
    confidence: float
    source_model: str

class SentimentProvider(Protocol):
    """Interface for all sentiment models"""
    
    def score(self, text: str) -> SentimentResult:
        ...

# --- Implementations ---
class RuleBasedSentimentProvider(SentimentProvider):
    """Fast, free, decent for obvious cases"""
    
    def score(self, text: str) -> SentimentResult:
        # Use lexicon + emoji analysis
        positive_words = ["love", "amazing", "great", "best"]
        negative_words = ["hate", "terrible", "worst", "awful"]
        
        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        if pos_count + neg_count == 0:
            return SentimentResult(score=0.0, confidence=0.3, source_model="rule_based")
        
        score = (pos_count - neg_count) / (pos_count + neg_count)
        return SentimentResult(score=score, confidence=0.6, source_model="rule_based")

class OpenAISentimentProvider(SentimentProvider):
    """High accuracy, costs money"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def score(self, text: str) -> SentimentResult:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Score sentiment of: {text}\nReturn only a number from -1.0 to 1.0"
            }],
            max_tokens=10
        )
        
        score = float(response.choices[0].message.content.strip())
        return SentimentResult(score=score, confidence=0.9, source_model="gpt-4o-mini")

class HybridSentimentProvider(SentimentProvider):
    """
    Cost optimization: use cheap model first, escalate if uncertain.
    """
    
    def __init__(self, cheap: SentimentProvider, expensive: SentimentProvider):
        self.cheap = cheap
        self.expensive = expensive
    
    def score(self, text: str) -> SentimentResult:
        # Try cheap first
        result = self.cheap.score(text)
        
        # Escalate if uncertain
        if result.confidence < 0.7 or abs(result.score) < 0.2:
            return self.expensive.score(text)
        
        return result

# --- Factory ---
def get_sentiment_provider(config: Settings) -> SentimentProvider:
    """Get sentiment provider based on config"""
    if config.sentiment_backend == "openai":
        return OpenAISentimentProvider(config.openai_api_key)
    elif config.sentiment_backend == "hybrid":
        cheap = RuleBasedSentimentProvider()
        expensive = OpenAISentimentProvider(config.openai_api_key)
        return HybridSentimentProvider(cheap, expensive)
    else:
        return RuleBasedSentimentProvider()

# --- Enrichment Service ---
class EnrichmentService:
    """
    Takes raw comments, produces signals.
    Separate from ingestion - can be run as batch job.
    """
    
    def __init__(
        self,
        session: Session,
        extractor: EntityExtractor,
        sentiment_provider: SentimentProvider
    ):
        self.session = session
        self.extractor = extractor
        self.sentiment_provider = sentiment_provider
    
    def enrich_comments(
        self,
        comment_ids: Optional[List[uuid.UUID]] = None,
        since: Optional[datetime] = None
    ) -> dict:
        """
        Enrich comments with entities + sentiment.
        Idempotent: can be re-run to update signals.
        
        Args:
            comment_ids: Specific comments to enrich (or None for all unprocessed)
            since: Only enrich comments created after this date
        """
        stats = {
            "comments_processed": 0,
            "signals_created": 0,
            "entities_discovered": 0
        }
        
        # Query comments to process
        query = self.session.query(Comment)
        
        if comment_ids:
            query = query.filter(Comment.id.in_(comment_ids))
        elif since:
            query = query.filter(Comment.created_at >= since)
        else:
            # Default: only unprocessed comments
            query = query.filter(
                ~exists().where(
                    ExtractedSignal.comment_id == Comment.id
                )
            )
        
        comments = query.all()
        
        for comment in comments:
            # Extract entities
            entity_mentions, discovered = self.extractor.extract(
                comment.text,
                post_caption=comment.post.subject_line
            )
            
            # Track discovered entities
            for disc in discovered:
                self._track_discovered_entity(disc, comment.text)
                stats["entities_discovered"] += 1
            
            # Score sentiment
            sentiment_result = self.sentiment_provider.score(comment.text)
            
            # Create general comment sentiment signal
            self._create_signal(
                comment_id=comment.id,
                entity_id=None,
                signal_type=SignalType.SENTIMENT,
                value=self._sentiment_label(sentiment_result.score),
                numeric_value=sentiment_result.score,  # For analytics
                source_model=sentiment_result.source_model,
                confidence=sentiment_result.confidence,
                weight_score=1.0 + (comment.likes / 100)  # Like-weighted
            )
            stats["signals_created"] += 1
            
            # Create entity-specific signals
            for entity_mention in entity_mentions:
                # In a perfect world, you'd do entity-targeted sentiment here
                # For MVP, use the general sentiment with entity association
                self._create_signal(
                    comment_id=comment.id,
                    entity_id=entity_mention.entity_id,
                    signal_type=SignalType.SENTIMENT,
                    value=self._sentiment_label(sentiment_result.score),
                    numeric_value=sentiment_result.score,
                    source_model=sentiment_result.source_model,
                    confidence=entity_mention.confidence * sentiment_result.confidence,
                    weight_score=1.0 + (comment.likes / 100)
                )
                stats["signals_created"] += 1
            
            stats["comments_processed"] += 1
            
            # Commit in batches
            if stats["comments_processed"] % 50 == 0:
                self.session.commit()
        
        self.session.commit()
        return stats
    
    def _create_signal(self, **kwargs):
        """Create or update signal (idempotent)"""
        # Check for existing signal
        existing = self.session.query(ExtractedSignal).filter(
            ExtractedSignal.comment_id == kwargs['comment_id'],
            ExtractedSignal.entity_id == kwargs.get('entity_id'),
            ExtractedSignal.signal_type == kwargs['signal_type'],
            ExtractedSignal.source_model == kwargs['source_model']
        ).first()
        
        if existing:
            # Update existing
            existing.value = kwargs['value']
            existing.numeric_value = kwargs.get('numeric_value')
            existing.confidence = kwargs['confidence']
            existing.weight_score = kwargs['weight_score']
        else:
            # Create new
            signal = ExtractedSignal(**kwargs, created_at=datetime.utcnow())
            self.session.add(signal)
    
    def _sentiment_label(self, score: float) -> str:
        """Convert numeric sentiment to label"""
        if score > 0.3:
            return "positive"
        elif score < -0.3:
            return "negative"
        else:
            return "neutral"
    
    def _track_discovered_entity(self, name: str, context: str):
        """Track an entity that spaCy found but isn't in MonitoredEntity"""
        discovered = self.session.query(DiscoveredEntity).filter(
            DiscoveredEntity.name == name
        ).first()
        
        if discovered:
            # Update existing
            discovered.last_seen_at = datetime.utcnow()
            discovered.mention_count += 1
            # Keep up to 10 sample mentions
            if len(discovered.sample_mentions) < 10:
                discovered.sample_mentions.append(context[:200])
        else:
            # Create new
            discovered = DiscoveredEntity(
                name=name,
                entity_type="PERSON",  # From spaCy
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                mention_count=1,
                sample_mentions=[context[:200]]
            )
            self.session.add(discovered)
```

**Key Improvements:**

1. **Batch Processing**: Commits every 50 comments instead of per-comment
2. **Discovered Entity Tracking**: Automatically logs unknown entities for review
3. **numeric_value Population**: Sentiment scores go in dedicated column
4. **Idempotent**: Can re-run on same comments (updates existing signals)
5. **Query Flexibility**: Can target specific comments, date ranges, or unprocessed only

### 3. Analytics Service

**Pure Query Functions That Return Data, Not Visualizations**

```python
from typing import Tuple
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import text

class AnalyticsService:
    """
    Analytics layer: queries database, computes metrics.
    No presentation logic (that's for report generator).
    All queries are timezone-aware (UTC).
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_top_entities(
        self,
        time_window: Tuple[datetime, datetime],
        platforms: Optional[List[str]] = None,
        limit: int = 20
    ) -> pd.DataFrame:
        """
        Get top entities by mention count + average sentiment.
        Uses numeric_value column for clean aggregation.
        """
        query = text("""
        SELECT 
            me.name as entity_name,
            me.entity_type,
            COUNT(DISTINCT es.comment_id) as mention_count,
            AVG(es.numeric_value) as avg_sentiment,
            SUM(c.likes) as total_likes,
            AVG(es.numeric_value * es.weight_score) as weighted_sentiment
        FROM extracted_signals es
        JOIN comments c ON es.comment_id = c.id
        JOIN monitored_entities me ON es.entity_id = me.id
        JOIN posts p ON c.post_id = p.id
        WHERE es.signal_type = 'sentiment'
          AND c.created_at BETWEEN :start AND :end
          AND es.numeric_value IS NOT NULL
        """)
        
        params = {"start": time_window[0], "end": time_window[1]}
        
        if platforms:
            query = text(str(query) + " AND p.platform = ANY(:platforms)")
            params["platforms"] = platforms
        
        query = text(str(query) + """
        GROUP BY me.name, me.entity_type
        ORDER BY mention_count DESC
        LIMIT :limit
        """)
        params["limit"] = limit
        
        result = self.session.execute(query, params)
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    
    def compute_velocity(
        self,
        entity_id: uuid.UUID,
        window_hours: int = 72,
        min_sample_size: int = 10
    ) -> dict:
        """
        Calculate sentiment velocity for an entity.
        Returns percent change over window.
        
        Designed for LIVE ALERTS (relative to NOW).
        For briefs, see compute_brief_velocity().
        """
        now = datetime.utcnow()
        recent_start = now - timedelta(hours=window_hours)
        previous_start = now - timedelta(hours=window_hours * 2)
        
        # Recent sentiment (last N hours)
        recent_query = text("""
            SELECT 
                AVG(es.numeric_value) as avg_sentiment,
                COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE es.entity_id = :entity_id
              AND es.signal_type = 'sentiment'
              AND es.numeric_value IS NOT NULL
              AND c.created_at BETWEEN :recent_start AND :now
        """)
        
        recent = self.session.execute(
            recent_query,
            {"entity_id": entity_id, "recent_start": recent_start, "now": now}
        ).fetchone()
        
        # Previous sentiment (previous N hours)
        previous_query = text("""
            SELECT 
                AVG(es.numeric_value) as avg_sentiment,
                COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE es.entity_id = :entity_id
              AND es.signal_type = 'sentiment'
              AND es.numeric_value IS NOT NULL
              AND c.created_at BETWEEN :previous_start AND :recent_start
        """)
        
        previous = self.session.execute(
            previous_query,
            {"entity_id": entity_id, "previous_start": previous_start, "recent_start": recent_start}
        ).fetchone()
        
        # Validation
        if not recent or not previous:
            return {"error": "No data found"}
        
        if recent.count < min_sample_size or previous.count < min_sample_size:
            return {
                "error": "Insufficient data",
                "recent_count": recent.count,
                "previous_count": previous.count,
                "min_required": min_sample_size
            }
        
        # Calculate velocity
        if previous.avg_sentiment == 0:
            percent_change = 0
        else:
            percent_change = (
                (recent.avg_sentiment - previous.avg_sentiment) / abs(previous.avg_sentiment)
            ) * 100
        
        return {
            "entity_id": str(entity_id),
            "window_hours": window_hours,
            "recent_sentiment": round(recent.avg_sentiment, 3),
            "previous_sentiment": round(previous.avg_sentiment, 3),
            "percent_change": round(percent_change, 1),
            "recent_sample_size": recent.count,
            "previous_sample_size": previous.count,
            "alert": abs(percent_change) > 30,  # Alert threshold
            "direction": "up" if percent_change > 0 else "down",
            "calculated_at": now.isoformat()
        }
    
    def compute_brief_velocity(
        self,
        entity_id: uuid.UUID,
        brief_window: Tuple[datetime, datetime]
    ) -> dict:
        """
        Calculate velocity WITHIN a brief window.
        Compares first half vs second half of window.
        
        Use this for briefs, not live alerts.
        """
        start, end = brief_window
        midpoint = start + (end - start) / 2
        
        # First half sentiment
        first_half = self.session.execute(text("""
            SELECT AVG(es.numeric_value) as avg_sentiment, COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE es.entity_id = :entity_id
              AND es.signal_type = 'sentiment'
              AND c.created_at BETWEEN :start AND :midpoint
        """), {"entity_id": entity_id, "start": start, "midpoint": midpoint}).fetchone()
        
        # Second half sentiment
        second_half = self.session.execute(text("""
            SELECT AVG(es.numeric_value) as avg_sentiment, COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE es.entity_id = :entity_id
              AND es.signal_type = 'sentiment'
              AND c.created_at BETWEEN :midpoint AND :end
        """), {"entity_id": entity_id, "midpoint": midpoint, "end": end}).fetchone()
        
        if not first_half or not second_half or first_half.count < 5 or second_half.count < 5:
            return {"error": "Insufficient data for brief window"}
        
        percent_change = (
            (second_half.avg_sentiment - first_half.avg_sentiment) / abs(first_half.avg_sentiment)
        ) * 100 if first_half.avg_sentiment != 0 else 0
        
        return {
            "entity_id": str(entity_id),
            "brief_window": f"{start.date()} to {end.date()}",
            "first_half_sentiment": round(first_half.avg_sentiment, 3),
            "second_half_sentiment": round(second_half.avg_sentiment, 3),
            "percent_change": round(percent_change, 1),
            "trending": "up" if percent_change > 0 else "down"
        }
    
    def get_entity_sentiment_history(
        self,
        entity_id: uuid.UUID,
        days: int = 30
    ) -> pd.DataFrame:
        """Time series of sentiment for charts"""
        query = text("""
        SELECT 
            DATE_TRUNC('day', c.created_at) as date,
            AVG(es.numeric_value) as avg_sentiment,
            COUNT(DISTINCT es.comment_id) as mention_count,
            SUM(c.likes) as total_likes
        FROM extracted_signals es
        JOIN comments c ON es.comment_id = c.id
        WHERE es.entity_id = :entity_id
          AND es.signal_type = 'sentiment'
          AND es.numeric_value IS NOT NULL
          AND c.created_at > NOW() - INTERVAL ':days days'
        GROUP BY date
        ORDER BY date
        """)
        
        result = self.session.execute(
            query,
            {"entity_id": entity_id, "days": days}
        )
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    
    def get_comment_count(self, time_window: Tuple[datetime, datetime]) -> int:
        """Simple count of comments in window"""
        result = self.session.execute(text("""
            SELECT COUNT(*)
            FROM comments
            WHERE created_at BETWEEN :start AND :end
        """), {"start": time_window[0], "end": time_window[1]})
        
        return result.scalar()
    
    def get_discovered_entities(
        self,
        min_mentions: int = 5,
        reviewed: bool = False,
        limit: int = 50
    ) -> pd.DataFrame:
        """
        Get list of entities discovered by spaCy but not in MonitoredEntity.
        For periodic review: "Who should we add to tracking?"
        """
        query = text("""
        SELECT 
            name,
            entity_type,
            mention_count,
            first_seen_at,
            last_seen_at,
            sample_mentions
        FROM discovered_entities
        WHERE mention_count >= :min_mentions
          AND reviewed = :reviewed
        ORDER BY mention_count DESC
        LIMIT :limit
        """)
        
        result = self.session.execute(
            query,
            {
                "min_mentions": min_mentions,
                "reviewed": reviewed,
                "limit": limit
            }
        )
        
        return pd.DataFrame(result.fetchall(), columns=result.keys())
```

**Key Improvements:**

1. **Clean numeric queries**: Using `numeric_value` directly, no casting
2. **Two velocity functions**: 
   - `compute_velocity()` for live alerts (relative to NOW)
   - `compute_brief_velocity()` for brief windows (first half vs second half)
3. **Proper SQL parameterization**: Using SQLAlchemy `text()` with bound params
4. **Timezone awareness**: All datetimes in UTC, conversions happen in presentation layer
5. **Discovered entities query**: Built-in support for reviewing unknowns

### 4. Brief Builder & Report Generation


**Separation of Compute and Presentation**

```python
from dataclasses import dataclass
from typing import List, Dict

# --- Brief Data Structure ---
@dataclass
class BriefSection:
    """One section of the brief"""
    title: str
    items: List[Dict]
    summary: Optional[str] = None

@dataclass
class IntelligenceBriefData:
    """
    Pure data structure. No PDF logic here.
    Can be rendered as PDF, Slack message, email, dashboard.
    """
    timeframe: Dict[str, datetime]
    topline_summary: Dict[str, Any]
    top_entities: BriefSection
    velocity_alerts: BriefSection
    storylines: BriefSection
    risk_signals: BriefSection
    metadata: Dict[str, Any]

# --- Brief Builder ---
class BriefBuilder:
    """
    Composes analytics results into brief structure.
    No presentation logic - just data assembly.
    """
    
    def __init__(self, analytics: AnalyticsService):
        self.analytics = analytics
    
    def build(
        self,
        start: datetime,
        end: datetime,
        platforms: Optional[List[str]] = None,
        focus_entities: Optional[List[uuid.UUID]] = None
    ) -> IntelligenceBriefData:
        """Build intelligence brief from analytics"""
        
        # Compute all metrics
        top_entities_df = self.analytics.get_top_entities(
            (start, end),
            platforms,
            limit=20
        )
        
        # Velocity checks
        velocity_alerts = []
        for _, entity in top_entities_df.head(10).iterrows():
            velocity = self.analytics.compute_velocity(entity['entity_id'])
            if velocity.get('alert'):
                velocity_alerts.append(velocity)
        
        # Assemble brief
        return IntelligenceBriefData(
            timeframe={'start': start, 'end': end},
            topline_summary={
                'total_comments': self.analytics.get_comment_count((start, end)),
                'total_entities': len(top_entities_df),
                'critical_alerts': len([v for v in velocity_alerts if abs(v['percent_change']) > 50])
            },
            top_entities=BriefSection(
                title="Top Entities by Volume",
                items=top_entities_df.to_dict('records'),
                summary=self._summarize_top_entities(top_entities_df)
            ),
            velocity_alerts=BriefSection(
                title="Sentiment Velocity Alerts",
                items=velocity_alerts,
                summary=f"{len(velocity_alerts)} entities with significant sentiment shifts"
            ),
            storylines=BriefSection(
                title="Active Storylines",
                items=[],  # Implement storyline detection
                summary=""
            ),
            risk_signals=BriefSection(
                title="Risk Signals",
                items=[],  # Implement risk detection
                summary=""
            ),
            metadata={
                'generated_at': datetime.utcnow(),
                'platforms': platforms or ['all']
            }
        )
    
    def _summarize_top_entities(self, df: pd.DataFrame) -> str:
        """Generate executive summary text"""
        if len(df) == 0:
            return "No significant entity activity in this period."
        
        top = df.iloc[0]
        sentiment_desc = "positive" if top['avg_sentiment'] > 0 else "negative"
        
        return f"{top['entity_name']} dominated conversations with {top['mention_count']} mentions and {sentiment_desc} sentiment."

# --- PDF Renderer ---
class PDFRenderer:
    """
    Takes BriefData, renders PDF.
    No computation - just formatting.
    """
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
    
    def render(self, brief: IntelligenceBriefData, filename: Optional[str] = None) -> Path:
        """Render brief as PDF"""
        if not filename:
            timestamp = brief.metadata['generated_at'].strftime("%Y%m%d_%H%M%S")
            filename = f"ET_Intelligence_Brief_{timestamp}.pdf"
        
        output_path = self.output_dir / filename
        
        # Use ReportLab to create PDF
        doc = SimpleDocTemplate(str(output_path), pagesize=letter)
        story = []
        
        # Title page
        story.extend(self._create_title(brief))
        story.append(PageBreak())
        
        # Executive summary
        story.extend(self._create_summary(brief))
        story.append(PageBreak())
        
        # Each section
        for section in [brief.top_entities, brief.velocity_alerts]:
            story.extend(self._create_section(section))
            story.append(PageBreak())
        
        doc.build(story)
        return output_path
    
    def _create_title(self, brief: IntelligenceBriefData) -> List:
        """Title page elements"""
        styles = getSampleStyleSheet()
        return [
            Paragraph("ET Social Intelligence Brief", styles['Title']),
            Spacer(1, 0.5*inch),
            Paragraph(f"Period: {brief.timeframe['start'].date()} to {brief.timeframe['end'].date()}", styles['Normal'])
        ]
    
    def _create_summary(self, brief: IntelligenceBriefData) -> List:
        """Executive summary section"""
        # Implementation...
        pass
    
    def _create_section(self, section: BriefSection) -> List:
        """Render one section"""
        # Implementation...
        pass
```



---

## Interfaces: Library-First Approach

### CLI (Direct Library Import)

**Simple, synchronous CLI that imports services directly**

```python
# cli.py
import click
from pathlib import Path
from datetime import datetime, timedelta
from et_intel.db import get_session
from et_intel.services import IngestionService, EnrichmentService, AnalyticsService
from et_intel.sources import ESUITSource, ApifySource
from et_intel.reporting import BriefBuilder, PDFRenderer

@click.group()
def cli():
    """ET Social Intelligence CLI"""
    pass

@cli.command()
@click.option('--source', type=click.Choice(['esuit', 'apify']), required=True)
@click.option('--file', type=click.Path(exists=True), required=True)
def ingest(source, file):
    """Ingest comments from CSV"""
    session = get_session()
    
    # Create appropriate source
    if source == 'esuit':
        src = ESUITSource(Path(file))
    else:
        src = ApifySource(Path(file))
    
    # Ingest
    ingestion = IngestionService(session)
    stats = ingestion.ingest(src)
    
    click.echo(f"✓ Ingested {stats['comments_created']} new comments")
    click.echo(f"✓ Updated {stats['comments_updated']} existing comments")
    click.echo(f"✓ Created {stats['posts_created']} new posts")

@cli.command()
@click.option('--since', type=click.DateTime(), help='Only enrich comments after this date')
def enrich(since):
    """Extract entities and score sentiment"""
    session = get_session()
    
    # Set up enrichment
    from et_intel.nlp import EntityExtractor, get_sentiment_provider
    entity_catalog = session.query(MonitoredEntity).filter_by(is_active=True).all()
    extractor = EntityExtractor(entity_catalog)
    sentiment_provider = get_sentiment_provider()
    
    enrichment = EnrichmentService(session, extractor, sentiment_provider)
    
    # Run enrichment
    click.echo("Processing comments...")
    stats = enrichment.enrich_comments(since=since)
    
    click.echo(f"✓ Processed {stats['comments_processed']} comments")
    click.echo(f"✓ Created {stats['signals_created']} signals")
    if stats['entities_discovered'] > 0:
        click.echo(f"ℹ Discovered {stats['entities_discovered']} new entities (run 'et-intel review-entities' to see)")

@cli.command()
@click.option('--start', type=click.DateTime(), required=True)
@click.option('--end', type=click.DateTime(), required=True)
@click.option('--platforms', multiple=True, help='Filter by platform')
@click.option('--output', type=click.Path(), help='Output file path')
def brief(start, end, platforms, output):
    """Generate intelligence brief"""
    session = get_session()
    
    # Build brief
    analytics = AnalyticsService(session)
    builder = BriefBuilder(analytics)
    
    click.echo(f"Generating brief for {start.date()} to {end.date()}...")
    brief_data = builder.build(start, end, platforms=list(platforms) if platforms else None)
    
    # Render PDF
    renderer = PDFRenderer(output_dir=Path('./reports'))
    pdf_path = renderer.render(brief_data, filename=output)
    
    click.echo(f"✓ Brief generated: {pdf_path}")
    
    # Also save JSON
    import json
    json_path = pdf_path.with_suffix('.json')
    with open(json_path, 'w') as f:
        json.dump(brief_data.dict(), f, indent=2, default=str)
    
    click.echo(f"✓ Data saved: {json_path}")

@cli.command()
@click.option('--min-mentions', default=5, help='Minimum mentions to show')
def review_entities(min_mentions):
    """Review entities discovered by spaCy"""
    session = get_session()
    analytics = AnalyticsService(session)
    
    discovered = analytics.get_discovered_entities(
        min_mentions=min_mentions,
        reviewed=False
    )
    
    if len(discovered) == 0:
        click.echo("No new entities to review.")
        return
    
    click.echo(f"\n{len(discovered)} entities discovered:\n")
    
    for _, entity in discovered.iterrows():
        click.echo(f"  {entity['name']} ({entity['entity_type']})")
        click.echo(f"    Mentions: {entity['mention_count']}")
        click.echo(f"    First seen: {entity['first_seen_at']}")
        click.echo(f"    Sample: {entity['sample_mentions'][0] if entity['sample_mentions'] else 'N/A'}")
        click.echo()
    
    click.echo("To add an entity to monitoring, use: et-intel add-entity <name>")

@cli.command()
@click.argument('name')
@click.option('--type', type=click.Choice(['person', 'show', 'couple', 'brand']), default='person')
@click.option('--aliases', multiple=True, help='Alternate names')
def add_entity(name, type, aliases):
    """Add entity to monitored list"""
    session = get_session()
    
    entity = MonitoredEntity(
        name=name,
        canonical_name=name,
        entity_type=type,
        aliases=list(aliases) if aliases else [],
        is_active=True
    )
    
    session.add(entity)
    session.commit()
    
    click.echo(f"✓ Added {name} to monitored entities")

if __name__ == '__main__':
    cli()
```

**Usage:**

```bash
# Ingest new data
$ et-intel ingest --source esuit --file data/esuit_export.csv

# Extract entities and sentiment
$ et-intel enrich

# Generate weekly brief
$ et-intel brief --start 2024-01-01 --end 2024-01-07 --platforms instagram

# Review discovered entities
$ et-intel review-entities --min-mentions 10

# Add entity to tracking
$ et-intel add-entity "Kelsea Ballerini" --type person --aliases "Kelsea"
```

### Streamlit Dashboard (Direct Library Import)

**Interactive exploration that imports services directly**

```python
# dashboard.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from et_intel.db import get_session
from et_intel.services import AnalyticsService

# Page config
st.set_page_config(
    page_title="ET Social Intelligence",
    page_icon="📊",
    layout="wide"
)

# Session state for database connection
if 'session' not in st.session_state:
    st.session_state.session = get_session()

session = st.session_state.session
analytics = AnalyticsService(session)

# Header
st.title("📊 ET Social Intelligence Dashboard")

# Sidebar filters
st.sidebar.header("Filters")
days_back = st.sidebar.slider("Days to analyze", 7, 90, 30)
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=days_back)

# Platforms filter
platforms = st.sidebar.multiselect(
    "Platforms",
    ["instagram", "youtube", "tiktok"],
    default=["instagram"]
)

# Main content
tab1, tab2, tab3 = st.tabs(["Top Entities", "Entity Deep Dive", "Discovered Entities"])

with tab1:
    st.header("Top Entities by Volume")
    
    # Fetch data
    entities_df = analytics.get_top_entities(
        (start_date, end_date),
        platforms=platforms if platforms else None,
        limit=20
    )
    
    if len(entities_df) == 0:
        st.warning("No data found for this time period.")
    else:
        # Display table with formatting
        st.dataframe(
            entities_df.style.format({
                'avg_sentiment': '{:.2f}',
                'weighted_sentiment': '{:.2f}',
                'mention_count': '{:,}',
                'total_likes': '{:,}'
            }),
            use_container_width=True
        )
        
        # Sentiment distribution chart
        import plotly.express as px
        fig = px.scatter(
            entities_df,
            x='mention_count',
            y='avg_sentiment',
            size='total_likes',
            color='avg_sentiment',
            hover_data=['entity_name', 'entity_type'],
            title='Entity Sentiment vs. Volume',
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=0
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Entity Deep Dive")
    
    # Entity selector
    if len(entities_df) > 0:
        selected_entity_name = st.selectbox(
            "Select entity",
            entities_df['entity_name'].tolist()
        )
        
        # Get entity ID
        entity_row = entities_df[entities_df['entity_name'] == selected_entity_name].iloc[0]
        entity_id = session.query(MonitoredEntity).filter_by(
            name=selected_entity_name
        ).first().id
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Mentions", f"{int(entity_row['mention_count']):,}")
        with col2:
            sentiment_val = entity_row['avg_sentiment']
            st.metric(
                "Avg Sentiment",
                f"{sentiment_val:.2f}",
                delta=None,
                delta_color="off" if abs(sentiment_val) < 0.3 else ("normal" if sentiment_val > 0 else "inverse")
            )
        with col3:
            st.metric("Total Likes", f"{int(entity_row['total_likes']):,}")
        
        # Velocity check
        st.subheader("Velocity Alert")
        velocity = analytics.compute_velocity(entity_id, window_hours=72)
        
        if 'error' not in velocity:
            if velocity['alert']:
                st.error(
                    f"⚠️ {velocity['percent_change']:+.1f}% change in last {velocity['window_hours']}h "
                    f"({velocity['previous_sentiment']:.2f} → {velocity['recent_sentiment']:.2f})"
                )
            else:
                st.success(
                    f"✓ Stable: {velocity['percent_change']:+.1f}% change in last {velocity['window_hours']}h"
                )
        else:
            st.info(f"Velocity: {velocity['error']}")
        
        # Sentiment history chart
        st.subheader("Sentiment Trend")
        history_df = analytics.get_entity_sentiment_history(entity_id, days=days_back)
        
        if len(history_df) > 0:
            import plotly.graph_objects as go
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=history_df['date'],
                y=history_df['avg_sentiment'],
                mode='lines+markers',
                name='Sentiment',
                line=dict(color='blue', width=2)
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            fig.update_layout(
                title=f"Sentiment Over Time: {selected_entity_name}",
                xaxis_title="Date",
                yaxis_title="Average Sentiment",
                yaxis_range=[-1, 1]
            )
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.header("Discovered Entities")
    st.write("Entities found by spaCy that aren't in the monitored list")
    
    # Fetch discovered
    discovered_df = analytics.get_discovered_entities(
        min_mentions=5,
        reviewed=False,
        limit=50
    )
    
    if len(discovered_df) == 0:
        st.info("No new entities discovered. All entities are being tracked!")
    else:
        st.dataframe(
            discovered_df[['name', 'entity_type', 'mention_count', 'first_seen_at', 'last_seen_at']],
            use_container_width=True
        )
        
        st.caption(f"Use CLI to add entities: `et-intel add-entity <name> --type person`")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
```

**Running:**

```bash
$ streamlit run dashboard.py
```

---

## FastAPI Layer (Phase 2 - Future)

**Only add this when you need external integrations**

When you're ready for Slack bots, webhooks, or external systems, wrap the same services:

```python
# api.py (Future Phase 2)
from fastapi import FastAPI, Depends
from et_intel.db import get_session
from et_intel.services import AnalyticsService, IngestionService

app = FastAPI(title="ET Social Intelligence API")

@app.get("/api/v1/entities")
def list_entities(
    session: Session = Depends(get_session)
):
    """Same AnalyticsService, now over HTTP"""
    analytics = AnalyticsService(session)
    df = analytics.get_top_entities(...)
    return df.to_dict('records')

# Add endpoints as needed
```

**Benefits of deferring FastAPI:**

1. **Simpler development**: No auth, CORS, deployment complexity
2. **Direct debugging**: Function calls, not HTTP requests
3. **Faster iteration**: No server to restart
4. **Same architecture**: Services stay clean, HTTP is just a wrapper

**When to add it**: When you have a stable analytics surface and actual need for programmatic access

---

## Technology Stack

### Core (MVP)
- **Language**: Python 3.11+
- **Database**: PostgreSQL 15 (native partitioning, no TimescaleDB needed)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Validation**: Pydantic v2
- **CLI**: Click
- **Dashboard**: Streamlit

### NLP/ML (MVP)
- **Entity Extraction**: spaCy 3.7
- **Sentiment**: 
  - TextBlob (free, fast baseline)
  - OpenAI API (optional, via env flag)
- **Data Processing**: pandas, numpy

### Reporting (MVP)
- **PDF**: ReportLab
- **Charts**: matplotlib or plotly

### Infrastructure (MVP)
- **Containerization**: Docker (optional)
- **Logging**: Python logging stdlib
- **Configuration**: python-dotenv

### Phase 2 (Future)
- **API**: FastAPI (when external integrations needed)
- **Advanced NLP**: HuggingFace Transformers
- **Monitoring**: Prometheus + Grafana
- **Task Queue**: Celery + Redis (if async processing needed)

---

## Implementation Roadmap (Revised for Pragmatism)

### Week 1: Foundation
**Goal**: Database + models + basic ingestion

**Tasks**:
- [ ] Set up PostgreSQL database locally
- [ ] Implement SQLAlchemy models:
  - `Post`, `Comment`, `MonitoredEntity`, `ExtractedSignal`, `DiscoveredEntity`
  - Include `numeric_value` column in signals
  - Add unique constraints
- [ ] Create Alembic migrations
- [ ] Build Pydantic models (`RawComment`, etc.)
- [ ] Implement `ESUITSource` adapter (synchronous)
- [ ] Implement `ApifySource` adapter (synchronous)
- [ ] Build `IngestionService.ingest()`
- [ ] Write unit tests for ingestion

**Deliverable**: Can ingest CSVs into clean database schema

**Validation**:
```bash
$ python -m pytest tests/test_ingestion.py
$ et-intel ingest --source esuit --file test_data.csv
$ psql -d et_intel -c "SELECT COUNT(*) FROM comments;"
```

### Week 2: NLP Layer
**Goal**: Entity extraction + sentiment working

**Tasks**:
- [ ] Load initial `MonitoredEntity` catalog from V1 data
  - Blake Lively, Justin Baldoni, Taylor Swift, etc.
- [ ] Build `EntityExtractor` with spaCy
  - Catalog matching (exact + alias)
  - Basic regex for couples ("X & Y")
- [ ] Implement `RuleBasedSentimentProvider`
  - Lexicon-based scoring
  - Emoji analysis
- [ ] Implement `OpenAISentimentProvider` (via env flag)
- [ ] Build `HybridSentimentProvider` (cheap → expensive escalation)
- [ ] Create `EnrichmentService.enrich_comments()`
  - Populate both `value` and `numeric_value`
  - Track discovered entities
- [ ] Write tests for entity extraction + sentiment

**Deliverable**: Comments get enriched with entity + sentiment signals

**Validation**:
```bash
$ et-intel enrich --since 2024-01-01
$ psql -d et_intel -c "SELECT COUNT(*) FROM extracted_signals WHERE signal_type='sentiment';"
$ psql -d et_intel -c "SELECT * FROM discovered_entities LIMIT 10;"
```

### Week 3: Analytics
**Goal**: Query layer working

**Tasks**:
- [ ] Implement `AnalyticsService.get_top_entities()`
  - Use `numeric_value` for clean aggregation
- [ ] Implement `AnalyticsService.compute_velocity()`
  - Live alert version (relative to NOW)
- [ ] Implement `AnalyticsService.compute_brief_velocity()`
  - Brief window version (first half vs second half)
- [ ] Implement `AnalyticsService.get_entity_sentiment_history()`
- [ ] Implement `AnalyticsService.get_discovered_entities()`
- [ ] Create database indexes for performance
  - `(entity_id, signal_type, created_at)`
  - `(signal_type, created_at)` for comment signals
- [ ] Write tests for analytics functions

**Deliverable**: Can query top entities, velocity, history

**Validation**:
```python
from et_intel.analytics import AnalyticsService
from et_intel.db import get_session

analytics = AnalyticsService(get_session())
df = analytics.get_top_entities((start, end))
print(df.head())

velocity = analytics.compute_velocity(entity_id)
print(velocity)
```

### Week 4: CLI
**Goal**: Command-line interface working

**Tasks**:
- [ ] Build Click CLI
  - `et-intel ingest`
  - `et-intel enrich`
  - `et-intel brief` (even if brief is just JSON for now)
  - `et-intel review-entities`
  - `et-intel add-entity`
- [ ] Add proper error handling and user feedback
- [ ] Create config loading from `.env`
- [ ] Write end-to-end CLI tests

**Deliverable**: Full workflow via CLI

**Validation**:
```bash
$ et-intel ingest --source esuit --file data.csv
✓ Ingested 1,234 new comments

$ et-intel enrich
✓ Processed 1,234 comments
✓ Created 3,702 signals

$ et-intel brief --start 2024-01-01 --end 2024-01-07
✓ Brief generated: reports/brief_20240107.json
```

### Week 5: Reporting
**Goal**: PDF briefs working

**Tasks**:
- [ ] Build `BriefBuilder.build()`
  - Compose analytics results into `BriefData` structure
  - Top entities section
  - Velocity alerts section
  - Executive summary
- [ ] Implement `PDFRenderer.render()`
  - Title page
  - Summary page
  - Entity tables
  - Velocity alerts
  - Charts (matplotlib/plotly → PDF)
- [ ] Test PDF generation end-to-end

**Deliverable**: Can generate PDF intelligence briefs

**Validation**:
```bash
$ et-intel brief --start 2024-01-01 --end 2024-01-07 --output report.pdf
✓ Brief generated: reports/report.pdf
✓ Data saved: reports/report.json

$ open reports/report.pdf  # Should look professional
```

### Week 6: Dashboard
**Goal**: Streamlit UI working

**Tasks**:
- [ ] Build Streamlit app
  - Top entities table
  - Entity selector + sentiment chart
  - Velocity alerts
  - Discovered entities tab
- [ ] Wire dashboard to services (direct import, no HTTP)
- [ ] Add filters (date range, platforms)
- [ ] Add interactive Plotly charts
- [ ] Polish UI/UX

**Deliverable**: Interactive dashboard for exploration

**Validation**:
```bash
$ streamlit run dashboard.py
# Browser opens, can explore entities, see charts, check velocity
```

### Week 7: Production Prep
**Goal**: Ready for deployment

**Tasks**:
- [ ] Docker containerization (optional but recommended)
- [ ] Environment configuration management
- [ ] Database backup/restore procedures
- [ ] Logging improvements (structured logging)
- [ ] Documentation
  - README with setup instructions
  - API docs for services
  - User guide for CLI + dashboard
- [ ] Migration script from V1 data (if needed)

**Deliverable**: Production-ready system

### Week 8: Polish & Deploy
**Goal**: Running in production

**Tasks**:
- [ ] Deploy to production server
- [ ] Set up scheduled runs (daily ingestion + enrichment via cron)
- [ ] Email report distribution (simple SMTP)
- [ ] Monitor initial runs
- [ ] Gather feedback from stakeholders
- [ ] Fix any critical issues

**Deliverable**: System live, generating daily briefs

---

## Post-MVP: Phase 2 Features

**Only add these when they're actually needed:**

### FastAPI Layer
- When: External integrations, Slack bots, webhooks needed
- Effort: 3-5 days (thin wrapper around services)
- Benefits: Programmatic access, real-time integrations

### Advanced NLP
- HuggingFace BERT for better entity recognition
- Zero-shot classification for storylines
- Emotion detection models
- Effort: 1-2 weeks

### React Dashboard
- Replace Streamlit with Next.js + React
- When: Need mobile support, better UX, custom branding
- Effort: 3-4 weeks

### Async Processing
- Background workers for enrichment
- Job queue (Celery + Redis)
- When: Processing millions of comments
- Effort: 1-2 weeks

---

## Migration Strategy from V1

### Recommended Approach: Parallel Development

1. **Build V2 in separate codebase** (Weeks 1-6)
   - New repo or separate branch
   - Fresh database schema
   - Keep V1 running as-is

2. **Backfill V2 database from V1 CSVs** (Week 7)
   - Write migration script
   - Process historical V1 data through V2 ingestion
   - Validate data integrity

3. **Parallel validation** (Week 7-8)
   - Run both systems on new data for 1-2 weeks
   - Compare outputs (entity lists, sentiment scores, velocity alerts)
   - Identify and fix discrepancies

4. **Cutover** (Week 8)
   - Switch all workflows to V2
   - Keep V1 read-only for 30 days as safety net
   - Monitor closely

5. **Archive V1** (Week 12)
   - Export final V1 data
   - Shut down V1 system
   - Document lessons learned

**Pros**: Low risk, can rollback, validates architecture
**Cons**: Takes 8-12 weeks total
**Cost**: Worth it for production system

---

## Key Improvements Over V1

### 1. **Data Model**
- **V1**: Sentiment stored in comment columns, entities in JSON files
- **V2**: Signals table = multi-perspective intelligence layer
- **Win**: Entity-targeted sentiment, extensibility without migrations

### 2. **Separation of Concerns**
- **V1**: Monolithic pipeline does everything
- **V2**: Clean services (Ingestion → Enrichment → Analytics → Reporting)
- **Win**: Testable components, reusable for other workflows

### 3. **Cost Optimization**
- **V1**: All-or-nothing OpenAI API
- **V2**: Hybrid provider (cheap → expensive escalation)
- **Win**: 30-40% cost savings with same quality

### 4. **Extensibility**
- **V1**: New metric = schema migration
- **V2**: New metric = new signal type (no migration)
- **Win**: Add emotion/toxicity/risk scores without downtime

### 5. **Interfaces**
- **V1**: CLI + basic Streamlit
- **V2**: Clean library + CLI + Streamlit (FastAPI optional)
- **Win**: Easy to add Slack bot, email reports, etc. later

### 6. **Entity Management**
- **V1**: Hardcoded config file
- **V2**: Database-driven + discovery tracking
- **Win**: Add entities without code deployment

### 7. **Pragmatic Architecture**
- **V1**: MVP grew organically
- **V2**: Library-first, add complexity only when needed
- **Win**: Simpler to build, maintain, and understand

---

## Cost Analysis

### V1 Costs
- **API**: $50-100/mo (GPT-4o-mini on all comments)
- **Infrastructure**: $0 (SQLite, local)
- **Total**: ~$100/mo

### V2 Costs (MVP)
- **API**: $30-70/mo (hybrid escalation saves 30-40%)
- **Database**: $25/mo (managed PostgreSQL on Digital Ocean)
- **Infrastructure**: $0-20/mo (can run locally or small VPS)
- **Total**: ~$55-115/mo

### V2 Costs (Production Scale)
- **API**: $50-100/mo (more volume)
- **Database**: $50/mo (larger instance)
- **Infrastructure**: $20-50/mo (proper server)
- **Total**: ~$120-200/mo

**ROI**: Better architecture for similar cost. Scale costs appear only when processing 10x more data.

---

## Success Metrics

### Technical
- [x] Library-first architecture (no forced HTTP boundaries)
- [x] 100% test coverage for services
- [ ] Sub-1s response time for analytics queries (with indexes)
- [ ] Idempotent ingestion (re-run without duplicates)
- [ ] Zero data loss (upsert logic + raw_data safety net)

### Business
- [ ] Daily briefs auto-generated
- [ ] 90%+ sentiment accuracy (vs. manual coding)
- [ ] Velocity alerts catch issues 24-48hrs before crisis
- [ ] Stakeholders reference system weekly
- [ ] 5+ entities added via discovery workflow

---

## Conclusion

V2 is a **pragmatic rebuild** that:

1. **Preserves** what V1 got right
   - Intelligence features (velocity, fatigue detection)
   - Domain knowledge (entertainment language, stan culture)
   - PDF reports + interactive exploration

2. **Fixes** architectural limitations
   - Monolithic pipeline → Clean service layer
   - Mixed storage → Unified PostgreSQL schema
   - Reactive schema → Signals-based intelligence
   - Hardcoded config → Database-driven entities

3. **Enables** future growth
   - Library-first (add FastAPI when needed)
   - Clean services (easy to test, modify, extend)
   - Extensible schema (new signals without migrations)

4. **Costs** roughly the same
   - V1: ~$100/mo
   - V2 MVP: ~$55-115/mo
   - V2 Scale: ~$120-200/mo (only at 10x volume)

**The Killer Feature**: The **signals table**. Intelligence as derived data, not stored properties. This single design decision unlocks:
- Entity-targeted sentiment ("I love Ryan but hate Blake")
- Multi-model perspectives (TextBlob + GPT both valid)
- Extensibility without migrations (add emotion/toxicity later)
- Clean separation of data and intelligence

**The Right Approach**: **Library-first**. Build clean services that CLI and Streamlit import directly. Add FastAPI only when you need external integrations. This keeps development simple while maintaining good architecture.

**Bottom Line**: 
- V1 proves the concept
- V2 makes it production-grade
- Same cost, better maintainability, unlimited extensibility

---

**Ready to build?**

Start with **Week 1: Foundation**. The database schema is the most important decision - get that right (especially the signals table with `numeric_value`) and everything else follows naturally.

The beauty of this architecture: you can build it incrementally, validate at each step, and always have a working system. No big-bang rewrite required.
