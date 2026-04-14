#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export LOST_WORLD_STATIC="$ROOT/frontend/dist"
export PYTHONPATH="$ROOT"
cd "$ROOT/backend"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
