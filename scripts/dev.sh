#!/usr/bin/env bash
# Starts backend (8000) and frontend (5173). Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=$(command -v python3.11 || command -v python3.12 || command -v python3.13 || command -v python3)
export PATH="/opt/homebrew/bin:$PATH"   # Homebrew's Node 18+ ahead of an older nvm default on macOS

if [ ! -d backend/.venv ]; then
  echo "→ creating backend virtualenv with $($PY --version)"
  "$PY" -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules ]; then
  echo "→ installing frontend packages (node $(node --version))"
  (cd frontend && npm install --no-audit --no-fund)
fi

echo "→ API  http://127.0.0.1:8000/docs"
(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT
echo "→ App  http://localhost:5173"
(cd frontend && npm run dev)
