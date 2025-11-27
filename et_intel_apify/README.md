# ET Social Intelligence - Apify Integration

Automated Instagram comment scraping for the ET Social Intelligence System.

## Overview

This module integrates [Apify's Instagram scrapers](https://apify.com/louisdeconinck/instagram-comments-scraper) into your pipeline.

**Two modes of operation:**
1. **CSV Export Mode** (recommended for validation): Export from Apify Console, merge with `ApifyMergedSource`
2. **Live API Mode**: Direct API calls with `ApifyInstagramScraper`

## Quick Start (CSV Mode - No Dependencies)

```python
from et_intel_apify import ApifyMergedSource

source = ApifyMergedSource(
    post_csv="dataset_instagram-post-scraper_xxx.csv",
    comment_csvs=[
        "dataset_instagram-comments-scraper_xxx.csv",
        "dataset_instagram-comments-scraper_yyy.csv",
    ],
    metadata_csv="dataset_instagram-post-metadata-scraper_xxx.csv",  # optional
)

for record in source.iter_records():
    print(f"@{record.comment_author}: {record.comment_text}")
    print(f"  Post: {record.post_shortcode} ({record.post_likes} likes)")
```

## The ID Matching Problem (Solved)

Apify's scrapers have an ID mismatch issue:
- **Post Scraper** returns exact IDs: `3773020515456922670`
- **Comments Scraper** returns rounded IDs: `3773020515456922000`

**Solution:** `ApifyMergedSource` uses 15-digit prefix matching to join them correctly.

```
Post ID:    3773020515456922670
Comment ID: 3773020515456922000
Match on:   377302051545692____  (first 15 digits)
```

## Data Sources

| Scraper | What It Provides | Key Fields |
|---------|------------------|------------|
| `instagram-post-scraper` | Post content & metrics | `id`, `shortCode`, `url`, `caption`, `likesCount` |
| `instagram-comments-scraper` | Comment data | `media_id`, `text`, `comment_like_count`, `user/username` |
| `instagram-post-metadata-scraper` | Rich metadata | `description`, `likes`, `upload_date` (cleaner format) |

## Output Record

Each `RawComment` includes:

```python
@dataclass
class RawComment:
    # Core fields (for your pipeline)
    post_url: str
    post_caption: str
    comment_author: str
    comment_text: str
    comment_timestamp: datetime
    comment_likes: int
    platform: str = "instagram"
    
    # Extended fields
    post_id: str           # Exact post ID
    post_shortcode: str    # e.g., "DRcdisiEjQu"
    post_likes: int        # Post like count
    comment_id: str        # Unique comment ID
    author_full_name: str  # Display name
```

## Integration with Your Pipeline

```python
from et_intel_apify import ApifyMergedSource
from et_intel_core.services.ingestion import IngestionService
from et_intel_core.db import get_session

source = ApifyMergedSource(
    post_csv="posts.csv",
    comment_csvs=["comments.csv"],
)

with get_session() as session:
    service = IngestionService(session)
    # ApifyMergedSource is protocol-compatible with your existing sources
    stats = service.ingest(source)
```

## Live API Mode

For automated scraping (requires `pip install apify-client`):

```python
from et_intel_apify import ApifyInstagramScraper

scraper = ApifyInstagramScraper(
    api_token="your-apify-token",
    max_comments_per_post=5000,
)

comments = scraper.scrape_post("https://www.instagram.com/p/DRcdisiEjQu/")
```

## Files

```
et_intel_apify/
├── __init__.py              # Package exports
├── apify_merged_source.py   # CSV merging (MAIN - no dependencies)
├── apify_scraper.py         # Live API + legacy CSV source
├── post_monitor.py          # Automated monitoring
└── requirements.txt         # Optional: apify-client
```

## Validation Results

Tested with your ET data:
- **100 posts** loaded
- **12,675 comments** matched (94.9% match rate)
- **61 unique posts** with comment activity
- Top post: Meghan Markle (1,593 comments, 46K likes)

## Setup

### 1. Install Dependencies

```bash
pip install apify-client
```

### 2. Get Apify API Token

1. Sign up at [apify.com](https://apify.com)
2. Go to Settings → Integrations
3. Copy your API token

### 3. Configure Environment

```bash
export APIFY_TOKEN="your-token-here"
```

Or add to your `.env`:
```
APIFY_TOKEN=your-token-here
```

## Usage

### Direct Scraping

```python
from et_intel_apify import ApifyInstagramScraper

scraper = ApifyInstagramScraper(
    api_token="your-token",
    max_comments_per_post=5000,
)

# Single post
comments = scraper.scrape_post("https://www.instagram.com/p/ABC123/")

for c in comments:
    print(f"@{c.author_username}: {c.text} ({c.like_count} likes)")

# Multiple posts
results = scraper.scrape_posts([
    "https://www.instagram.com/p/ABC123/",
    "https://www.instagram.com/p/DEF456/",
])
```

### Pipeline Integration

The `ApifyLiveSource` adapter fits your existing `IngestionService`:

```python
from et_intel_apify import ApifyLiveSource
from et_intel_core.services.ingestion import IngestionService
from et_intel_core.db import get_session

# Create source
source = ApifyLiveSource(
    api_token="your-token",
    post_urls=["https://www.instagram.com/p/ABC123/"],
    post_captions={"https://...": "Post about Blake Lively..."},
)

# Ingest (uses your existing pipeline)
with get_session() as session:
    service = IngestionService(session)
    stats = service.ingest(source)
    print(f"Ingested {stats['comments']} comments")
```

### Automated Monitoring

For continuous monitoring of ET's Instagram:

```python
from et_intel_apify import ETPostMonitor, ETPostConfig

config = ETPostConfig(
    account_username="entertainmenttonight",
    posts_to_monitor=20,
    rescrape_interval_hours=24,
    max_comments_per_post=5000,
)

monitor = ETPostMonitor(api_token="your-token", config=config)

# Single update
results = monitor.update_recent_posts()

# Feed to pipeline
for record in monitor.create_ingestion_source(results):
    # Your ingestion logic
    pass
```

### CLI Commands

Add to your `cli.py`:

```python
from et_intel_apify.apify_scraper import create_cli_commands
from et_intel_apify.post_monitor import create_monitor_commands

cli.add_command(create_cli_commands())  # apify group
cli.add_command(create_monitor_commands())  # monitor group
```

Then use:

```bash
# Scrape specific posts
et-intel apify scrape https://instagram.com/p/ABC123/ --output comments.csv

# Estimate costs
et-intel apify estimate URL1 URL2

# Run monitoring update
et-intel monitor update --posts 20

# Run as daemon
et-intel monitor daemon --interval 4
```

## Cost Estimation

| Comments | Without Cookies | With Cookies |
|----------|-----------------|--------------|
| 1,000    | ~$1.00          | ~$0.20       |
| 5,000    | ~$5.00          | ~$1.00       |
| 10,000   | ~$10.00         | ~$2.00       |

Plus $0.001 per Actor run.

### Using Cookies (Optional)

For cheaper scraping, provide Instagram cookies:

1. Install [Copy Cookies extension](https://chromewebstore.google.com/detail/copy-cookies/jcbpglbplpblnagieibnemmkiamekcdg)
2. Log into Instagram
3. Click extension → Copy cookies
4. Pass to scraper:

```python
scraper = ApifyInstagramScraper(
    api_token="...",
    cookies="your-cookie-string",  # 5x cheaper!
)
```

⚠️ **Note**: Using cookies ties requests to your Instagram account. Use a dedicated account.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Pipeline                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ ApifyLive    │    │ ESUITSource  │    │ ApifyCSV  │ │
│  │ Source       │    │ (existing)   │    │ Source    │ │
│  │ (new - live) │    │              │    │ (existing)│ │
│  └──────┬───────┘    └──────┬───────┘    └─────┬─────┘ │
│         │                   │                  │       │
│         └───────────────────┼──────────────────┘       │
│                             │                          │
│                             ▼                          │
│                    ┌────────────────┐                  │
│                    │ IngestionService│                  │
│                    └────────┬───────┘                  │
│                             │                          │
│                             ▼                          │
│                    ┌────────────────┐                  │
│                    │  PostgreSQL    │                  │
│                    │  (Posts,       │                  │
│                    │   Comments,    │                  │
│                    │   Signals)     │                  │
│                    └────────────────┘                  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Files

```
et_intel_apify/
├── __init__.py           # Package exports
├── apify_scraper.py      # Core scraper + IngestionSource adapter
├── post_monitor.py       # Automated ET monitoring
├── requirements.txt      # Dependencies
└── README.md             # This file
```

## Next Steps

1. **Test with real posts**: Try scraping a few ET posts to verify output format
2. **Validate data mapping**: Ensure Apify output maps correctly to your `RawComment` schema
3. **Set up scheduling**: Cron, Apify Schedules, or daemon mode
4. **Cost monitoring**: Track Apify spend in early usage

## Troubleshooting

### "Actor run failed"
- Check your Apify token is valid
- Verify you have credits/subscription
- Check the Apify Console for run logs

### Missing comments
- Some posts may have comments disabled
- Private accounts won't work without cookies
- Rate limiting may occur on very large posts

### Data format issues
- The Apify output format may vary slightly
- Check `InstagramComment.from_apify_item()` if fields are missing
- Log raw items to debug: `logger.debug(f"Raw item: {item}")`
