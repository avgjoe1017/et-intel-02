"""
Post model - parent container for comments.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from et_intel_core.models.base import Base
from et_intel_core.models.enums import PlatformType


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
    subject_line: Mapped[Optional[str]] = mapped_column(String, nullable=True)
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

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, platform={self.platform}, external_id={self.external_id})>"

