"""
ET Social Intelligence - Apify Integration

Automated Instagram comment scraping using Apify's Instagram Comments Scraper.

Components:
- ApifyMergedSource: Combines posts, metadata, and comments CSVs (RECOMMENDED)
- ApifyInstagramScraper: Direct API calls to Apify (requires apify-client)
- ApifyLiveSource: Live scraping as an ingestion source (requires apify-client)

Quick Start (CSV exports - no dependencies):
    from et_intel_apify import ApifyMergedSource
    
    source = ApifyMergedSource(
        post_csv="posts.csv",
        comment_csvs=["comments1.csv", "comments2.csv"],
        metadata_csv="metadata.csv",  # optional
    )
    
    for record in source.iter_records():
        # Feed to IngestionService
        pass

Quick Start (live API - requires apify-client):
    from et_intel_apify import ApifyInstagramScraper
    
    scraper = ApifyInstagramScraper(api_token="...")
    comments = scraper.scrape_post("https://instagram.com/p/...")
"""

# Merged source (no external dependencies) - RECOMMENDED
from .apify_merged_source import (
    ApifyMergedSource,
    PostData,
    RawComment,
)

# Re-export for convenience
__all__ = [
    "ApifyMergedSource",
    "PostData", 
    "RawComment",
]

# Optional: API-based sources (require apify-client)
try:
    from .apify_scraper import (
        ApifyInstagramScraper,
        ApifyLiveSource,
        ApifyMergedCSVSource,
        InstagramComment,
    )
    from .post_monitor import (
        ETPostMonitor,
        ETPostConfig,
        PostTracker,
    )
    __all__.extend([
        "ApifyInstagramScraper",
        "ApifyLiveSource",
        "ApifyMergedCSVSource",
        "InstagramComment",
        "ETPostMonitor",
        "ETPostConfig",
        "PostTracker",
    ])
except ImportError:
    # apify-client not installed, API-based sources unavailable
    pass

__version__ = "0.2.0"
