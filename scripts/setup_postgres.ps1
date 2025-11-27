# PostgreSQL Setup Script for ET Intelligence
# This script helps you create/reset the database and user

Write-Host "=== PostgreSQL Setup for ET Intelligence ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check PostgreSQL service
Write-Host "Step 1: Checking PostgreSQL service..." -ForegroundColor Yellow
$service = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
if ($service) {
    Write-Host "✓ PostgreSQL service found: $($service.Name)" -ForegroundColor Green
    if ($service.Status -ne "Running") {
        Write-Host "Starting PostgreSQL service..." -ForegroundColor Yellow
        Start-Service $service.Name
    }
} else {
    Write-Host "✗ PostgreSQL service not found. Please install PostgreSQL first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 2: Database Setup Options" -ForegroundColor Yellow
Write-Host ""
Write-Host "Choose an option:" -ForegroundColor Cyan
Write-Host "1. I know my postgres password - create database and user"
Write-Host "2. I forgot my password - reset postgres password (requires admin)"
Write-Host "3. Use Docker instead (recommended - easier)"
Write-Host ""
$choice = Read-Host "Enter choice (1-3)"

if ($choice -eq "1") {
    Write-Host ""
    Write-Host "Enter your postgres password when prompted:" -ForegroundColor Yellow
    
    $newPassword = Read-Host "Enter password for et_intel_user (or press Enter to skip creating user)"
    
    if ($newPassword) {
        Write-Host ""
        Write-Host "Creating database and user..." -ForegroundColor Yellow
        
        # SQL commands
        $createDb = "CREATE DATABASE et_intel;"
        $createUser = "CREATE USER et_intel_user WITH PASSWORD '$newPassword';"
        $grantPrivs = "GRANT ALL PRIVILEGES ON DATABASE et_intel TO et_intel_user;"
        
        Write-Host ""
        Write-Host "Run these commands in psql:" -ForegroundColor Cyan
        Write-Host "psql -U postgres" -ForegroundColor White
        Write-Host ""
        Write-Host "$createDb" -ForegroundColor White
        Write-Host "$createUser" -ForegroundColor White
        Write-Host "$grantPrivs" -ForegroundColor White
        Write-Host "\q" -ForegroundColor White
        Write-Host ""
        
        $runNow = Read-Host "Run these commands now? (y/n)"
        if ($runNow -eq "y") {
            $env:PGPASSWORD = Read-Host "Enter postgres password"
            psql -U postgres -c $createDb
            psql -U postgres -c $createUser
            psql -U postgres -c $grantPrivs
            
            Write-Host ""
            Write-Host "✓ Database created!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Add this to your .env file:" -ForegroundColor Cyan
            Write-Host "DATABASE_URL=postgresql://et_intel_user:$newPassword@localhost:5432/et_intel" -ForegroundColor White
        }
    }
}
elseif ($choice -eq "2") {
    Write-Host ""
    Write-Host "⚠️  Resetting password requires:" -ForegroundColor Yellow
    Write-Host "1. Administrator privileges"
    Write-Host "2. Temporarily modifying pg_hba.conf"
    Write-Host "3. Restarting PostgreSQL service"
    Write-Host ""
    Write-Host "See MD_DOCS/FIND_POSTGRES_PASSWORD.md for detailed instructions" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Or use Option 3 (Docker) which is easier!" -ForegroundColor Green
}
elseif ($choice -eq "3") {
    Write-Host ""
    Write-Host "Using Docker Compose for PostgreSQL..." -ForegroundColor Yellow
    Write-Host ""
    
    $password = Read-Host "Enter password for PostgreSQL (will be saved to .env)"
    
    # Add to .env file
    $envContent = @"
# Database Configuration
DATABASE_URL=postgresql://et_intel_user:$password@localhost:5432/et_intel

# PostgreSQL Password for Docker
POSTGRES_PASSWORD=$password
"@
    
    Write-Host ""
    Write-Host "Add these lines to your .env file:" -ForegroundColor Cyan
    Write-Host $envContent -ForegroundColor White
    Write-Host ""
    
    $addToEnv = Read-Host "Add these to .env automatically? (y/n)"
    if ($addToEnv -eq "y") {
        if (Test-Path .env) {
            Add-Content -Path .env -Value "`n# PostgreSQL Password for Docker`nPOSTGRES_PASSWORD=$password"
            Write-Host "✓ Added POSTGRES_PASSWORD to .env" -ForegroundColor Green
        } else {
            Set-Content -Path .env -Value $envContent
            Write-Host "✓ Created .env file" -ForegroundColor Green
        }
    }
    
    Write-Host ""
    Write-Host "Start PostgreSQL with Docker:" -ForegroundColor Cyan
    Write-Host "docker-compose up -d postgres" -ForegroundColor White
    Write-Host ""
    Write-Host "Then initialize the database:" -ForegroundColor Cyan
    Write-Host "python cli.py init" -ForegroundColor White
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green

