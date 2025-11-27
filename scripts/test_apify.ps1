# Quick test script for Apify integration (PowerShell)

Write-Host "Testing Apify Live Scraping..." -ForegroundColor Cyan
Write-Host ""

# Test with the provided post URL
python cli.py apify-scrape `
    --urls https://www.instagram.com/p/DRSmMhODnJ2/ `
    --cookies data/apify_cookies.json `
    --max-comments 2000

Write-Host ""
Write-Host "Done!" -ForegroundColor Green

