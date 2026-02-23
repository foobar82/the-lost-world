#!/usr/bin/env bash
set -e

# Resolve the repo root relative to this script, so it works from any working directory.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Step 1/6: Frontend Lint ==="
cd "$REPO_ROOT/frontend" && npx eslint src/

echo "=== Step 2/6: TypeScript Check ==="
cd "$REPO_ROOT/frontend" && npx tsc --noEmit

echo "=== Step 3/6: Backend Lint ==="
cd "$REPO_ROOT/backend" && ruff check .

echo "=== Step 4/6: Frontend Tests ==="
cd "$REPO_ROOT/frontend" && npx vitest run

echo "=== Step 5/6: Backend Tests ==="
cd "$REPO_ROOT/backend" && python -m pytest "$REPO_ROOT/tests/backend/" -q

echo "=== Step 6/6: Build Frontend ==="
cd "$REPO_ROOT/frontend" && npm run build

echo ""
echo "=== All checks passed ==="
