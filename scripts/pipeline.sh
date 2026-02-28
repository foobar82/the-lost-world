#!/usr/bin/env bash
set -e

# Resolve the repo root relative to this script, so it works from any working directory.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Ensure a root-level node_modules symlink exists so that vitest can resolve
# packages (react, @testing-library, etc.) from test files outside frontend/.
if [ ! -e "$REPO_ROOT/node_modules" ]; then
  ln -sf frontend/node_modules "$REPO_ROOT/node_modules"
fi

echo "=== Step 1/9: Frontend Lint ==="
cd "$REPO_ROOT/frontend" && npx eslint src/

echo "=== Step 2/9: TypeScript Check ==="
cd "$REPO_ROOT/frontend" && npx tsc -b --noEmit

echo "=== Step 3/9: Backend Lint ==="
cd "$REPO_ROOT/backend" && ruff check .

echo "=== Step 4/9: Essential Tests (Frontend) ==="
cd "$REPO_ROOT/frontend" && npx vitest run ../tests/essential/

echo "=== Step 5/9: Essential Tests (Backend) ==="
cd "$REPO_ROOT/backend" && python -m pytest "$REPO_ROOT/tests/essential/" -q

echo "=== Step 6/9: Frontend Tests ==="
cd "$REPO_ROOT/frontend" && npx vitest run ../tests/frontend/

echo "=== Step 7/9: Backend Tests ==="
cd "$REPO_ROOT/backend" && python -m pytest "$REPO_ROOT/tests/backend/" -q

echo "=== Step 8/9: Pipeline Tests ==="
cd "$REPO_ROOT" && python -m pytest tests/pipeline/ -q

echo "=== Step 9/9: Build Frontend ==="
cd "$REPO_ROOT/frontend" && npm run build

echo ""
echo "=== All checks passed ==="
