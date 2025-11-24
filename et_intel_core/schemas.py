"""
Pydantic models for data validation and serialization.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RawComment(BaseModel):
    """
    Normalized comment from any source.
    Used for ingestion validation.
    """
    platform: str = Field(..., description="Social media platform")
    external_post_id: str = Field(..., description="Post ID from platform")
    post_url: str = Field(..., description="URL to the post")
    post_caption: Optional[str] = Field(None, description="Post caption/description")
    post_subject: Optional[str] = Field(None, description="Editorial subject line")
    comment_author: str = Field(..., description="Comment author username")
    comment_text: str = Field(..., description="Comment text content")
    comment_timestamp: datetime = Field(..., description="When comment was posted")
    like_count: int = Field(default=0, description="Number of likes")
    raw: dict = Field(default_factory=dict, description="Original row for debugging")

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "instagram",
                "external_post_id": "ABC123",
                "post_url": "https://instagram.com/p/ABC123/",
                "post_caption": "Check out this post!",
                "post_subject": "Taylor Swift at Chiefs Game",
                "comment_author": "user123",
                "comment_text": "Love this!",
                "comment_timestamp": "2024-01-01T12:00:00Z",
                "like_count": 42,
                "raw": {}
            }
        }

