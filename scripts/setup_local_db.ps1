# Setup Local PostgreSQL Database for ET Intelligence
# Run this script to create the database and user

Write-Host "=== Setting up Local PostgreSQL Database ===" -ForegroundColor Cyan
Write-Host ""

# You'll need to know your postgres password
$postgresPassword = Read-Host "Enter your postgres user password"
$newPassword = Read-Host "Enter password for et_intel_user (or press Enter for 'simplepass123')"

if ([string]::IsNullOrWhiteSpace($newPassword)) {
    $newPassword = "simplepass123"
}

Write-Host ""
Write-Host "Creating database and user..." -ForegroundColor Yellow

# SQL commands to run
$sql = @"
CREATE DATABASE et_intel;
CREATE USER et_intel_user WITH PASSWORD '$newPassword';
GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;
"@

# Connect and run SQL
$env:PGPASSWORD = $postgresPassword
$sql | psql -U postgres

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Database and user created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Update your .env file with:" -ForegroundColor Cyan
    Write-Host "DATABASE_URL=postgresql://et_intel_user:$newPassword@localhost:5432/et_intel" -ForegroundColor White
    Write-Host ""
    Write-Host "Then run: python cli.py init" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "✗ Error creating database. You may need to run this manually." -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual SQL commands:" -ForegroundColor Cyan
    Write-Host $sql -ForegroundColor White
}

