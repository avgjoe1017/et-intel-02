"""
ET Instagram Post Monitor

Automated monitoring of ET's Instagram posts for new comments.
Tracks which posts have been scraped and when, enabling incremental updates.

Usage:
    monitor = ETPostMonitor(
        api_token="...",
        db_session=session,
        et_account="entertainmenttonight"
    )
    
    # Scrape new comments from recent posts
    monitor.update_recent_posts(days=7)
    
    # Or run on a schedule
    monitor.run_scheduled(interval_hours=4)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from apify_client import ApifyClient

logger = logging.getLogger(__name__)

# Actor IDs
COMMENTS_ACTOR = "louisdeconinck/instagram-comments-scraper"
PROFILE_ACTOR = "apify/instagram-profile-scraper"  # For getting post list


@dataclass
class PostTracker:
    """
    Tracks scraped posts to enable incremental updates.
    
    Simple file-based storage - upgrade to DB table if needed.
    """
    storage_path: Path = field(default_factory=lambda: Path("data/post_tracker.json"))
    posts: dict = field(default_factory=dict)
    
    def __post_init__(self):
        self.load()
    
    def load(self):
        """Load tracking data from file."""
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                self.posts = json.load(f)
    
    def save(self):
        """Save tracking data to file."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(self.posts, f, indent=2, default=str)
    
    def mark_scraped(self, post_url: str, comment_count: int):
        """Record that a post was scraped."""
        self.posts[post_url] = {
            "last_scraped": datetime.now(timezone.utc).isoformat(),
            "comment_count": comment_count,
        }
        self.save()
    
    def get_last_scraped(self, post_url: str) -> Optional[datetime]:
        """Get when a post was last scraped."""
        if post_url in self.posts:
            ts = self.posts[post_url].get("last_scraped")
            if ts:
                return datetime.fromisoformat(ts)
        return None
    
    def needs_update(self, post_url: str, max_age_hours: int = 24) -> bool:
        """Check if a post needs to be re-scraped."""
        last = self.get_last_scraped(post_url)
        if not last:
            return True
        age = datetime.now(timezone.utc) - last
        return age > timedelta(hours=max_age_hours)


@dataclass 
class ETPostConfig:
    """Configuration for ET Instagram monitoring."""
    
    # ET's Instagram account
    account_username: str = "entertainmenttonight"
    
    # How many recent posts to monitor
    posts_to_monitor: int = 20
    
    # How often to re-scrape posts (hours)
    rescrape_interval_hours: int = 24
    
    # Max comments per post (cost control)
    max_comments_per_post: int = 5000
    
    # Cost cap per run (USD)
    max_cost_per_run: float = 5.0
    
    # Use cookies for cheaper scraping
    instagram_cookies: Optional[str] = None


class ETPostMonitor:
    """
    Monitors ET's Instagram posts for new comments.
    
    Workflow:
    1. Get list of recent posts from ET's profile
    2. Check which posts need updating (new or stale)
    3. Scrape comments from those posts
    4. Feed into ingestion pipeline
    """
    
    def __init__(
        self,
        api_token: str,
        config: Optional[ETPostConfig] = None,
        tracker: Optional[PostTracker] = None,
    ):
        self.client = ApifyClient(api_token)
        self.config = config or ETPostConfig()
        self.tracker = tracker or PostTracker()
        
    def get_recent_post_urls(self) -> list[dict]:
        """
        Fetch recent posts from ET's Instagram profile.
        
        Returns list of dicts with 'url' and 'caption' keys.
        
        Note: This requires the Instagram Profile Scraper actor.
        Alternative: Maintain a manual list of post URLs.
        """
        logger.info(f"Fetching recent posts from @{self.config.account_username}")
        
        # Run profile scraper to get post list
        run_input = {
            "usernames": [self.config.account_username],
            "resultsLimit": self.config.posts_to_monitor,
        }
        
        run = self.client.actor(PROFILE_ACTOR).call(run_input=run_input)
        
        if not run:
            logger.error("Failed to fetch profile posts")
            return []
        
        items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
        
        posts = []
        for item in items:
            # Extract post URLs from profile data
            # Structure depends on the specific actor output
            if "latestPosts" in item:
                for post in item["latestPosts"]:
                    posts.append({
                        "url": post.get("url", ""),
                        "caption": post.get("caption", ""),
                        "timestamp": post.get("timestamp"),
                    })
        
        logger.info(f"Found {len(posts)} recent posts")
        return posts
    
    def get_posts_needing_update(self, posts: list[dict]) -> list[dict]:
        """Filter posts to only those needing a scrape."""
        needs_update = []
        
        for post in posts:
            url = post["url"]
            if self.tracker.needs_update(url, self.config.rescrape_interval_hours):
                needs_update.append(post)
        
        logger.info(f"{len(needs_update)} of {len(posts)} posts need updating")
        return needs_update
    
    def scrape_posts(self, posts: list[dict]) -> dict[str, list]:
        """
        Scrape comments from posts.
        
        Returns dict mapping URL to list of comment dicts.
        """
        if not posts:
            return {}
        
        urls = [p["url"] for p in posts]
        
        run_input = {
            "urls": urls,
            "maxComments": self.config.max_comments_per_post,
        }
        
        if self.config.instagram_cookies:
            run_input["cookies"] = self.config.instagram_cookies
        
        if self.config.max_cost_per_run:
            run_input["maxCostPerRun"] = self.config.max_cost_per_run
        
        logger.info(f"Scraping {len(urls)} posts...")
        
        run = self.client.actor(COMMENTS_ACTOR).call(run_input=run_input)
        
        if not run:
            logger.error("Comment scraping failed")
            return {}
        
        items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
        logger.info(f"Retrieved {len(items)} total comments")
        
        # Group by post (simplified - may need refinement)
        results = {p["url"]: [] for p in posts}
        
        # For single post, assign all
        if len(posts) == 1:
            results[posts[0]["url"]] = items
        else:
            # Try to match by media_id or other identifier
            for item in items:
                # Assign to first post for now - refine based on actual output
                results[posts[0]["url"]].append(item)
        
        # Update tracker
        for url, comments in results.items():
            self.tracker.mark_scraped(url, len(comments))
        
        return results
    
    def update_recent_posts(self) -> dict:
        """
        Main update workflow.
        
        1. Get recent posts
        2. Filter to those needing update
        3. Scrape comments
        4. Return results for ingestion
        """
        posts = self.get_recent_post_urls()
        needs_update = self.get_posts_needing_update(posts)
        
        if not needs_update:
            logger.info("All posts are up to date")
            return {}
        
        return self.scrape_posts(needs_update)
    
    def create_ingestion_source(self, results: dict):
        """
        Create an IngestionSource from scrape results.
        
        Returns an iterator compatible with your IngestionService.
        """
        from .apify_scraper import InstagramComment, RawComment
        
        for post_url, items in results.items():
            for item in items:
                comment = InstagramComment.from_apify_item(item, post_url)
                yield RawComment(
                    post_url=post_url,
                    post_caption=None,  # Could be added from post data
                    comment_author=comment.author_username,
                    comment_text=comment.text,
                    comment_timestamp=comment.created_at,
                    comment_likes=comment.like_count,
                    platform="instagram",
                )


