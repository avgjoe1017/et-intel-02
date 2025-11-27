# Apify Live Scraping Integration

## Overview

The ET Intelligence system now supports direct scraping of Instagram comments via Apify's API. This eliminates the need for CSV exports and enables real-time data ingestion with parallel processing capabilities.

## Architecture

```
Instagram Posts (URLs)
        ↓
   ApifyLiveSource
        ↓
   Apify API → Run Actor → Get Dataset
        ↓
   Transform to RawComment schema
        ↓
   IngestionService
        ↓
   PostgreSQL
```

## Key Features

- **Direct API Integration**: No CSV export step required
- **Parallel Processing**: Scrape multiple posts simultaneously
- **Cookie Support**: Use Instagram cookies for 80% cost reduction ($0.0002 vs $0.001/comment)
- **Cost Limits**: Set maximum cost per run to prevent budget overruns
- **Idempotent**: Safe to re-run without creating duplicates

## Installation

1. Install the Apify client:
```bash
pip install apify-client==1.7.0
```

2. Get your Apify API token from [Apify Console](https://console.apify.com/)

3. Set environment variable (optional):
```bash
export APIFY_TOKEN="your-token-here"
```

## Usage

### Basic Usage

```bash
python cli.py apify-scrape \
    --token YOUR_APIFY_TOKEN \
    --urls https://www.instagram.com/p/DRSmMhODnJ2/
```

### With Cookies (Cheaper Scraping)

```bash
python cli.py apify-scrape \
    --token YOUR_APIFY_TOKEN \
    --urls https://www.instagram.com/p/DRSmMhODnJ2/ \
    --cookies data/apify_cookies.json \
    --max-comments 2000
```

### Multiple Posts (Parallel Processing)

```bash
python cli.py apify-scrape \
    --token YOUR_APIFY_TOKEN \
    --urls URL1 URL2 URL3 \
    --cookies data/apify_cookies.json \
    --max-comments 2000 \
    --max-workers 5
```

### With Cost Limit

```bash
python cli.py apify-scrape \
    --token YOUR_APIFY_TOKEN \
    --urls URL1 \
    --max-comments 5000 \
    --max-cost 10.0
```

## Programmatic Usage

```python
from et_intel_core.sources.apify_live import ApifyLiveSource
from et_intel_core.services.ingestion import IngestionService
from et_intel_core.db import get_session

# Create source
source = ApifyLiveSource(
    api_token="your-token",
    post_urls=[
        "https://www.instagram.com/p/DRSmMhODnJ2/",
        "https://www.instagram.com/p/ABC123/",
    ],
    cookies=cookies_json_string,  # Optional
    max_comments=2000,
    parallel=True,
    max_workers=5,
)

# Ingest into database
session = get_session()
try:
    service = IngestionService(session)
    stats = service.ingest(source)
    print(f"Created {stats['comments_created']} comments")
finally:
    session.close()
```

## Cookie Configuration

Cookies can be provided in two formats:

### Format 1: Array of Cookie Objects
```json
{
  "cookies": [
    {
      "domain": ".instagram.com",
      "name": "sessionid",
      "value": "...",
      ...
    }
  ]
}
```

### Format 2: Direct Cookie Array
```json
[
  {
    "domain": ".instagram.com",
    "name": "sessionid",
    "value": "...",
    ...
  }
]
```

The CLI automatically handles both formats.

## Cost Estimation

**Without Cookies**:
- Base cost: ~$0.001 per comment
- Example: 10,000 comments = ~$10.00

**With Cookies**:
- Base cost: ~$0.0002 per comment
- Example: 10,000 comments = ~$2.00
- **80% cost reduction**

## Apify Actor Details

- **Actor ID**: `louisdeconinck/instagram-comments-scraper`
- **Speed**: ~10K comments in ~60 seconds
- **No Login Required**: No account ban risk
- **Output Fields**: `text`, `comment_like_count`, `created_at`, `username`

## Parallel Processing

By default, multiple posts are processed in parallel using `ThreadPoolExecutor`. This significantly speeds up scraping when processing multiple posts.

- **Default workers**: 5
- **Configurable**: Use `--max-workers` to adjust
- **Automatic**: Disabled for single post (no overhead)

## Error Handling

The integration includes comprehensive error handling:

- Network errors are logged and skipped
- Invalid URLs are handled gracefully
- Cost limits prevent budget overruns
- Failed posts don't block other posts (in parallel mode)

## Integration with Existing Pipeline

`ApifyLiveSource` implements the `IngestionSource` protocol, making it a drop-in replacement for CSV sources:

```python
# Before (CSV)
source = ApifySource(Path("comments.csv"))

# After (Live)
source = ApifyLiveSource(
    api_token=token,
    post_urls=["https://..."],
    cookies=cookies_json,
)

# Same ingestion pipeline
service = IngestionService(session)
stats = service.ingest(source)
```

## Best Practices

1. **Use Cookies**: Always use cookies when available to reduce costs by 80%
2. **Set Cost Limits**: Use `--max-cost` to prevent unexpected charges
3. **Batch Processing**: Process multiple posts in one run for efficiency
4. **Monitor Usage**: Check Apify dashboard for usage and costs
5. **Idempotent Runs**: Safe to re-run - won't create duplicates

## Troubleshooting

### "Apify Actor run failed"
- Check your API token is valid
- Verify you have sufficient Apify credits
- Check post URLs are accessible

### "No dataset ID returned"
- Actor may have failed silently
- Check Apify console for run details
- Verify actor is still available

### High Costs
- Use cookies to reduce costs by 80%
- Set `--max-cost` limit
- Reduce `--max-comments` per post

## Future Enhancements

- Scheduled runs via Apify Schedules
- Webhook integration for automatic ingestion
- Progress tracking and resumption
- Cost analytics and reporting

