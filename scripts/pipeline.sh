#!/usr/bin/env bash
set -e

# Resolve the repo root relative to this script, so it works from any working directory.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Step 1/7: Frontend Lint ==="
cd "$REPO_ROOT/frontend" && npx eslint src/

echo "=== Step 2/7: TypeScript Check ==="
cd "$REPO_ROOT/frontend" && npx tsc -b --noEmit

echo "=== Step 3/7: Backend Lint ==="
cd "$REPO_ROOT/backend" && ruff check .

echo "=== Step 4/7: Frontend Tests ==="
cd "$REPO_ROOT/frontend" && npx vitest run

echo "=== Step 5/7: Backend Tests ==="
cd "$REPO_ROOT/backend" && python -m pytest "$REPO_ROOT/tests/backend/" -q

echo "=== Step 6/7: Pipeline Tests ==="
cd "$REPO_ROOT" && python -m pytest tests/pipeline/ -q

echo "=== Step 7/7: Build Frontend ==="
cd "$REPO_ROOT/frontend" && npm run build

echo ""
echo "=== All checks passed ==="
