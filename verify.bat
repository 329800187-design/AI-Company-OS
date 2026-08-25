@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo AI Company OS - Phase 7D Deployment Verification

if not exist ".venv\Scripts\python.exe" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python 3.12+ not found.
        exit /b 1
    )
    echo [INFO] Creating .venv...
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" scripts\verify_deployment.py --install-deps %*
exit /b %errorlevel%
