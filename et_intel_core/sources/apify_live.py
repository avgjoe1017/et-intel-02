"""
Apify Live Scraper - Direct API integration for Instagram comments.

This module provides an IngestionSource that scrapes Instagram comments
directly from Apify's API, supporting parallel processing for multiple posts.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Iterator, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from apify_client import ApifyClient

from et_intel_core.schemas import RawComment
from et_intel_core.sources.base import IngestionSource

logger = logging.getLogger(__name__)

# The Actor ID for the Instagram Comments Scraper
ACTOR_ID = "louisdeconinck/instagram-comments-scraper"


def extract_post_id(url: str) -> str:
    """
    Extract post ID from Instagram URL.
    
    Examples:
        https://www.instagram.com/p/DRSmMhODnJ2/ -> DRSmMhODnJ2
        https://instagram.com/p/ABC123 -> ABC123
        /p/XYZ789/ -> XYZ789
    """
    # Remove trailing slash
    url = url.rstrip('/')
    
    # Try to match /p/SHORTCODE pattern
    match = re.search(r'/p/([^/?]+)', url)
    if match:
        return match.group(1)
    
    # Fallback: take last segment
    parts = url.split('/')
    return parts[-1] if parts else url


def parse_timestamp(ts: Optional[float]) -> datetime:
    """Parse Unix timestamp to datetime."""
    if ts is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(ts, tz=timezone.utc)


class ApifyLiveSource(IngestionSource):
    """
    Live Apify scraper that implements IngestionSource protocol.
    
    Scrapes Instagram comments directly from Apify API and yields
    RawComment objects compatible with IngestionService.
    
    Supports:
    - Multiple posts in parallel
    - Cookie-based authentication (cheaper scraping)
    - Cost limits
    - Progress tracking
    
    Usage:
        source = ApifyLiveSource(
            api_token="your-token",
            post_urls=["https://www.instagram.com/p/ABC123/"],
            cookies=cookies_json_string,
            max_comments=2000
        )
        
        service = IngestionService(session)
        stats = service.ingest(source)
    """
    
    def __init__(
        self,
        api_token: str,
        post_urls: list[str],
        post_captions: Optional[dict[str, str]] = None,
        post_subjects: Optional[dict[str, str]] = None,
        max_comments: int = 10000,
        cookies: Optional[str] = None,
        max_cost: Optional[float] = None,
        parallel: bool = True,
        max_workers: int = 5,
    ):
        """
        Initialize Apify live source.
        
        Args:
            api_token: Apify API token
            post_urls: List of Instagram post URLs to scrape
            post_captions: Optional dict mapping URL -> caption text
            post_subjects: Optional dict mapping URL -> editorial subject
            max_comments: Maximum comments to fetch per post
            cookies: Optional Instagram cookies JSON string (for cheaper scraping)
            max_cost: Optional cost cap per run in USD
            parallel: Whether to process multiple posts in parallel
            max_workers: Max parallel workers (if parallel=True)
        """
        self.client = ApifyClient(api_token)
        self.post_urls = post_urls
        self.post_captions = post_captions or {}
        self.post_subjects = post_subjects or {}
        self.max_comments = max_comments
        self.cookies = cookies
        self.max_cost = max_cost
        self.parallel = parallel and len(post_urls) > 1
        self.max_workers = max_workers
        
    def iter_records(self) -> Iterator[RawComment]:
        """
        Scrape posts and yield RawComment records.
        
        If parallel=True and multiple posts, processes them concurrently.
        Otherwise processes sequentially.
        """
        if self.parallel and len(self.post_urls) > 1:
            yield from self._iter_records_parallel()
        else:
            yield from self._iter_records_sequential()
    
    def _iter_records_sequential(self) -> Iterator[RawComment]:
        """Process posts sequentially."""
        results = self._scrape_posts(self.post_urls)
        
        for post_url, items in results.items():
            post_id = extract_post_id(post_url)
            caption = self.post_captions.get(post_url)
            subject = self.post_subjects.get(post_url)
            
            for item in items:
                yield self._item_to_raw_comment(item, post_url, post_id, caption, subject)
    
    def _iter_records_parallel(self) -> Iterator[RawComment]:
        """Process posts in parallel using ThreadPoolExecutor."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all posts for scraping
            future_to_url = {
                executor.submit(self._scrape_single_post, url): url
                for url in self.post_urls
            }
            
            # Yield results as they complete
            for future in as_completed(future_to_url):
                post_url = future_to_url[future]
                try:
                    items = future.result()
                    post_id = extract_post_id(post_url)
                    caption = self.post_captions.get(post_url)
                    subject = self.post_subjects.get(post_url)
                    
                    for item in items:
                        yield self._item_to_raw_comment(item, post_url, post_id, caption, subject)
                except Exception as e:
                    logger.error(f"Error scraping {post_url}: {e}")
                    continue
    
    def _scrape_single_post(self, post_url: str) -> list[dict]:
        """Scrape a single post (for parallel processing)."""
        results = self._scrape_posts([post_url])
        return results.get(post_url, [])
    
    def _scrape_posts(self, urls: list[str]) -> dict[str, list[dict]]:
        """
        Scrape comments from multiple posts using Apify.
        
        Returns dict mapping post URL to list of comment items.
        """
        if not urls:
            return {}
        
        logger.info(f"Starting Apify run for {len(urls)} post(s)")
        
        # Build input for the Actor
        run_input = {
            "urls": urls,
            "maxComments": self.max_comments,
        }
        
        if self.cookies:
            # Apify expects cookies as a JSON string representation of the array
            # Convert to string if it's not already
            import json
            if isinstance(self.cookies, str):
                # Already a string - use as is (should be valid JSON)
                run_input["cookies"] = self.cookies
            elif isinstance(self.cookies, list):
                # Convert array to JSON string
                run_input["cookies"] = json.dumps(self.cookies)
            else:
                # Single cookie object - wrap in array then stringify
                run_input["cookies"] = json.dumps([self.cookies])
            
        if self.max_cost:
            run_input["maxCostPerRun"] = self.max_cost
        
        # Run the Actor and wait for completion
        try:
            run = self.client.actor(ACTOR_ID).call(run_input=run_input)
            
            if not run:
                logger.error("Apify Actor run failed")
                return {url: [] for url in urls}
            
            logger.info(f"Apify run completed: {run.get('status')}")
            
            # Fetch results from the dataset
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                logger.error("No dataset ID returned from run")
                return {url: [] for url in urls}
            
            # Get dataset info to check item count
            dataset_client = self.client.dataset(dataset_id)
            try:
                dataset_info = dataset_client.get()
                item_count = dataset_info.get("itemCount", 0)
                logger.info(f"Dataset {dataset_id} has {item_count} items according to metadata")
            except Exception as e:
                logger.warning(f"Could not get dataset info: {e}")
                item_count = 0
            
            # Fetch dataset items - Apify returns items as a list
            # Note: iterate_items() may return empty if dataset is still being populated
            # or if posts genuinely have no comments
            try:
                items = list(dataset_client.iterate_items())
                logger.info(f"Retrieved {len(items)} items from Apify dataset (expected {item_count})")
            except Exception as e:
                logger.error(f"Error fetching dataset items: {e}")
                items = []
            
            # Debug: Log first item structure if available
            if items and len(items) > 0:
                logger.info(f"Sample item keys: {list(items[0].keys())[:10]}")
                logger.debug(f"First item (truncated): {str(items[0])[:200]}")
            else:
                logger.warning(f"No items found in dataset for URLs: {urls}")
                if item_count > 0:
                    logger.warning(f"Dataset metadata says {item_count} items, but iterate_items() returned 0. This may indicate a dataset access issue.")
                else:
                    logger.info("This likely means: 1) Posts have no comments, 2) Posts are private/restricted, 3) Cookies are invalid/expired")
            
            # Group comments by post URL
            # Apify returns items with media_id or post_url - we need to match them
            results: dict[str, List[dict]] = {url: [] for url in urls}
            
            # If single post, assign all comments to it
            if len(urls) == 1:
                results[urls[0]] = items
            else:
                # Try to match items to posts by media_id or URL
                for item in items:
                    # Try to extract post URL from item
                    item_url = item.get("post_url") or item.get("url")
                    media_id = item.get("media_id", "")
                    
                    matched = False
                    for url in urls:
                        # Match by URL or by media_id in URL
                        if item_url and url in item_url:
                            results[url].append(item)
                            matched = True
                            break
                        elif media_id and media_id in url:
                            results[url].append(item)
                            matched = True
                            break
                    
                    # If no match, assign to first post (fallback)
                    if not matched:
                        results[urls[0]].append(item)
            
            return results
            
        except Exception as e:
            logger.error(f"Error during Apify scraping: {e}")
            return {url: [] for url in urls}
    
    def _item_to_raw_comment(
        self,
        item: dict,
        post_url: str,
        post_id: str,
        caption: Optional[str],
        subject: Optional[str],
    ) -> RawComment:
        """
        Convert Apify item to RawComment schema.
        
        Apify item structure:
        {
            "pk": "comment_id",
            "text": "comment text",
            "created_at": 1234567890.0,  # Unix timestamp
            "comment_like_count": 42,
            "user": {
                "username": "author_username",
                "full_name": "Author Name",
                ...
            },
            "media_id": "post_id",
            ...
        }
        """
        # Extract user info
        user = item.get("user", {})
        username = user.get("username", "unknown")
        
        # Parse timestamp
        created_at = parse_timestamp(
            item.get("created_at") or item.get("created_at_utc")
        )
        
        # Extract like count
        like_count = item.get("comment_like_count", 0)
        
        # Build raw data dict for debugging
        raw_data = {
            "apify_item": item,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        
        return RawComment(
            platform="instagram",
            external_post_id=post_id,
            post_url=post_url,
            post_caption=caption,
            post_subject=subject,
            comment_author=username,
            comment_text=item.get("text", ""),
            comment_timestamp=created_at,
            like_count=like_count,
            raw=raw_data,
        )

