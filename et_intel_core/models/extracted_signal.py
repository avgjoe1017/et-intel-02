"""
ExtractedSignal model - THE KILLER TABLE.

Intelligence as derived data, not stored properties.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Float, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from et_intel_core.models.base import Base
from et_intel_core.models.enums import SignalType


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
    
    # FIX 10: Indexes for fast querying
    # All analytics queries filter by signal_type, many also filter by entity_id
    __table_args__ = (
        # Prevent duplicate signals (same comment + entity + type + model)
        UniqueConstraint(
            'comment_id', 
            'entity_id', 
            'signal_type', 
            'source_model',
            name='uq_signal_identity'
        ),
        # Performance indexes for common query patterns
        Index('ix_signals_type', 'signal_type'),
        Index('ix_signals_entity_type', 'entity_id', 'signal_type'),
        Index('ix_signals_comment', 'comment_id'),
        Index('ix_signals_numeric', 'signal_type', 'numeric_value'),
    )

    def __repr__(self) -> str:
        return (
            f"<ExtractedSignal(id={self.id}, type={self.signal_type}, "
            f"value={self.value}, numeric={self.numeric_value})>"
        )

