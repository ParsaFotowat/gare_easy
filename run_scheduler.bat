@echo off
REM Quick start script for Gare Easy scheduler

echo Starting Gare Easy Scheduler (6-hour automatic updates)...
echo.

REM Activate environment if exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Run scheduler
python main.py --mode schedule --platform mef

pause
