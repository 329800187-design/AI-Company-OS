@echo off
chcp 65001 >nul
title AI Company OS v1.5.0

echo.
echo ============================================
echo   AI Company OS - Multi-Agent System
echo   Version 1.5.0
echo ============================================
echo.

cd /d "%~dp0"

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.10+ from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
echo [OK] Python found

:: 2. Create virtual environment if not exists
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment exists
)

:: 3. Activate virtual environment
call .venv\Scripts\activate.bat
echo [OK] Virtual environment activated

:: 4. Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip -q

:: 5. Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: 6. Install Playwright browser
echo [INFO] Checking Playwright browser...
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.launch(); p.stop()" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing Playwright Chromium...
    playwright install chromium
)
echo [OK] Playwright ready

:: 7. Build React frontend
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] npm not found. Install Node.js 20.19+ or 22.12+.
    pause
    exit /b 1
)
echo [INFO] Preparing frontend...
pushd frontend-new
if not exist "node_modules" (
    call npm ci
    if errorlevel 1 (
        popd
        echo [ERROR] Failed to install frontend dependencies!
        pause
        exit /b 1
    )
)
call npm run build
if errorlevel 1 (
    popd
    echo [ERROR] Frontend build failed!
    pause
    exit /b 1
)
popd
echo [OK] Frontend production build ready

:: 8. Create .env if not exists
if not exist ".env" (
    echo [INFO] Creating .env from template...
    copy .env.example .env >nul
    echo.
    echo [IMPORTANT] Please edit .env and set both AUTH_TOKEN and your API Key before starting.
    echo.
    echo Supported providers:
    echo   - DeepSeek: https://platform.deepseek.com
    echo   - OpenAI:   https://platform.openai.com
    echo   - Claude:   https://console.anthropic.com
    echo.
    echo [STOP] Authentication is enabled by default. Configure AUTH_TOKEN in .env, then run start.bat again.
    exit /b 1
)

:: 9. Start server
echo.
echo ============================================
echo   Starting server...
echo   URL: http://localhost:8000/app
echo   API: http://localhost:8000/docs
echo ============================================
echo.

:: 10. Open browser after 3 seconds
start /b cmd /c "timeout /t 3 >nul && start http://localhost:8000/app"

:: 11. Start uvicorn
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000

pause
