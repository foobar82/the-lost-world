#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Running pipeline ==="
"$REPO_ROOT/scripts/pipeline.sh"

echo ""
echo "=== Deploying ==="

# Point FastAPI at the freshly-built frontend bundle.
export LOST_WORLD_STATIC="$REPO_ROOT/frontend/dist"

echo "LOST_WORLD_STATIC=$LOST_WORLD_STATIC"

# Restart the backend server.
# TODO: Replace with the actual restart mechanism (systemd, pm2, process manager, etc.)
echo "=== Restarting server (placeholder) ==="
echo "  To run manually:  cd $REPO_ROOT/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo ""
echo "=== Deployment complete ==="
