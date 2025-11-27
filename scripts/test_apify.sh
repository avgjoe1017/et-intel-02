#!/bin/bash
# Quick test script for Apify integration

echo "Testing Apify Live Scraping..."
echo ""

# Test with the provided post URL
python cli.py apify-scrape \
    --urls https://www.instagram.com/p/DRSmMhODnJ2/ \
    --cookies data/apify_cookies.json \
    --max-comments 2000

echo ""
echo "Done!"

