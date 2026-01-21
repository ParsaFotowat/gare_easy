@echo off
REM Quick start script for single MEF scrape

echo Running MEF Scraper (once)...
echo.

REM Activate environment if exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Run scraper once
python main.py --platform mef --mode once

echo.
echo Scraping complete! Run run_dashboard.bat to view results.
pause
