#!/usr/bin/env bash
# ============================================
#   AI Company OS v1.5.0
#   Multi-Agent Operating System
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "============================================"
echo "  AI Company OS v1.5.0"
echo "  Multi-Agent Operating System"
echo "============================================"
echo ""

# 1. Check Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[ERROR] Python not found!"
    echo ""
    echo "Please install Python 3.10+ from:"
    echo "https://www.python.org/downloads/"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)
echo "[OK] Python found: $($PYTHON --version)"

# 2. Create virtual environment if not exists
if [ ! -f ".venv/bin/python" ]; then
    echo "[INFO] Creating virtual environment..."
    $PYTHON -m venv .venv
    echo "[OK] Virtual environment created"
else
    echo "[OK] Virtual environment exists"
fi

source .venv/bin/activate
echo "[OK] Virtual environment activated"

# 3. Upgrade pip
echo "[INFO] Upgrading pip..."
pip install --upgrade pip -q

# 4. Install dependencies
echo "[INFO] Installing dependencies..."
pip install -r requirements.txt -q
echo "[OK] Dependencies installed"

# 5. Check Playwright browser
if ! python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.launch(); p.stop()" &>/dev/null; then
    echo "[INFO] Installing Playwright Chromium..."
    playwright install chromium
fi
echo "[OK] Playwright ready"

# 6. Build React frontend
if ! command -v npm &>/dev/null; then
    echo "[ERROR] npm not found. Install Node.js 20.19+ or 22.12+."
    exit 1
fi
echo "[INFO] Preparing frontend..."
pushd frontend-new >/dev/null
if [ ! -d "node_modules" ]; then
    npm ci
fi
npm run build
popd >/dev/null
echo "[OK] Frontend production build ready"

# 7. Create .env if not exists
if [ ! -f ".env" ]; then
    echo "[INFO] Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "[IMPORTANT] Please edit .env file and add your API Key!"
    echo ""
    echo "Supported providers:"
    echo "  - DeepSeek: https://platform.deepseek.com"
    echo "  - OpenAI:   https://platform.openai.com"
    echo "  - Claude:   https://console.anthropic.com"
    echo ""
fi

# 8. Start server
echo ""
echo "============================================"
echo "  Starting server..."
echo "  URL: http://localhost:8000/app"
echo "  API: http://localhost:8000/docs"
echo "============================================"
echo ""

python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
