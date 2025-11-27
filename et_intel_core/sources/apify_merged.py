"""
Adapter for ApifyMergedSource to work with IngestionSource protocol.
"""

from pathlib import Path
from typing import Iterator, Optional
import logging

from et_intel_core.schemas import RawComment as CoreRawComment
from et_intel_core.sources.base import IngestionSource

logger = logging.getLogger(__name__)

try:
    from et_intel_apify import ApifyMergedSource, RawComment as ApifyRawComment
except ImportError:
    logger.error("et_intel_apify not found. Install it or add to path.")
    ApifyMergedSource = None
    ApifyRawComment = None


class ApifyMergedAdapter(IngestionSource):
    """
    Adapter that wraps ApifyMergedSource to work with IngestionSource protocol.
    
    This handles the complex ID matching between Apify's different scrapers
    and merges posts, metadata, and comments into a unified stream.
    """
    
    def __init__(
        self,
        post_csv: Optional[Path] = None,
        comment_csvs: Optional[list[Path]] = None,
        metadata_csv: Optional[Path] = None,
        metadata_csvs: Optional[list[Path]] = None,
    ):
        """
        Initialize the merged source adapter.
        
        Args:
            post_csv: Path to instagram-post-scraper export
            comment_csvs: List of paths to instagram-comments-scraper exports
            metadata_csv: Optional path to instagram-post-metadata-scraper export (single file)
            metadata_csvs: Optional list of paths to metadata exports (multiple files)
        """
        if ApifyMergedSource is None:
            raise ImportError("et_intel_apify module not found. Please ensure it's installed or in the path.")
        
        # Convert Path objects to strings
        post_str = str(post_csv) if post_csv else None
        comment_strs = [str(c) for c in (comment_csvs or [])]
        metadata_str = str(metadata_csv) if metadata_csv else None
        metadata_strs = [str(m) for m in (metadata_csvs or [])] if metadata_csvs else None
        
        self.merged_source = ApifyMergedSource(
            post_csv=post_str,
            comment_csvs=comment_strs,
            metadata_csv=metadata_str,
            metadata_csvs=metadata_strs,
        )
    
    def iter_records(self) -> Iterator[CoreRawComment]:
        """
        Yield RawComment records compatible with IngestionSource protocol.
        
        Converts from ApifyMergedSource's RawComment format to the core schema.
        """
        for apify_record in self.merged_source.iter_records():
            # Convert ApifyRawComment to CoreRawComment
            yield CoreRawComment(
                platform=apify_record.platform,
                external_post_id=apify_record.post_shortcode or apify_record.post_id or "",
                post_url=apify_record.post_url,
                post_caption=apify_record.post_caption,
                post_subject=None,
                comment_author=apify_record.comment_author,
                comment_text=apify_record.comment_text,
                comment_timestamp=apify_record.comment_timestamp,
                like_count=apify_record.comment_likes,
                raw={
                    "post_metadata": {
                        "post_id": apify_record.post_id,
                        "post_shortcode": apify_record.post_shortcode,
                        "post_likes": apify_record.post_likes,
                        "post_description": apify_record.post_description,
                    },
                    "comment_metadata": {
                        "comment_id": apify_record.comment_id,
                        "author_full_name": apify_record.author_full_name,
                        "author_is_verified": apify_record.author_is_verified,
                    },
                }
            )

