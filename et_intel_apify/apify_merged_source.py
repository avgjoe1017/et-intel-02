"""
Apify Merged Source - Combines Posts, Metadata, and Comments

This module handles the tricky ID matching between Apify's different scrapers:
- Post Scraper: Has exact post IDs (e.g., 3773020515456922670)
- Metadata Scraper: Has exact IDs in al:ios:url field
- Comments Scraper: Has ROUNDED media_ids (e.g., 3773020515456922000)

The join strategy uses 15-digit prefix matching to handle the rounding.

Usage:
    source = ApifyMergedSource(
        post_csv="posts.csv",                    # From instagram-post-scraper
        comment_csvs=["comments1.csv", ...],     # From instagram-comments-scraper
        metadata_csv="metadata.csv",             # Optional: from instagram-post-metadata-scraper
    )
    
    for record in source.iter_records():
        # Full RawComment with post context
        pass
"""

import csv
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PostData:
    """Merged post data from all sources."""
    # Identifiers
    post_id: str                    # Exact ID from post scraper
    shortcode: str                  # e.g., "DRcdisiEjQu"
    url: str                        # Full URL
    
    # Content
    caption: str                    # Full caption text
    description: str                # Cleaned description (from metadata)
    alt_text: str                   # Image alt text
    
    # Metrics
    likes_count: Optional[int]      # From post scraper (exact) or metadata (approx)
    comments_count: Optional[int]   # Expected comment count
    
    # Timestamps
    timestamp: Optional[datetime]   # Post creation time
    upload_date: Optional[str]      # Human-readable date from metadata
    
    # Media
    display_url: str                # Image/video URL
    media_type: str                 # "image", "video", etc.
    video_url: Optional[str]
    video_play_count: Optional[int]
    
    # Owner
    owner_id: str
    owner_username: str
    
    # Raw data for debugging
    raw_post: dict = field(default_factory=dict, repr=False)
    raw_metadata: dict = field(default_factory=dict, repr=False)


@dataclass
class RawComment:
    """
    Comment record ready for ingestion pipeline.
    
    Matches the schema expected by your IngestionService.
    """
    post_url: str
    post_caption: Optional[str]
    comment_author: str
    comment_text: str
    comment_timestamp: datetime
    comment_likes: int
    platform: str = "instagram"
    
    # Extended fields (optional, for richer analysis)
    post_id: Optional[str] = None
    post_shortcode: Optional[str] = None
    post_likes: Optional[int] = None
    post_description: Optional[str] = None
    comment_id: Optional[str] = None
    author_full_name: Optional[str] = None
    author_is_verified: bool = False


