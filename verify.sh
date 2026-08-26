#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "AI Company OS - Phase 7D Deployment Verification"

if [ ! -x ".venv/bin/python" ]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
  if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Python 3.12+ not found."
    exit 1
  fi
  echo "[INFO] Creating .venv..."
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python scripts/verify_deployment.py --install-deps "$@"
