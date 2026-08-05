@echo off
REM Start v3 backend server (FastAPI + Uvicorn) on port 8000
REM Usage: scripts\start_backend.bat
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
python -m uvicorn src.backend.http.app:app --host 0.0.0.0 --port 8000 --reload
