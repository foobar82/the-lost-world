#!/usr/bin/env bash
set -euo pipefail

# The Lost World Plateau — deployment script
# Builds the React frontend and serves everything via FastAPI on port 8000.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"
STATIC_DIR="$BACKEND_DIR/static"

echo "=== The Lost World Plateau — Deploy ==="
echo ""

# 1. Install frontend dependencies
echo "[1/4] Installing frontend dependencies..."
cd "$FRONTEND_DIR"
npm install --silent

# 2. Build the frontend
echo "[2/4] Building frontend..."
npm run build

# 3. Copy build output to backend static directory
echo "[3/4] Copying build to backend/static..."
rm -rf "$STATIC_DIR"
cp -r "$FRONTEND_DIR/dist" "$STATIC_DIR"

# 4. Install backend dependencies
echo "[4/4] Installing backend dependencies..."
cd "$BACKEND_DIR"
pip install -q -r requirements.txt

echo ""
echo "=== Build complete ==="
echo ""
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop."
echo ""

# Start the server
cd "$BACKEND_DIR"
python -m uvicorn main:app --host 0.0.0.0 --port 8000
