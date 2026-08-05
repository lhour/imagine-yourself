@echo off
setlocal
set "NODE_DIR="
if exist "%USERPROFILE%\.fnm\aliases\default\node.exe" set "NODE_DIR=%USERPROFILE%\.fnm\aliases\default"
if exist "C:\Program Files\nodejs\node.exe" set "NODE_DIR=C:\Program Files\nodejs"
if not defined NODE_DIR goto :no_node
set "PATH=%NODE_DIR%;%PATH%"
cd /d "%~dp0\..\frontend"
echo [Frontend] Node: %NODE_DIR%
echo [Frontend] Starting Vite dev server at http://localhost:5173 ...
call npx vite
goto :eof

:no_node
echo [ERROR] Node.js not found. Please install Node.js v20+ or use fnm.
exit /b 1
