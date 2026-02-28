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

export LOST_WORLD_STATIC="$REPO_ROOT/frontend/dist"

# Write PID file so scripts/deploy.sh can find and restart the server.
echo $$ > "$REPO_ROOT/backend/uvicorn.pid"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
