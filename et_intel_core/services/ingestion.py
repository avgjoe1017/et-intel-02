"""
Ingestion service - orchestrates data ingestion into database.
"""

from typing import Dict
from sqlalchemy.orm import Session

from et_intel_core.sources.base import IngestionSource
from et_intel_core.schemas import RawComment
from et_intel_core.models import Post, Comment
from et_intel_core.models.enums import ContextType


class IngestionService:
    """
    Orchestrates ingestion into database.
    
    Key features:
    - Idempotent: won't duplicate existing comments
    - Synchronous: simple, debuggable, sufficient for CSV volumes
    - Batch commits: every 100 records for efficiency
    """
    
    def __init__(self, session: Session):
        """
        Initialize ingestion service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
    
    def ingest(self, source: IngestionSource) -> Dict[str, int]:
        """
        Ingest comments from any source.
        
        Idempotent: can be re-run without creating duplicates.
        Synchronous: simple and sufficient for CSV volumes.
        
        Args:
            source: Any object implementing IngestionSource protocol
            
        Returns:
            Dictionary with ingestion statistics:
            - posts_created: Number of new posts created
            - posts_updated: Number of existing posts updated
            - comments_created: Number of new comments created
            - comments_updated: Number of existing comments updated
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
        
        # Final commit
        self.session.commit()
        return stats
    
    def _get_or_create_post(self, record: RawComment) -> tuple[Post, bool]:
        """
        Get existing post or create new one.
        
        Args:
            record: Normalized comment data
            
        Returns:
            Tuple of (post, created_flag)
            - post: The Post object
            - created_flag: True if newly created, False if existing
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

