@echo off
title ClimbUP - Local Admin Video Ingestion Engine
cd /d "%~dp0"
echo ===================================================================
echo     ClimbUP AI - Local Admin Ingestion ^& Course Management
echo ===================================================================
echo [1/2] Checking Python environment...
python -c "import fastapi, uvicorn; print('Python dependencies verified!')"
if %ERRORLEVEL% NEQ 0 (
    echo Installing missing requirements...
    pip install -r requirements.txt
)

echo.
echo [2/2] Starting local ingestion server on http://127.0.0.1:8000 ...
echo - All 2GB+ video downloads ^& FFmpeg processing will run on THIS PC.
echo - Results ^& embeddings will automatically sync to Supabase Cloud!
echo - Cloud Run will stay 100%% lightweight with ZERO heavy load.
echo.
echo Admin Portal URL: http://127.0.0.1:8000
echo.
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
pause
