#!/usr/bin/env bash
# deploy.sh — Build the frontend and start the production server.
# Run from the repository root.
#
# Usage:
#   ./deploy.sh          # Build and start on port 8000
#   PORT=9000 ./deploy.sh  # Build and start on a custom port

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8000}"

echo "=== The Lost World Plateau — Production Deploy ==="

# 1. Build the React frontend
echo ""
echo "--- Building frontend ---"
cd "$SCRIPT_DIR/frontend"
npm install --production=false
npm run build
echo "Frontend built to frontend/dist/"

# 2. Set up Python venv if needed
echo ""
echo "--- Preparing backend ---"
cd "$SCRIPT_DIR/backend"
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

# 3. Start the server
echo ""
echo "--- Starting server on port $PORT ---"
echo "The app will be available at http://localhost:$PORT"
echo "Point your Cloudflare Tunnel at this address."
echo ""
uvicorn main:app --host 0.0.0.0 --port "$PORT"
