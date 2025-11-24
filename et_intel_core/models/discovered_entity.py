"""
DiscoveredEntity model - tracking entities found by spaCy but not in MonitoredEntity.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from et_intel_core.models.base import Base


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
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Sample contexts where this entity appeared
    sample_mentions: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Reviewed by human?
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # If reviewed, did we add to MonitoredEntity or ignore?
    action_taken: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<DiscoveredEntity(id={self.id}, name={self.name}, "
            f"mentions={self.mention_count}, reviewed={self.reviewed})>"
        )

