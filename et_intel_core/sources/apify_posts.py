"""
Apify Post Scraper CSV adapter - for ingesting post metadata with captions.
"""

from pathlib import Path
from typing import Iterator
from datetime import datetime, timezone
import pandas as pd

from et_intel_core.schemas import RawComment
from et_intel_core.sources.base import IngestionSource


class ApifyPostSource(IngestionSource):
    """
    Adapter for Apify Post Scraper CSV exports.
    
    This is different from ApifySource - it handles post metadata (captions, likes, comments count)
    rather than comment data.
    
    Key columns:
    - caption: Post caption text
    - shortCode: Post ID
    - url: Post URL
    - commentsCount: Number of comments
    - likesCount: Number of likes
    - timestamp: When post was created
    """
    
    def __init__(self, csv_path: Path):
        """
        Initialize Apify post source adapter.
        
        Args:
            csv_path: Path to Apify Post Scraper CSV file
        """
        self.csv_path = csv_path
    
    def iter_records(self) -> Iterator[RawComment]:
        """
        Yield RawComment records with post metadata.
        
        This is a bit of a hack - we yield minimal comment records
        just to trigger post creation/update. The real value is in
        the post_caption field which gets stored in the Post model.
        """
        df = pd.read_csv(self.csv_path)
        
        for _, row in df.iterrows():
            # Extract post ID from shortCode (primary identifier)
            post_id = str(row.get('shortCode', ''))
            if pd.isna(post_id) or not post_id:
                continue
            
            # Also get numeric ID (media_id) for matching existing posts
            numeric_id = row.get('id')
            if pd.isna(numeric_id):
                numeric_id = None
            else:
                numeric_id = str(int(numeric_id)) if isinstance(numeric_id, (int, float)) else str(numeric_id)
            
            # Get post URL
            post_url = row.get('url') or row.get('inputUrl', '')
            if pd.isna(post_url) or not post_url:
                post_url = f"https://www.instagram.com/p/{post_id}/"
            post_url = str(post_url)
            
            # Get caption
            caption = row.get('caption', '')
            if pd.isna(caption):
                caption = None
            else:
                caption = str(caption)
            
            # Get timestamp
            timestamp = row.get('timestamp')
            if pd.isna(timestamp):
                posted_at = datetime.now(timezone.utc)
            elif isinstance(timestamp, (int, float)):
                posted_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            else:
                try:
                    posted_at = pd.to_datetime(timestamp)
                    if posted_at.tzinfo is None:
                        posted_at = posted_at.replace(tzinfo=timezone.utc)
                except:
                    posted_at = datetime.now(timezone.utc)
            
            # Build raw data dict
            raw_dict = {}
            for key, value in row.items():
                if pd.isna(value):
                    raw_dict[key] = None
                elif isinstance(value, (int, float, str, bool, type(None))):
                    raw_dict[key] = value
                else:
                    raw_dict[key] = str(value)
            
            # Yield a dummy comment record to trigger post creation/update
            # The post_caption will be stored in the Post model
            # We yield TWO records: one with shortCode, one with numeric ID
            # This ensures we match existing posts created from comments CSV
            yield RawComment(
                platform="instagram",
                external_post_id=post_id,  # shortCode (primary)
                post_url=post_url,
                post_caption=caption,
                post_subject=None,
                comment_author="__POST_METADATA__",  # Dummy author to indicate this is post metadata
                comment_text="",  # Empty comment text
                comment_timestamp=posted_at,
                like_count=0,
                raw={
                    "post_metadata": {
                        "comments_count": int(row.get('commentsCount', 0) or 0),
                        "likes_count": int(row.get('likesCount', 0) or 0),
                        "post_type": row.get('type', ''),
                        "owner_username": row.get('ownerUsername', ''),
                        "numeric_id": numeric_id,  # Store numeric ID for matching
                    },
                    "raw_row": raw_dict,
                }
            )
            
            # Also yield a record with numeric ID if available, to match existing posts
            if numeric_id and numeric_id != post_id:
                yield RawComment(
                    platform="instagram",
                    external_post_id=numeric_id,  # numeric ID (for matching)
                    post_url=post_url,
                    post_caption=caption,
                    post_subject=None,
                    comment_author="__POST_METADATA__",
                    comment_text="",
                    comment_timestamp=posted_at,
                    like_count=0,
                    raw={
                        "post_metadata": {
                            "comments_count": int(row.get('commentsCount', 0) or 0),
                            "likes_count": int(row.get('likesCount', 0) or 0),
                            "post_type": row.get('type', ''),
                            "owner_username": row.get('ownerUsername', ''),
                            "shortCode": post_id,  # Store shortCode for reference
                        },
                        "raw_row": raw_dict,
                    }
                )

