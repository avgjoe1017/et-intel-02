"""
ReviewQueue model - entities/mentions that need human review for disambiguation.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from et_intel_core.models.base import Base


class ReviewQueue(Base):
    """
    Queue for human review of ambiguous entity mentions.
    
    Created when:
    - GPT finds an entity mention but confidence is low
    - Entity name is ambiguous (e.g., "Justin" could be multiple people)
    - Context doesn't clearly disambiguate
    
    Workflow:
    1. System queues ambiguous mention
    2. Human reviews and assigns to correct entity (or creates new)
    3. System processes queued items with human decisions
    """
    __tablename__ = "review_queue"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # What needs review
    comment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comments.id"))
    entity_mention: Mapped[str] = mapped_column(String)  # The ambiguous name found
    context: Mapped[str] = mapped_column(Text)  # Comment text + post caption for context
    post_caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Why it needs review
    confidence: Mapped[float] = mapped_column(Float)  # GPT's confidence (0.0-1.0)
    possible_entities: Mapped[list[str]] = mapped_column(JSONB, default=list)  # Possible matches
    reason: Mapped[str] = mapped_column(String)  # Why it's ambiguous (e.g., "Multiple Justins in context")
    
    # Review status
    reviewed: Mapped[bool] = mapped_column(default=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Human reviewer
    
    # Human decision
    assigned_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("monitored_entities.id"),
        nullable=True
    )
    assigned_entity_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # In case new entity
    decision: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "assign", "ignore", "new_entity"
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    comment: Mapped["Comment"] = relationship(back_populates="review_queue_items")
    assigned_entity: Mapped[Optional["MonitoredEntity"]] = relationship(back_populates="review_queue_items")
    
    def __repr__(self) -> str:
        return (
            f"<ReviewQueue(id={self.id}, mention={self.entity_mention}, "
            f"confidence={self.confidence}, reviewed={self.reviewed})>"
        )

