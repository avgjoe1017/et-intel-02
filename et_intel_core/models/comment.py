"""
Comment model - the atomic unit of data.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from et_intel_core.models.base import Base
from et_intel_core.models.enums import ContextType


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
    likes: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Threading
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("comments.id"), 
        nullable=True
    )
    context_type: Mapped[ContextType] = mapped_column(
        String(50),
        default=ContextType.DIRECT
    )

    # For future extensions (language, toxicity, etc.)
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    post: Mapped["Post"] = relationship(back_populates="comments")
    replies: Mapped[List["Comment"]] = relationship(
        back_populates="parent",
        remote_side=[id]
    )
    parent: Mapped[Optional["Comment"]] = relationship(
        back_populates="replies",
        remote_side=[parent_id]
    )
    signals: Mapped[List["ExtractedSignal"]] = relationship(
        back_populates="comment",
        cascade="all, delete-orphan"
    )
    review_queue_items: Mapped[List["ReviewQueue"]] = relationship(back_populates="comment")

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, author={self.author_name}, text={self.text[:50]}...)>"

