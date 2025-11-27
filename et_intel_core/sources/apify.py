"""
Apify CSV format adapter.
"""

from pathlib import Path
from typing import Iterator, Optional
from datetime import datetime
import pandas as pd

from et_intel_core.schemas import RawComment


class ApifySource:
    """
    Adapter for Apify CSV exports.
    
    Handles two formats:
    1. Simple format: shortCode, url, caption, ownerUsername, text, timestamp, likesCount
    2. Raw dataset format: media_id, text, user/username, comment_like_count, created_at, etc.
    """
    
    def __init__(self, csv_path: Path, post_urls: Optional[dict[str, str]] = None):
        """
        Initialize Apify source adapter.
        
        Args:
            csv_path: Path to Apify CSV file
            post_urls: Optional dict mapping media_id -> post_url (for raw dataset format)
        """
        self.csv_path = csv_path
        self.post_urls = post_urls or {}
    
    def iter_records(self) -> Iterator[RawComment]:
        """
        Yield normalized comments from Apify CSV.
        
        Auto-detects CSV format and handles both simple and raw dataset formats.
        """
        df = pd.read_csv(self.csv_path)
        
        # Detect format by checking for key columns
        if 'shortCode' in df.columns:
            # Simple format
            yield from self._iter_simple_format(df)
        elif 'media_id' in df.columns:
            # Raw dataset format
            yield from self._iter_raw_format(df)
        else:
            raise ValueError(f"Unknown CSV format. Expected 'shortCode' or 'media_id' column.")
    
    def _iter_simple_format(self, df: pd.DataFrame) -> Iterator[RawComment]:
        """Handle simple Apify CSV format."""
        for _, row in df.iterrows():
            yield RawComment(
                platform="instagram",
                external_post_id=row['shortCode'],
                post_url=row['url'],
                post_caption=row.get('caption', ''),
                post_subject=None,
                comment_author=row['ownerUsername'],
                comment_text=row['text'],
                comment_timestamp=pd.to_datetime(row['timestamp']),
                like_count=int(row.get('likesCount', 0)),
                raw=row.to_dict()
            )
    
    def _iter_raw_format(self, df: pd.DataFrame) -> Iterator[RawComment]:
        """Handle raw Apify dataset CSV format."""
        from et_intel_core.sources.apify_live import extract_post_id
        
        for _, row in df.iterrows():
            media_id = str(row.get('media_id', ''))
            
            # Get post URL from mapping, or construct from media_id if not provided
            post_url = self.post_urls.get(media_id)
            if not post_url:
                # Try to find by matching media_id in the URLs
                # This is a fallback - ideally post_urls should be provided
                post_url = f"https://www.instagram.com/p/{media_id}/"
            
            # Extract post ID from URL
            post_id = extract_post_id(post_url) if post_url else media_id
            
            # Extract username (handle nested column name)
            username = row.get('user/username') or row.get('user.username') or 'unknown'
            if pd.isna(username) or username == '':
                username = 'unknown'
            username = str(username)
            
            # Extract timestamp
            created_at = row.get('created_at_utc') or row.get('created_at')
            if pd.isna(created_at):
                timestamp = datetime.now()
            elif isinstance(created_at, (int, float)):
                from datetime import timezone
                timestamp = datetime.fromtimestamp(created_at, tz=timezone.utc)
            else:
                timestamp = pd.to_datetime(created_at)
            
            # Extract like count
            like_count = int(row.get('comment_like_count', 0) or row.get('like_count', 0))
            
            # Convert row to dict, handling NaN and other non-JSON types
            raw_dict = {}
            for key, value in row.items():
                if pd.isna(value):
                    raw_dict[key] = None
                elif isinstance(value, (int, float, str, bool, type(None))):
                    raw_dict[key] = value
                else:
                    raw_dict[key] = str(value)
            
            # Ensure all required fields are valid
            comment_text = row.get('text', '') or ''
            if pd.isna(comment_text):
                comment_text = ''
            comment_text = str(comment_text)
            
            # Ensure post_id and post_url are strings
            post_id = str(post_id) if post_id else 'unknown'
            post_url = str(post_url) if post_url else f"https://www.instagram.com/p/{post_id}/"
            
            yield RawComment(
                platform="instagram",
                external_post_id=post_id,
                post_url=post_url,
                post_caption=None,  # Not available in raw format
                post_subject=None,
                comment_author=username,
                comment_text=comment_text,
                comment_timestamp=timestamp,
                like_count=like_count,
                raw=raw_dict
            )

