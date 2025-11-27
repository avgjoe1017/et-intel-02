"""
Apify Instagram Comments Scraper Integration

This module integrates the Apify Instagram Comments Scraper into the ET Social Intelligence
pipeline. It provides both direct API calls and an IngestionSource adapter that fits your
existing architecture.

Usage:
    # Direct scraping
    scraper = ApifyInstagramScraper(api_token="your-token")
    comments = scraper.scrape_post("https://www.instagram.com/p/ABC123/")
    
    # As ingestion source (fits your existing pipeline)
    source = ApifyLiveSource(api_token="your-token", post_urls=["https://..."])
    for record in source.iter_records():
        # RawComment objects ready for IngestionService
        pass

Actor ID: louisdeconinck/instagram-comments-scraper
Pricing: ~$0.001/comment (no cookie) or ~$0.0002/comment (with cookie)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator, Optional
import logging

from apify_client import ApifyClient

logger = logging.getLogger(__name__)

# The Actor ID for the Instagram Comments Scraper
ACTOR_ID = "louisdeconinck/instagram-comments-scraper"


@dataclass
class InstagramComment:
    """Raw comment data from Apify scraper."""
    comment_id: str
    post_url: str
    text: str
    author_username: str
    author_full_name: str
    like_count: int
    created_at: datetime
    is_private: bool
    profile_pic_url: Optional[str] = None
    
    @classmethod
    def from_apify_item(cls, item: dict, post_url: str) -> "InstagramComment":
        """Convert Apify output item to InstagramComment."""
        # Parse timestamp - Apify returns Unix timestamp
        created_at_ts = item.get("created_at") or item.get("created_at_utc")
        if created_at_ts:
            created_at = datetime.fromtimestamp(created_at_ts, tz=timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)
        
        # Extract user info
        user = item.get("user", {})
        
        return cls(
            comment_id=str(item.get("pk", "")),
            post_url=post_url,
            text=item.get("text", ""),
            author_username=user.get("username", "unknown"),
            author_full_name=user.get("full_name", ""),
            like_count=item.get("comment_like_count", 0),
            created_at=created_at,
            is_private=user.get("is_private", False),
            profile_pic_url=user.get("profile_pic_url"),
        )


class ApifyInstagramScraper:
    """
    Direct interface to Apify Instagram Comments Scraper.
    
    This handles the API calls and returns structured data.
    """
    
    def __init__(
        self,
        api_token: str,
        max_comments_per_post: int = 10000,
        cookies: Optional[str] = None,
        max_cost_per_run: Optional[float] = None,
    ):
        """
        Initialize the scraper.
        
        Args:
            api_token: Your Apify API token
            max_comments_per_post: Maximum comments to scrape per post (default 10000)
            cookies: Optional Instagram cookies for cheaper scraping ($0.0002 vs $0.001/comment)
            max_cost_per_run: Optional cost cap per run in USD
        """
        self.client = ApifyClient(api_token)
        self.max_comments = max_comments_per_post
        self.cookies = cookies
        self.max_cost = max_cost_per_run
        
    def scrape_post(self, post_url: str) -> list[InstagramComment]:
        """
        Scrape comments from a single Instagram post.
        
        Args:
            post_url: Full URL or shortcode of the Instagram post
            
        Returns:
            List of InstagramComment objects
        """
        return self.scrape_posts([post_url]).get(post_url, [])
    
    def scrape_posts(self, post_urls: list[str]) -> dict[str, list[InstagramComment]]:
        """
        Scrape comments from multiple Instagram posts in a single run.
        
        Args:
            post_urls: List of Instagram post URLs or shortcodes
            
        Returns:
            Dict mapping post URL to list of comments
        """
        # Build input for the Actor
        run_input = {
            "urls": post_urls,
            "maxComments": self.max_comments,
        }
        
        if self.cookies:
            run_input["cookies"] = self.cookies
            
        if self.max_cost:
            run_input["maxCostPerRun"] = self.max_cost
        
        logger.info(f"Starting Apify run for {len(post_urls)} post(s)")
        
        # Run the Actor and wait for completion
        run = self.client.actor(ACTOR_ID).call(run_input=run_input)
        
        if not run:
            logger.error("Apify Actor run failed")
            return {}
        
        logger.info(f"Apify run completed: {run.get('status')}")
        
        # Fetch results from the dataset
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            logger.error("No dataset ID returned from run")
            return {}
        
        items = list(self.client.dataset(dataset_id).iterate_items())
        logger.info(f"Retrieved {len(items)} comments from Apify")
        
        # Group comments by post URL
        # Note: The scraper might not return the original URL in each item,
        # so we may need to handle this differently based on actual output
        results: dict[str, list[InstagramComment]] = {url: [] for url in post_urls}
        
        for item in items:
            # Try to match to original URL - this might need adjustment
            # based on actual Apify output structure
            media_id = item.get("media_id", "")
            
            # For now, if single URL, assign all to it
            if len(post_urls) == 1:
                target_url = post_urls[0]
            else:
                # Try to find matching URL (may need refinement)
                target_url = post_urls[0]  # Fallback
                for url in post_urls:
                    if media_id in url or url in str(item):
                        target_url = url
                        break
            
            comment = InstagramComment.from_apify_item(item, target_url)
            results[target_url].append(comment)
        
        return results


# =============================================================================
# CSV-Based Source (for Apify exports)
# =============================================================================

class ApifyMergedCSVSource:
    """
    Ingestion source that merges Apify post and comment CSV exports.
    
    Handles the ID matching issue where comment media_ids are rounded versions
    of post IDs (match on first 15 digits).
    
    Usage:
        source = ApifyMergedCSVSource(
            post_csv="posts.csv",
            comment_csvs=["comments1.csv", "comments2.csv"],
        )
        
        for record in source.iter_records():
            # RawComment with post_caption populated
            pass
    """
    
    def __init__(
        self,
        post_csv: str,
        comment_csvs: list[str],
    ):
        self.post_csv = post_csv
        self.comment_csvs = comment_csvs
        self._posts_by_id: dict = {}
        self._posts_by_prefix: dict = {}
        self._load_posts()
    
    def _load_posts(self):
        """Load posts into lookup dictionaries."""
        import csv
        
        with open(self.post_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                post_id = row.get("id", "")
                self._posts_by_id[post_id] = {
                    "url": row.get("url", ""),
                    "shortCode": row.get("shortCode", ""),
                    "caption": row.get("caption", ""),
                    "timestamp": row.get("timestamp", ""),
                    "likesCount": row.get("likesCount", ""),
                    "commentsCount": row.get("commentsCount", ""),
                }
                # Prefix for fuzzy matching (first 15 digits)
                prefix = post_id[:15]
                self._posts_by_prefix[prefix] = post_id
        
        logger.info(f"Loaded {len(self._posts_by_id)} posts from {self.post_csv}")
    
    def _match_post(self, media_id: str) -> Optional[dict]:
        """
        Match a comment's media_id to a post.
        
        Comments have rounded media_ids, posts have exact IDs.
        Match on first 15 digits.
        """
        # Exact match
        if media_id in self._posts_by_id:
            return self._posts_by_id[media_id]
        
        # Prefix match
        prefix = media_id[:15]
        post_id = self._posts_by_prefix.get(prefix)
        if post_id:
            return self._posts_by_id[post_id]
        
        return None
    
    def iter_records(self) -> Iterator["RawComment"]:
        """Yield RawComment records with post data merged in."""
        import csv
        from datetime import datetime, timezone
        
        for comment_csv in self.comment_csvs:
            logger.info(f"Processing {comment_csv}")
            
            with open(comment_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    media_id = row.get("media_id", "")
                    post = self._match_post(media_id)
                    
                    if not post:
                        logger.debug(f"No post match for media_id {media_id}")
                        continue
                    
                    # Parse timestamp
                    ts_str = row.get("created_at_utc") or row.get("created_at")
                    if ts_str:
                        try:
                            ts = datetime.fromtimestamp(int(ts_str), tz=timezone.utc)
                        except (ValueError, TypeError):
                            ts = datetime.now(timezone.utc)
                    else:
                        ts = datetime.now(timezone.utc)
                    
                    # Parse like count
                    like_count = 0
                    like_str = row.get("comment_like_count") or row.get("like_count") or "0"
                    try:
                        like_count = int(like_str)
                    except ValueError:
                        pass
                    
                    # Get author info
                    author = row.get("user/username", "") or row.get("username", "unknown")
                    
                    yield RawComment(
                        post_url=post["url"],
                        post_caption=post["caption"],
                        comment_author=author,
                        comment_text=row.get("text", ""),
                        comment_timestamp=ts,
                        comment_likes=like_count,
                        platform="instagram",
                    )


# =============================================================================
# Integration with ET Social Intelligence Pipeline
# =============================================================================

@dataclass
class RawComment:
    """
    Schema matching your existing et_intel_core/schemas.py RawComment.
    
    This is duplicated here for standalone use - in production, import from your schemas.
    """
    post_url: str
    post_caption: Optional[str]
    comment_author: str
    comment_text: str
    comment_timestamp: datetime
    comment_likes: int
    platform: str = "instagram"


class ApifyLiveSource:
    """
    IngestionSource adapter for live Apify scraping.
    
    Fits your existing Protocol-based architecture:
        class IngestionSource(Protocol):
            def iter_records(self) -> Iterator[RawComment]: ...
    
    Usage:
        source = ApifyLiveSource(
            api_token="your-token",
            post_urls=["https://www.instagram.com/p/ABC123/"]
        )
        
        ingestion_service = IngestionService(session)
        ingestion_service.ingest(source)
    """
    
    def __init__(
        self,
        api_token: str,
        post_urls: list[str],
        post_captions: Optional[dict[str, str]] = None,
        max_comments_per_post: int = 10000,
        cookies: Optional[str] = None,
    ):
        """
        Initialize live Apify source.
        
        Args:
            api_token: Apify API token
            post_urls: List of Instagram post URLs to scrape
            post_captions: Optional dict mapping URL -> caption text
            max_comments_per_post: Max comments to fetch per post
            cookies: Optional Instagram cookies for cheaper scraping
        """
        self.scraper = ApifyInstagramScraper(
            api_token=api_token,
            max_comments_per_post=max_comments_per_post,
            cookies=cookies,
        )
        self.post_urls = post_urls
        self.post_captions = post_captions or {}
        
    def iter_records(self) -> Iterator[RawComment]:
        """
        Scrape Instagram posts and yield RawComment records.
        
        This method triggers the Apify scraper, waits for results,
        and yields records compatible with your IngestionService.
        """
        # Scrape all posts
        results = self.scraper.scrape_posts(self.post_urls)
        
        for post_url, comments in results.items():
            caption = self.post_captions.get(post_url)
            
            for comment in comments:
                yield RawComment(
                    post_url=post_url,
                    post_caption=caption,
                    comment_author=comment.author_username,
                    comment_text=comment.text,
                    comment_timestamp=comment.created_at,
                    comment_likes=comment.like_count,
                    platform="instagram",
                )


# =============================================================================
# CLI Integration
# =============================================================================

def create_cli_commands():
    """
    Click commands for CLI integration.
    
    Add these to your cli.py:
    
        from et_intel_apify.apify_scraper import create_cli_commands
        apify_commands = create_cli_commands()
        cli.add_command(apify_commands)
    """
    import click
    
    @click.group(name="apify")
    def apify_group():
        """Apify Instagram scraper commands."""
        pass
    
    @apify_group.command(name="scrape")
    @click.argument("urls", nargs=-1, required=True)
    @click.option("--token", envvar="APIFY_TOKEN", required=True, help="Apify API token")
    @click.option("--max-comments", default=10000, help="Max comments per post")
    @click.option("--output", "-o", type=click.Path(), help="Output CSV file")
    @click.option("--ingest", is_flag=True, help="Directly ingest into database")
    def scrape_command(urls, token, max_comments, output, ingest):
        """
        Scrape Instagram comments from URLs.
        
        Examples:
            et-intel apify scrape https://www.instagram.com/p/ABC123/
            et-intel apify scrape URL1 URL2 --output comments.csv
            et-intel apify scrape URL1 --ingest
        """
        scraper = ApifyInstagramScraper(
            api_token=token,
            max_comments_per_post=max_comments,
        )
        
        click.echo(f"Scraping {len(urls)} post(s)...")
        results = scraper.scrape_posts(list(urls))
        
        total_comments = sum(len(c) for c in results.values())
        click.echo(f"Retrieved {total_comments} comments")
        
        if output:
            # Export to CSV
            import csv
            with open(output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "post_url", "comment_id", "author", "text", 
                    "likes", "created_at"
                ])
                writer.writeheader()
                for post_url, comments in results.items():
                    for c in comments:
                        writer.writerow({
                            "post_url": post_url,
                            "comment_id": c.comment_id,
                            "author": c.author_username,
                            "text": c.text,
                            "likes": c.like_count,
                            "created_at": c.created_at.isoformat(),
                        })
            click.echo(f"Saved to {output}")
        
        if ingest:
            click.echo("Ingesting into database...")
            # Import your actual services here
            # from et_intel_core.db import get_session
            # from et_intel_core.services.ingestion import IngestionService
            # 
            # with get_session() as session:
            #     source = ApifyLiveSource(api_token=token, post_urls=list(urls))
            #     service = IngestionService(session)
            #     service.ingest(source)
            click.echo("(Ingest not implemented - uncomment imports in production)")
    
    @apify_group.command(name="estimate")
    @click.argument("urls", nargs=-1, required=True)
    @click.option("--with-cookies", is_flag=True, help="Estimate with cookies (cheaper)")
    def estimate_command(urls, with_cookies):
        """
        Estimate cost for scraping posts.
        
        Example:
            et-intel apify estimate URL1 URL2
        """
        # Rough estimates based on Apify pricing
        per_run = 0.001
        per_comment_no_cookie = 0.001
        per_comment_with_cookie = 0.0002
        
        per_comment = per_comment_with_cookie if with_cookies else per_comment_no_cookie
        
        click.echo("Cost Estimates (assuming 1000 comments per post):")
        click.echo(f"  Posts: {len(urls)}")
        click.echo(f"  Rate: ${per_comment}/comment {'(with cookies)' if with_cookies else '(no cookies)'}")
        click.echo(f"  Base cost: ${per_run:.3f}")
        
        for est_comments in [100, 500, 1000, 5000, 10000]:
            cost = per_run + (est_comments * len(urls) * per_comment)
            click.echo(f"  {est_comments:,} comments/post: ${cost:.2f}")
    
    return apify_group


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    import os
    
    # Example: Direct usage
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("Set APIFY_TOKEN environment variable")
        exit(1)
    
    scraper = ApifyInstagramScraper(api_token=token, max_comments_per_post=100)
    
    # Test with a sample URL (replace with real URL)
    test_url = "https://www.instagram.com/p/CmUv48DLvxd/"
    print(f"Scraping {test_url}...")
    
    comments = scraper.scrape_post(test_url)
    print(f"Got {len(comments)} comments")
    
    for c in comments[:5]:
        print(f"  @{c.author_username}: {c.text[:50]}... ({c.like_count} likes)")
