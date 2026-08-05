@echo off
REM Start v3 backend server (FastAPI + Uvicorn) on port 8000
REM Usage: scripts\start_backend.bat
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
REM --reload-dir src/backend: 把监听范围收窄到后端源码，
REM 避免 saves/*.db 与 logs/*.log 写入触发全项目重载、杀掉进行中的长请求。
python -m uvicorn src.backend.http.app:app --host 0.0.0.0 --port 8000 --reload --reload-dir src/backend
