"""
MonitoredEntity model - dynamic configuration for entity tracking.
"""

import uuid
from typing import List

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from et_intel_core.models.base import Base
from et_intel_core.models.enums import EntityType


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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Keywords for matching (stored as JSON array)
    aliases: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Relationships
    signals: Mapped[List["ExtractedSignal"]] = relationship(back_populates="entity")

    def __repr__(self) -> str:
        return f"<MonitoredEntity(id={self.id}, name={self.name}, type={self.entity_type})>"

