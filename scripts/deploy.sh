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

# Restart the backend server using a PID file to track the process.
PID_FILE="$REPO_ROOT/backend/uvicorn.pid"
LOG_FILE="$REPO_ROOT/backend/uvicorn.log"

echo "=== Restarting server ==="

# Stop existing server if running.
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "  Stopping existing server (PID $OLD_PID)..."
        kill "$OLD_PID"
        # Wait up to 5 seconds for graceful shutdown.
        for _ in 1 2 3 4 5; do
            kill -0 "$OLD_PID" 2>/dev/null || break
            sleep 1
        done
        # Force kill if still running.
        if kill -0 "$OLD_PID" 2>/dev/null; then
            echo "  Force-killing server (PID $OLD_PID)..."
            kill -9 "$OLD_PID"
        fi
    fi
    rm -f "$PID_FILE"
fi

# Activate venv if not already active.
cd "$REPO_ROOT/backend"
if [ -z "${VIRTUAL_ENV:-}" ]; then
    source venv/bin/activate
fi

# Start server in the background.
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
echo "  Server started (PID $NEW_PID)"

# Wait briefly and verify the server is responding.
sleep 2
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "  Health check passed"
else
    echo "  WARNING: Health check failed — server may not have started correctly"
    echo "  Check logs: $LOG_FILE"
    exit 1
fi

echo ""
echo "=== Deployment complete ==="
