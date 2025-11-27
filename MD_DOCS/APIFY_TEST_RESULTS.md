# Apify Integration Test Results

## Test Date: 2025-01-25

### Test Configuration
- **Apify Token**: Set via environment variable (`APIFY_TOKEN`)
- **Cookies**: Using `data/apify_cookies.json`
- **Max Comments**: 2000 per post
- **Test Posts**:
  1. https://www.instagram.com/p/DRSz8XLgVCC
  2. https://www.instagram.com/p/DRS626nE0Yv
  3. https://www.instagram.com/p/DRS8CkaD1vC/
  4. https://www.instagram.com/p/DRTBoTgD8Z5

### Results

#### Test 1: Single Post (DRSz8XLgVCC)
- ✅ **Status**: SUCCESS
- ✅ **Comments Retrieved**: 361 comments
- ✅ **Apify Run ID**: 6oEzWi76vhchbxrkX
- ✅ **Time**: ~30 seconds
- ✅ **Cost**: ~$0.07 (with cookies)

**Apify Logs**:
```
Post DRSz8XLgVCC (3770304286492283010): fetched 361/2000 comments
HttpCrawler: Finished! Total 26 requests: 26 succeeded, 0 failed.
Status: SUCCEEDED
```

**Notes**:
- The post had 361 comments total (less than the 2000 limit)
- All comments were successfully fetched
- Cookies were properly loaded and used (cheaper rate)

#### Database Connection Issue
- ❌ **Database**: Connection failed
- **Error**: `password authentication failed for user "postgres"`
- **Impact**: Comments were scraped successfully but not ingested into database

**Resolution Needed**:
Update `.env` file with correct `DATABASE_URL`:
```bash
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/et_intel
```

### Next Steps

1. **Fix Database Connection**: Update `.env` with correct PostgreSQL credentials
2. **Test Multiple Posts**: Run all 4 posts in parallel
3. **Verify Ingestion**: Confirm comments are properly stored in database
4. **Test Post Captions**: Verify that post captions are captured (Apify should include this)

### Performance Metrics

- **Speed**: ~12 comments/second (361 comments in 30 seconds)
- **Reliability**: 100% success rate
- **Cost Efficiency**: ~80% reduction with cookies ($0.0002 vs $0.001 per comment)

### Integration Status

✅ **Working**:
- Apify API connection
- Token authentication
- Cookie loading
- Comment scraping
- URL parsing
- Progress tracking

⚠️ **Needs Configuration**:
- Database connection
- Multiple URL handling (needs verification)

### Command Used

```bash
python cli.py apify-scrape \
    --urls "https://www.instagram.com/p/DRSz8XLgVCC" \
    --cookies data/apify_cookies.json \
    --max-comments 2000
```

