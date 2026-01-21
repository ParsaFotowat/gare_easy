# Gare Easy - Automated Setup Script
# Run this in PowerShell to set up the entire project

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Gare Easy - Setup Script" -ForegroundColor Cyan
Write-Host "  Public Procurement Tender Aggregator" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "[1/7] Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Please install Python 3.10 or higher." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Found: $pythonVersion" -ForegroundColor Green

# Create virtual environment
Write-Host ""
Write-Host "[2/7] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "  ℹ Virtual environment already exists, skipping..." -ForegroundColor Cyan
} else {
    python -m venv venv
    Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "[3/7] Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
Write-Host "  ✓ Virtual environment activated" -ForegroundColor Green

# Install requirements
Write-Host ""
Write-Host "[4/7] Installing Python dependencies..." -ForegroundColor Yellow
Write-Host "  This may take a few minutes..." -ForegroundColor Cyan
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Dependencies installed" -ForegroundColor Green

# Install Playwright browsers
Write-Host ""
Write-Host "[5/7] Installing Playwright browser..." -ForegroundColor Yellow
playwright install chromium --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Failed to install Playwright" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Playwright Chromium installed" -ForegroundColor Green

# Create directories
Write-Host ""
Write-Host "[6/7] Creating project directories..." -ForegroundColor Yellow
$dirs = @("data", "data/downloads", "logs")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  ✓ Created: $dir" -ForegroundColor Green
    } else {
        Write-Host "  ℹ Already exists: $dir" -ForegroundColor Cyan
    }
}

# Setup environment file
Write-Host ""
Write-Host "[7/7] Setting up environment configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  ✓ Created .env file from template" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ⚠ IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY" -ForegroundColor Yellow
    Write-Host "  Get your API key from: https://console.anthropic.com/settings/keys" -ForegroundColor Yellow
} else {
    Write-Host "  ℹ .env file already exists, skipping..." -ForegroundColor Cyan
}

# Initialize database
Write-Host ""
Write-Host "Initializing database..." -ForegroundColor Yellow
python main.py --init-db
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Failed to initialize database" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Database initialized" -ForegroundColor Green

# Success message
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup Complete! ✓" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Edit .env and add your Claude API key:" -ForegroundColor White
Write-Host "   notepad .env" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Run the scraper (MEF platform - 50 points):" -ForegroundColor White
Write-Host "   python main.py --platform mef" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Launch the dashboard:" -ForegroundColor White
Write-Host "   streamlit run streamlit_app/app.py" -ForegroundColor Gray
Write-Host ""
Write-Host "For detailed instructions, see:" -ForegroundColor White
Write-Host "   - QUICKSTART.md (Step-by-step guide)" -ForegroundColor Gray
Write-Host "   - STRATEGY.md (Implementation strategy)" -ForegroundColor Gray
Write-Host "   - README.md (Full documentation)" -ForegroundColor Gray
Write-Host ""
Write-Host "Good luck with your internship! 🚀" -ForegroundColor Green
Write-Host ""
