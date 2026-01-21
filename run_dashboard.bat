@echo off
REM Quick start script for Gare Easy dashboard

echo Starting Gare Easy Dashboard...
echo.

REM Activate environment if exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Run Streamlit dashboard
python -m streamlit run streamlit_app/app.py --server.port 8501

pause
