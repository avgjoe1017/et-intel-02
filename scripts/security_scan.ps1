# Security scanning script for ET Intelligence system (Windows PowerShell)

Write-Host "Running security scans..." -ForegroundColor Cyan

# Check for security vulnerabilities in dependencies
Write-Host "Checking dependencies for vulnerabilities..." -ForegroundColor Yellow
if (Get-Command safety -ErrorAction SilentlyContinue) {
    safety check --json 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] No known vulnerabilities found" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Some vulnerabilities detected" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [WARN] 'safety' not installed. Install with: pip install safety" -ForegroundColor Yellow
}

# Check for known security issues
Write-Host "Checking for common security issues..." -ForegroundColor Yellow

# Check for hardcoded secrets
Write-Host "  - Checking for hardcoded secrets..." -ForegroundColor White
$passwordPattern = "password\s*=\s*['`"][^ENV]"
$passwordMatches = Get-ChildItem -Recurse -Include *.py | Select-String -Pattern $passwordPattern | Where-Object { $_.Line -notmatch "#.*password" -and $_.Line -notmatch "test" } | Select-Object -First 5
if ($passwordMatches) {
    Write-Host "    [WARN] Potential hardcoded passwords found" -ForegroundColor Yellow
    $passwordMatches | ForEach-Object { Write-Host "      $($_.Filename):$($_.LineNumber)" -ForegroundColor Gray }
} else {
    Write-Host "    [OK] No obvious hardcoded passwords" -ForegroundColor Green
}

# Check for SQL injection risks (basic check)
Write-Host "  - Checking for SQL injection risks..." -ForegroundColor White
$sqlMatches = Get-ChildItem -Recurse -Include *.py | Select-String -Pattern "execute.*%" | Where-Object { $_.Line -notmatch "test" } | Select-Object -First 5
if ($sqlMatches) {
    Write-Host "    [WARN] Potential SQL injection risks (string formatting in queries)" -ForegroundColor Yellow
    $sqlMatches | ForEach-Object { Write-Host "      $($_.Filename):$($_.LineNumber)" -ForegroundColor Gray }
} else {
    Write-Host "    [OK] No obvious SQL injection patterns" -ForegroundColor Green
}

# Check for exposed API keys
Write-Host "  - Checking for exposed API keys..." -ForegroundColor White
$apiKeyPattern = "api[_-]key\s*=\s*['`"][^ENV]"
$apiKeyMatches = Get-ChildItem -Recurse -Include *.py | Select-String -Pattern $apiKeyPattern | Where-Object { $_.Line -notmatch "test" } | Select-Object -First 5
if ($apiKeyMatches) {
    Write-Host "    [WARN] Potential exposed API keys found" -ForegroundColor Yellow
    $apiKeyMatches | ForEach-Object { Write-Host "      $($_.Filename):$($_.LineNumber)" -ForegroundColor Gray }
} else {
    Write-Host "    [OK] No obvious exposed API keys" -ForegroundColor Green
}

# Check file permissions
Write-Host "  - Checking for sensitive files..." -ForegroundColor White
$sensitiveFiles = Get-ChildItem -Recurse -Include *.env,*.key,*.pem -ErrorAction SilentlyContinue | Select-Object -First 5
if ($sensitiveFiles) {
    Write-Host "    [WARN] Sensitive files found - ensure proper permissions" -ForegroundColor Yellow
    $sensitiveFiles | ForEach-Object { Write-Host "      $($_.FullName)" -ForegroundColor Gray }
} else {
    Write-Host "    [OK] No obvious sensitive files in repo" -ForegroundColor Green
}

Write-Host "[OK] Security scan complete" -ForegroundColor Green
