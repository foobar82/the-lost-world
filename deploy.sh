#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== Building frontend ==="
cd "$REPO_ROOT/frontend"
npm ci --silent
npm run build

echo "=== Starting production server ==="
cd "$REPO_ROOT/backend"

# Activate venv if not already active
if [ -z "${VIRTUAL_ENV:-}" ]; then
  source venv/bin/activate
fi

# ChromaDB requires Python <=3.13 (Pydantic V1 is incompatible with 3.14+).
py_minor=$(python -c 'import sys; print(sys.version_info.minor)')
if [ "$py_minor" -ge 14 ]; then
  echo "ERROR: Python 3.14+ detected. ChromaDB requires Python <=3.13." >&2
  echo "Recreate the venv with: python3.13 -m venv venv" >&2
  exit 1
fi

export LOST_WORLD_STATIC="$REPO_ROOT/frontend/dist"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

# Write PID file so scripts/deploy.sh can find and restart the server.
echo $$ > "$REPO_ROOT/backend/uvicorn.pid"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
