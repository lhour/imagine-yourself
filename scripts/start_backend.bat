@echo off
REM Start v3 backend server (FastAPI + Uvicorn) on port 8000
REM Usage: scripts\start_backend.bat
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
REM 优先使用 .venv 的 Python（sqlite_vec / kuzu 等依赖装在 venv 里，
REM 系统 Python 缺这些包会导致向量库/图库功能静默降级）
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
REM --reload-dir src/backend: 把监听范围收窄到后端源码，
REM 避免 saves/*.db 与 logs/*.log 写入触发全项目重载、杀掉进行中的长请求。
%PYTHON% -m uvicorn src.backend.http.app:app --host 0.0.0.0 --port 8000 --reload --reload-dir src/backend
