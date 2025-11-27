# Complete PostgreSQL Setup from Scratch
# This script helps you create a fresh database and user for ET Intelligence

Write-Host "=== PostgreSQL Setup from Scratch ===" -ForegroundColor Cyan
Write-Host ""

# Find PostgreSQL installation
$pgVersions = @("17", "16", "15", "14")
$pgPath = $null
$pgVersion = $null

foreach ($ver in $pgVersions) {
    $testPath = "C:\Program Files\PostgreSQL\$ver\data\pg_hba.conf"
    if (Test-Path $testPath) {
        $pgPath = $testPath
        $pgVersion = $ver
        break
    }
}

if (-not $pgPath) {
    Write-Host "✗ Could not find PostgreSQL installation" -ForegroundColor Red
    Write-Host "Please install PostgreSQL from https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Found PostgreSQL $pgVersion" -ForegroundColor Green
Write-Host "  Data directory: $(Split-Path $pgPath)" -ForegroundColor Gray
Write-Host ""

# Step 1: Backup pg_hba.conf
Write-Host "Step 1: Backing up pg_hba.conf..." -ForegroundColor Yellow
$backupPath = "$pgPath.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
Copy-Item $pgPath $backupPath
Write-Host "✓ Backup created: $backupPath" -ForegroundColor Green
Write-Host ""

# Step 2: Temporarily enable trust authentication
Write-Host "Step 2: Temporarily enabling passwordless authentication..." -ForegroundColor Yellow
$pgHbaContent = Get-Content $pgPath

# Check if already has trust
if ($pgHbaContent -match "host\s+all\s+all\s+127\.0\.0\.1/32\s+trust") {
    Write-Host "✓ Trust authentication already enabled" -ForegroundColor Green
} else {
    # Add trust for localhost
    $newContent = @()
    $foundLocalhost = $false
    
    foreach ($line in $pgHbaContent) {
        if ($line -match "host\s+all\s+all\s+127\.0\.0\.1/32") {
            # Replace md5/scram-sha-256 with trust
            $newLine = $line -replace "(md5|scram-sha-256|password)", "trust"
            $newContent += $newLine
            $foundLocalhost = $true
        } elseif ($line -match "host\s+all\s+all\s+::1/128") {
            $newLine = $line -replace "(md5|scram-sha-256|password)", "trust"
            $newContent += $newLine
        } else {
            $newContent += $line
        }
    }
    
    if (-not $foundLocalhost) {
        # Add trust lines if not found
        $newContent += "host    all             all             127.0.0.1/32            trust"
        $newContent += "host    all             all             ::1/128                 trust"
    }
    
    Set-Content -Path $pgPath -Value $newContent
    Write-Host "✓ Modified pg_hba.conf to enable trust authentication" -ForegroundColor Green
}
Write-Host ""

# Step 3: Restart PostgreSQL
Write-Host "Step 3: Restarting PostgreSQL service..." -ForegroundColor Yellow
$serviceName = "postgresql-x64-$pgVersion"
try {
    Restart-Service $serviceName -Force -ErrorAction Stop
    Start-Sleep -Seconds 3
    Write-Host "✓ PostgreSQL service restarted" -ForegroundColor Green
} catch {
    Write-Host "✗ Error restarting service. You may need to run as Administrator." -ForegroundColor Red
    Write-Host "  Run this command as Admin: Restart-Service $serviceName" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Step 4: Get password for new user
Write-Host "Step 4: Database setup" -ForegroundColor Yellow
$dbPassword = Read-Host "Enter password for et_intel_user (default: simplepass123)"
if ([string]::IsNullOrWhiteSpace($dbPassword)) {
    $dbPassword = "simplepass123"
}

Write-Host ""
Write-Host "Creating database and user..." -ForegroundColor Yellow

# SQL commands
$createDbSql = "CREATE DATABASE et_intel;"
$createUserSql = "CREATE USER et_intel_user WITH PASSWORD '$dbPassword';"
$grantSql = "GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;"

# Check if database exists
$dbExists = psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='et_intel'" 2>$null
if ($dbExists -eq "1") {
    Write-Host "⚠ Database 'et_intel' already exists" -ForegroundColor Yellow
    $recreate = Read-Host "Drop and recreate? (y/n)"
    if ($recreate -eq "y") {
        psql -U postgres -c "DROP DATABASE IF EXISTS et_intel;" 2>$null
        psql -U postgres -c "DROP USER IF EXISTS et_intel_user;" 2>$null
    }
}

# Create database and user
Write-Host "  Creating database..." -ForegroundColor Gray
$result1 = psql -U postgres -c $createDbSql 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Error creating database: $result1" -ForegroundColor Red
} else {
    Write-Host "  ✓ Database created" -ForegroundColor Green
}

Write-Host "  Creating user..." -ForegroundColor Gray
$result2 = psql -U postgres -c $createUserSql 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Error creating user: $result2" -ForegroundColor Red
} else {
    Write-Host "  ✓ User created" -ForegroundColor Green
}

Write-Host "  Granting privileges..." -ForegroundColor Gray
$result3 = psql -U postgres -c $grantSql 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Error granting privileges: $result3" -ForegroundColor Red
} else {
    Write-Host "  ✓ Privileges granted" -ForegroundColor Green
}
Write-Host ""

# Step 5: Restore secure authentication
Write-Host "Step 5: Restoring secure authentication..." -ForegroundColor Yellow
$finalContent = Get-Content $pgPath

$restoredContent = @()
foreach ($line in $finalContent) {
    if ($line -match "host\s+all\s+all\s+127\.0\.0\.1/32\s+trust") {
        $restoredContent += $line -replace "trust", "md5"
    } elseif ($line -match "host\s+all\s+all\s+::1/128\s+trust") {
        $restoredContent += $line -replace "trust", "md5"
    } else {
        $restoredContent += $line
    }
}

Set-Content -Path $pgPath -Value $restoredContent
Restart-Service $serviceName -Force
Start-Sleep -Seconds 2
Write-Host "✓ Authentication restored to md5" -ForegroundColor Green
Write-Host ""

# Step 6: Test connection
Write-Host "Step 6: Testing connection..." -ForegroundColor Yellow
$env:PGPASSWORD = $dbPassword
$testResult = psql -U et_intel_user -d et_intel -c "SELECT current_user, current_database();" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Connection successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "=== Setup Complete! ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Update your .env file with:" -ForegroundColor Cyan
    Write-Host "DATABASE_URL=postgresql://et_intel_user:$dbPassword@localhost:5432/et_intel" -ForegroundColor White
    Write-Host ""
    Write-Host "Then run:" -ForegroundColor Cyan
    Write-Host "  python cli.py init" -ForegroundColor White
    Write-Host "  python cli.py status" -ForegroundColor White
} else {
    Write-Host "✗ Connection test failed" -ForegroundColor Red
    Write-Host "Error: $testResult" -ForegroundColor Red
}