class ApifyMergedSource:
    """
    Unified ingestion source that merges Apify post, metadata, and comment exports.
    
    Handles the ID matching complexity:
    - Posts have exact IDs: 3773020515456922670
    - Comments have rounded IDs: 3773020515456922000
    - Match on first 15 digits (prefix match)
    
    Data priority (when fields overlap):
    1. Post scraper (most complete structured data)
    2. Metadata scraper (cleaner descriptions, social stats)
    3. Derived/computed values
    """
    
    def __init__(
        self,
        post_csv: Optional[str] = None,
        comment_csvs: Optional[list[str]] = None,
        metadata_csv: Optional[str] = None,
        metadata_csvs: Optional[list[str]] = None,
    ):
        """
        Initialize the merged source.
        
        Args:
            post_csv: Path to instagram-post-scraper export
            comment_csvs: List of paths to instagram-comments-scraper exports
            metadata_csv: Optional path to instagram-post-metadata-scraper export (single file)
            metadata_csvs: Optional list of paths to metadata exports (multiple files)
        """
        self.post_csv = post_csv
        self.comment_csvs = comment_csvs or []
        
        # Support both single file and multiple files for metadata
        self.metadata_csvs: list[str] = []
        if metadata_csvs:
            self.metadata_csvs.extend(metadata_csvs)
        if metadata_csv:
            self.metadata_csvs.append(metadata_csv)
        
        # Lookup dictionaries
        self._posts_by_id: dict[str, PostData] = {}
        self._posts_by_prefix: dict[str, str] = {}  # prefix -> post_id
        self._posts_by_shortcode: dict[str, str] = {}  # shortcode -> post_id
        
        # Load data
        self._load_posts()
        self._load_metadata()
        
        logger.info(f"Loaded {len(self._posts_by_id)} posts ready for comment matching")
    
    def _load_posts(self):
        """Load posts from instagram-post-scraper export."""
        if not self.post_csv or not Path(self.post_csv).exists():
            logger.warning("No post CSV provided or file not found")
            return
        
        with open(self.post_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                post_id = row.get("id", "")
                if not post_id:
                    continue
                
                # Parse timestamp
                ts = None
                ts_str = row.get("timestamp", "")
                if ts_str:
                    try:
                        # Instagram timestamps are usually ISO format or Unix
                        if ts_str.isdigit():
                            ts = datetime.fromtimestamp(int(ts_str), tz=timezone.utc)
                        else:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass
                
                # Parse counts
                likes = self._parse_int(row.get("likesCount"))
                comments = self._parse_int(row.get("commentsCount"))
                video_plays = self._parse_int(row.get("videoPlayCount"))
                
                post = PostData(
                    post_id=post_id,
                    shortcode=row.get("shortCode", ""),
                    url=row.get("url", ""),
                    caption=row.get("caption", ""),
                    description="",  # Will be enriched from metadata
                    alt_text=row.get("alt", ""),
                    likes_count=likes,
                    comments_count=comments,
                    timestamp=ts,
                    upload_date=None,
                    display_url=row.get("displayUrl", ""),
                    media_type=row.get("type", "image"),
                    video_url=row.get("videoUrl"),
                    video_play_count=video_plays,
                    owner_id=row.get("ownerId", ""),
                    owner_username=row.get("ownerUsername", ""),
                    raw_post=dict(row),
                )
                
                self._posts_by_id[post_id] = post
                self._posts_by_prefix[post_id[:15]] = post_id
                if post.shortcode:
                    self._posts_by_shortcode[post.shortcode] = post_id
        
        logger.info(f"Loaded {len(self._posts_by_id)} posts from {self.post_csv}")
    
    def _load_metadata(self):
        """
        Load and merge metadata from instagram-post-metadata-scraper exports.
        
        This enriches existing posts with cleaner descriptions and social stats,
        and adds any posts that are missing from the post scraper export.
        """
        if not self.metadata_csvs:
            logger.debug("No metadata CSVs provided")
            return
        
        enriched = 0
        new_posts = 0
        
        for metadata_csv in self.metadata_csvs:
            if not Path(metadata_csv).exists():
                logger.warning(f"Metadata file not found: {metadata_csv}")
                continue
            
            with open(metadata_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Extract exact media ID from al:ios:url
                    ios_url = row.get("Post_Metadata/al:ios:url", "")
                    match = re.search(r'id=(\d+)', ios_url)
                    media_id = match.group(1) if match else None
                    
                    shortcode = row.get("Post_Metadata/shortcode", "")
                    
                    if not media_id:
                        continue
                    
                    # Find existing post to enrich
                    post_id = None
                    if media_id in self._posts_by_id:
                        post_id = media_id
                    else:
                        # Try prefix match
                        post_id = self._posts_by_prefix.get(media_id[:15])
                    
                    # Also try shortcode match
                    if not post_id and shortcode:
                        post_id = self._posts_by_shortcode.get(shortcode)
                    
                    # Extract clean description
                    description = row.get("description", "") or row.get("Post_Metadata/og:description", "")
                    upload_date = row.get("upload_date", "")
                    likes_str = row.get("likes", "")
                    comments_str = row.get("comments", "")
                    
                    if post_id and post_id in self._posts_by_id:
                        # Enrich existing post
                        post = self._posts_by_id[post_id]
                        post.description = description
                        post.upload_date = upload_date
                        post.raw_metadata = dict(row)
                        
                        # Update counts if we don't have them
                        if post.likes_count is None:
                            post.likes_count = self._parse_likes(likes_str)
                        if post.comments_count is None:
                            post.comments_count = self._parse_int(comments_str)
                        
                        enriched += 1
                        
                        # Also register the exact media_id for matching
                        if media_id and media_id not in self._posts_by_id:
                            self._posts_by_id[media_id] = post
                            self._posts_by_prefix[media_id[:15]] = post_id
                    
                    else:
                        # Create new post from metadata only
                        url = row.get("original_url", "") or row.get("Post_Metadata/og:url", "")
                        
                        post = PostData(
                            post_id=media_id,
                            shortcode=shortcode,
                            url=url,
                            caption=row.get("Post_Metadata/caption", ""),
                            description=description,
                            alt_text="",
                            likes_count=self._parse_likes(likes_str),
                            comments_count=self._parse_int(comments_str),
                            timestamp=None,
                            upload_date=upload_date,
                            display_url=row.get("Post_Metadata/og:image", ""),
                            media_type=row.get("Post_Metadata/medium", "image"),
                            video_url=None,
                            video_play_count=None,
                            owner_id=row.get("Post_Metadata/owner_user_id", ""),
                            owner_username=row.get("author_username", ""),
                            raw_metadata=dict(row),
                        )
                        
                        self._posts_by_id[media_id] = post
                        self._posts_by_prefix[media_id[:15]] = media_id
                        if shortcode:
                            self._posts_by_shortcode[shortcode] = media_id
                        
                        new_posts += 1
                        logger.info(f"Added post from metadata: {shortcode} ({post.likes_count} likes)")
        
        logger.info(f"Metadata: enriched {enriched} posts, added {new_posts} new posts")
    
    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Parse integer from string, handling empty/None."""
        if not value:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _parse_likes(self, value: str) -> Optional[int]:
        """Parse likes count, handling '22k' style values."""
        if not value:
            return None
        value = value.lower().strip()
        try:
            if 'k' in value:
                return int(float(value.replace('k', '')) * 1000)
            elif 'm' in value:
                return int(float(value.replace('m', '')) * 1000000)
            else:
                return int(value)
        except (ValueError, TypeError):
            return None
    
    def find_post(self, media_id: str) -> Optional[PostData]:
        """
        Find a post by media_id (handles rounded IDs from comments).
        
        Tries:
        1. Exact match
        2. Prefix match (first 15 digits)
        """
        # Exact match
        if media_id in self._posts_by_id:
            return self._posts_by_id[media_id]
        
        # Prefix match for rounded IDs
        prefix = media_id[:15]
        post_id = self._posts_by_prefix.get(prefix)
        if post_id:
            return self._posts_by_id.get(post_id)
        
        return None
    
    def iter_records(self) -> Iterator[RawComment]:
        """
        Iterate through all comments, yielding RawComment records.
        
        Each comment is matched to its post for context.
        Unmatched comments are logged but skipped.
        """
        matched = 0
        unmatched = 0
        
        for comment_csv in self.comment_csvs:
            if not Path(comment_csv).exists():
                logger.warning(f"Comment file not found: {comment_csv}")
                continue
            
            logger.info(f"Processing {comment_csv}")
            
            with open(comment_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    media_id = row.get("media_id", "")
                    post = self.find_post(media_id)
                    
                    if not post:
                        unmatched += 1
                        if unmatched <= 10:
                            logger.debug(f"No post match for media_id: {media_id}")
                        continue
                    
                    matched += 1
                    
                    # Parse timestamp
                    ts_str = row.get("created_at_utc") or row.get("created_at")
                    try:
                        ts = datetime.fromtimestamp(int(ts_str), tz=timezone.utc)
                    except (ValueError, TypeError):
                        ts = datetime.now(timezone.utc)
                    
                    # Parse like count
                    like_count = self._parse_int(
                        row.get("comment_like_count") or row.get("like_count")
                    ) or 0
                    
                    # Get author info
                    author = row.get("user/username", "") or row.get("username", "") or "unknown"
                    author_full = row.get("user/full_name", "") or row.get("full_name", "")
                    author_verified = row.get("user/is_verified", "").lower() == "true"
                    
                    # Choose best caption/description
                    caption = post.description or post.caption
                    
                    yield RawComment(
                        # Core fields for your pipeline
                        post_url=post.url,
                        post_caption=caption,
                        comment_author=author,
                        comment_text=row.get("text", ""),
                        comment_timestamp=ts,
                        comment_likes=like_count,
                        platform="instagram",
                        
                        # Extended fields
                        post_id=post.post_id,
                        post_shortcode=post.shortcode,
                        post_likes=post.likes_count,
                        post_description=post.description,
                        comment_id=row.get("pk", ""),
                        author_full_name=author_full,
                        author_is_verified=author_verified,
                    )
        
        logger.info(f"Processed {matched + unmatched} comments: {matched} matched, {unmatched} unmatched")
    
    def get_stats(self) -> dict:
        """Return statistics about loaded data."""
        return {
            "posts_loaded": len(self._posts_by_id),
            "posts_with_metadata": sum(1 for p in self._posts_by_id.values() if p.raw_metadata),
            "unique_prefixes": len(self._posts_by_prefix),
            "shortcodes_indexed": len(self._posts_by_shortcode),
        }


# =============================================================================
# CLI Integration
# =============================================================================

def create_merge_cli_commands():
    """Click commands for merged source operations."""
    import click
    
    @click.group(name="merge")
    def merge_group():
        """Merge and ingest Apify exports."""
        pass
    
    @merge_group.command(name="ingest")
    @click.option("--posts", "-p", required=True, type=click.Path(exists=True),
                  help="Post scraper CSV")
    @click.option("--comments", "-c", multiple=True, required=True, type=click.Path(exists=True),
                  help="Comment scraper CSV(s)")
    @click.option("--metadata", "-m", type=click.Path(exists=True),
                  help="Optional metadata scraper CSV")
    @click.option("--output", "-o", type=click.Path(),
                  help="Output merged CSV (for inspection)")
    @click.option("--db", is_flag=True, help="Ingest directly to database")
    def ingest_command(posts, comments, metadata, output, db):
        """
        Merge Apify exports and optionally ingest to database.
        
        Example:
            et-intel merge ingest -p posts.csv -c comments1.csv -c comments2.csv -m metadata.csv
        """
        source = ApifyMergedSource(
            post_csv=posts,
            comment_csvs=list(comments),
            metadata_csv=metadata,
        )
        
        stats = source.get_stats()
        click.echo(f"Loaded {stats['posts_loaded']} posts ({stats['posts_with_metadata']} with metadata)")
        
        records = list(source.iter_records())
        click.echo(f"Processed {len(records)} comments")
        
        if output:
            # Write merged data to CSV for inspection
            with open(output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "post_url", "post_shortcode", "post_caption", "post_likes",
                    "comment_author", "comment_text", "comment_likes", "comment_timestamp"
                ])
                writer.writeheader()
                for r in records:
                    writer.writerow({
                        "post_url": r.post_url,
                        "post_shortcode": r.post_shortcode,
                        "post_caption": (r.post_caption or "")[:200],
                        "post_likes": r.post_likes,
                        "comment_author": r.comment_author,
                        "comment_text": r.comment_text,
                        "comment_likes": r.comment_likes,
                        "comment_timestamp": r.comment_timestamp.isoformat(),
                    })
            click.echo(f"Wrote merged data to {output}")
        
        if db:
            click.echo("Database ingestion not implemented - wire up your IngestionService here")
            # from et_intel_core.db import get_session
            # from et_intel_core.services.ingestion import IngestionService
            # with get_session() as session:
            #     service = IngestionService(session)
            #     service.ingest(source)
    
    @merge_group.command(name="stats")
    @click.option("--posts", "-p", type=click.Path(exists=True))
    @click.option("--comments", "-c", multiple=True, type=click.Path(exists=True))
    @click.option("--metadata", "-m", type=click.Path(exists=True))
    def stats_command(posts, comments, metadata):
        """Show statistics about Apify exports."""
        source = ApifyMergedSource(
            post_csv=posts,
            comment_csvs=list(comments) if comments else [],
            metadata_csv=metadata,
        )
        
        stats = source.get_stats()
        click.echo("Data Statistics:")
        for k, v in stats.items():
            click.echo(f"  {k}: {v}")
        
        if comments:
            # Count comments without loading all into memory
            total = 0
            matched = 0
            for csv_file in comments:
                with open(csv_file, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        total += 1
                        if source.find_post(row.get("media_id", "")):
                            matched += 1
            
            click.echo(f"  total_comments: {total}")
            click.echo(f"  matched_comments: {matched}")
            click.echo(f"  match_rate: {matched/total*100:.1f}%")
    
    return merge_group


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    
    source = ApifyMergedSource(
        post_csv="/mnt/user-data/uploads/dataset_instagram-post-scraper_2025-11-26_04-34-50-076.csv",
        comment_csvs=[
            "/mnt/user-data/uploads/dataset_instagram-comments-scraper_2025-11-26_04-18-53-697.csv",
            "/mnt/user-data/uploads/dataset_instagram-comments-scraper_2025-11-26_04-35-02-756.csv",
            "/mnt/user-data/uploads/dataset_instagram-comments-scraper_2025-11-26_04-51-14-308.csv",
            "/mnt/user-data/uploads/dataset_instagram-comments-scraper_2025-11-26_05-09-43-642.csv",
        ],
        metadata_csv="/mnt/user-data/uploads/dataset_instagram-post-metadata-scraper_2025-11-26_05-24-17-006.csv",
    )
    
    print(f"\nStats: {source.get_stats()}")
    
    # Sample records
    print("\nSample records:")
    for i, record in enumerate(source.iter_records()):
        if i >= 3:
            break
        print(f"  @{record.comment_author}: {record.comment_text[:40]}...")
        print(f"    Post: {record.post_shortcode} | {record.post_likes} likes")
        print()
