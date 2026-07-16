@echo off
chcp 65001 >nul
title AI Company OS - Build Desktop App

echo.
echo ============================================
echo   AI Company OS - Build Desktop App
echo ============================================
echo.

cd /d "%~dp0"

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)
echo [OK] Python found

:: 2. Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else (
    echo [WARN] No virtual environment found, using global Python
)

:: 3. Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt -q
pip install pyinstaller -q
echo [OK] Dependencies installed

:: 4. Build frontend
echo [INFO] Building frontend...
cd frontend-new
call npm run build
cd ..
echo [OK] Frontend built

:: 5. Copy frontend to backend
echo [INFO] Copying frontend files...
if exist "backend\static-new" rmdir /s /q "backend\static-new"
xcopy /E /I /Y "frontend-new\dist\*" "backend\static-new\" >nul
echo [OK] Frontend copied

:: 6. Build executable
echo [INFO] Building executable...
pyinstaller build.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build successful!
echo   Output: dist\AI-Company-OS.exe
echo ============================================
echo.

pause
