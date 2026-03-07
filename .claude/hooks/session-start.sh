#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "=== Session Start: Installing dependencies ==="

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# Install frontend dependencies
echo "--- Installing frontend npm dependencies ---"
cd "$REPO_ROOT/frontend"
npm install

# Install backend Python dependencies
echo "--- Installing backend Python dependencies ---"
cd "$REPO_ROOT/backend"
pip install -q -r requirements.txt

# Install pytest (not in requirements.txt)
echo "--- Installing pytest ---"
pip install -q pytest pytest-asyncio httpx

# Ensure root-level node_modules symlink for vitest to resolve packages
if [ ! -e "$REPO_ROOT/node_modules" ]; then
  ln -sf frontend/node_modules "$REPO_ROOT/node_modules"
fi

echo "=== Dependencies installed successfully ==="
