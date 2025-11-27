"""
Apify Post Metadata Scraper CSV adapter - for ingesting post metadata with captions.
This handles the metadata-only CSV format (different from post-scraper format).
"""

from pathlib import Path
from typing import Iterator
from datetime import datetime, timezone
import pandas as pd

from et_intel_core.schemas import RawComment
from et_intel_core.sources.base import IngestionSource


class ApifyMetadataSource(IngestionSource):
    """
    Adapter for Apify Post Metadata Scraper CSV exports.
    
    This format has:
    - Post_Metadata/shortcode: Post shortCode
    - Post_Metadata/caption: Post caption
    - original_url: Post URL
    - likes, comments: Engagement metrics
    - upload_date: When post was created
    """
    
    def __init__(self, csv_path: Path):
        """
        Initialize Apify metadata source adapter.
        
        Args:
            csv_path: Path to Apify Post Metadata Scraper CSV file
        """
        self.csv_path = csv_path
    
    def iter_records(self) -> Iterator[RawComment]:
        """
        Yield RawComment records with post metadata.
        
        This yields minimal comment records to trigger post creation/update.
        The real value is in the post_caption field which gets stored in the Post model.
        """
        df = pd.read_csv(self.csv_path)
        
        for _, row in df.iterrows():
            # Extract shortCode from nested column
            shortcode = row.get('Post_Metadata/shortcode') or row.get('shortcode', '')
            if pd.isna(shortcode) or not shortcode:
                continue
            post_id = str(shortcode)
            
            # Get post URL
            post_url = row.get('original_url') or row.get('Post_Metadata/og:url', '')
            if pd.isna(post_url) or not post_url:
                post_url = f"https://www.instagram.com/p/{post_id}/"
            post_url = str(post_url).rstrip('/')
            
            # Get caption from nested column
            caption = row.get('Post_Metadata/caption') or row.get('caption', '')
            if pd.isna(caption):
                caption = None
            else:
                caption = str(caption)
            
            # Get timestamp
            upload_date = row.get('upload_date')
            if pd.isna(upload_date):
                posted_at = datetime.now(timezone.utc)
            else:
                try:
                    posted_at = pd.to_datetime(upload_date)
                    if posted_at.tzinfo is None:
                        posted_at = posted_at.replace(tzinfo=timezone.utc)
                except:
                    posted_at = datetime.now(timezone.utc)
            
            # Get engagement metrics (handle "46k" style values)
            likes_str = str(row.get('likes', '') or '')
            comments_str = str(row.get('comments', '') or '')
            
            def parse_count(value: str) -> int:
                """Parse count, handling '46k', '1.2m' style values."""
                if not value or pd.isna(value):
                    return 0
                value = str(value).lower().strip()
                try:
                    if 'k' in value:
                        return int(float(value.replace('k', '')) * 1000)
                    elif 'm' in value:
                        return int(float(value.replace('m', '')) * 1000000)
                    else:
                        return int(float(value))
                except (ValueError, TypeError):
                    return 0
            
            likes = parse_count(likes_str)
            comments = parse_count(comments_str)
            
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
            yield RawComment(
                platform="instagram",
                external_post_id=post_id,  # shortCode
                post_url=post_url,
                post_caption=caption,
                post_subject=None,
                comment_author="__POST_METADATA__",
                comment_text="",
                comment_timestamp=posted_at,
                like_count=0,
                raw={
                    "post_metadata": {
                        "comments_count": comments,
                        "likes_count": likes,
                        "source": "metadata_scraper",
                    },
                    "raw_row": raw_dict,
                }
            )

