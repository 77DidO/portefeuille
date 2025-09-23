#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="${PYTHON:-python3}"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment in $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r "$ROOT_DIR/backend/requirements.txt"

pushd "$ROOT_DIR/frontend" >/dev/null
npm install
popd >/dev/null

echo "Starting backend (uvicorn) and frontend (Next.js). Press Ctrl+C to stop both services."

cleanup() {
  trap - INT TERM EXIT
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

pushd "$ROOT_DIR/backend" >/dev/null
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
popd >/dev/null

pushd "$ROOT_DIR/frontend" >/dev/null
if [ -n "${NEXT_PUBLIC_API_BASE:-}" ]; then
  NEXT_PUBLIC_API_BASE="$NEXT_PUBLIC_API_BASE" npm run dev &
else
  npm run dev &
fi
FRONTEND_PID=$!
popd >/dev/null

wait "$BACKEND_PID" "$FRONTEND_PID"