# =============================================================================
# Scheduling
# =============================================================================

def run_scheduled_update(
    api_token: str,
    interval_hours: int = 4,
    config: Optional[ETPostConfig] = None,
):
    """
    Run the monitor on a schedule.
    
    For production, consider using:
    - Apify Schedules (built-in)
    - Cron job
    - APScheduler
    - Celery beat
    """
    import time
    
    monitor = ETPostMonitor(api_token=api_token, config=config)
    
    while True:
        logger.info(f"Starting scheduled update at {datetime.now()}")
        
        try:
            results = monitor.update_recent_posts()
            
            total_comments = sum(len(c) for c in results.values())
            logger.info(f"Update complete: {len(results)} posts, {total_comments} comments")
            
            # TODO: Trigger ingestion pipeline
            # for record in monitor.create_ingestion_source(results):
            #     ingestion_service.ingest_record(record)
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
        
        logger.info(f"Sleeping for {interval_hours} hours")
        time.sleep(interval_hours * 3600)


# =============================================================================
# CLI Commands
# =============================================================================

def create_monitor_commands():
    """Click commands for the monitor."""
    import click
    
    @click.group(name="monitor")
    def monitor_group():
        """ET Instagram monitoring commands."""
        pass
    
    @monitor_group.command(name="update")
    @click.option("--token", envvar="APIFY_TOKEN", required=True)
    @click.option("--posts", default=20, help="Number of recent posts to check")
    @click.option("--max-comments", default=5000, help="Max comments per post")
    @click.option("--ingest", is_flag=True, help="Ingest results into database")
    def update_command(token, posts, max_comments, ingest):
        """Run a single update cycle."""
        config = ETPostConfig(
            posts_to_monitor=posts,
            max_comments_per_post=max_comments,
        )
        
        monitor = ETPostMonitor(api_token=token, config=config)
        
        click.echo("Checking for posts needing update...")
        results = monitor.update_recent_posts()
        
        total = sum(len(c) for c in results.values())
        click.echo(f"Scraped {total} comments from {len(results)} posts")
        
        if ingest:
            click.echo("Ingesting into database...")
            # Add your ingestion logic here
    
    @monitor_group.command(name="daemon")
    @click.option("--token", envvar="APIFY_TOKEN", required=True)
    @click.option("--interval", default=4, help="Hours between updates")
    def daemon_command(token, interval):
        """Run continuous monitoring daemon."""
        click.echo(f"Starting monitor daemon (interval: {interval}h)")
        click.echo("Press Ctrl+C to stop")
        
        try:
            run_scheduled_update(api_token=token, interval_hours=interval)
        except KeyboardInterrupt:
            click.echo("\nStopped")
    
    @monitor_group.command(name="status")
    def status_command():
        """Show tracking status."""
        tracker = PostTracker()
        
        click.echo(f"Tracked posts: {len(tracker.posts)}")
        
        for url, data in sorted(
            tracker.posts.items(),
            key=lambda x: x[1].get("last_scraped", ""),
            reverse=True,
        )[:10]:
            last = data.get("last_scraped", "never")[:19]
            count = data.get("comment_count", 0)
            click.echo(f"  {url[:50]}... | {count:,} comments | {last}")
    
    return monitor_group


if __name__ == "__main__":
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("Set APIFY_TOKEN environment variable")
        exit(1)
    
    monitor = ETPostMonitor(api_token=token)
    results = monitor.update_recent_posts()
    
    print(f"Got {sum(len(c) for c in results.values())} comments")
