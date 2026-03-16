#!/usr/bin/env bash
# Run each test suite with timing and record durations to metrics/test_timing.jsonl.
# Runs tests independently from pipeline.sh so suites can be measured in isolation.
#
# Usage:
#   bash scripts/metrics/test_timing.sh
#   SUITES=frontend,backend bash scripts/metrics/test_timing.sh  # run specific suites only
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
METRICS_FILE="$REPO_ROOT/metrics/test_timing.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Which suites to run: comma-separated from env, or all by default.
ALL_SUITES="essential-frontend,essential-backend,frontend,backend,pipeline"
SUITES="${SUITES:-$ALL_SUITES}"

# Ensure node_modules symlink exists (same logic as pipeline.sh).
if [ ! -e "$REPO_ROOT/node_modules" ]; then
    ln -sf frontend/node_modules "$REPO_ROOT/node_modules"
fi

# Helper: run a command, capture elapsed ms, passed/failed counts.
# Writes one JSONL line per suite.
run_suite() {
    local suite="$1"; shift
    local START END ELAPSED_MS EXIT_CODE
    local TMP_OUT
    TMP_OUT=$(mktemp /tmp/test_timing_XXXXXX.txt)
    trap 'rm -f "$TMP_OUT"' RETURN

    START=$(python3 -c "import time; print(int(time.time()*1000))")
    set +e
    "$@" > "$TMP_OUT" 2>&1
    EXIT_CODE=$?
    set -e
    END=$(python3 -c "import time; print(int(time.time()*1000))")
    ELAPSED_MS=$((END - START))

    # Parse pass/fail counts from output.
    python3 - "$TMP_OUT" "$suite" "$ELAPSED_MS" "$EXIT_CODE" "$TIMESTAMP" <<'PYEOF' >> "$METRICS_FILE"
import json, sys, re

out_file, suite, elapsed_ms, exit_code, timestamp = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
with open(out_file) as f:
    output = f.read()

passed = failed = skipped = None

# pytest summary: "X passed, Y failed" or "X passed"
m = re.search(r"(\d+) passed", output)
if m:
    passed = int(m.group(1))
m = re.search(r"(\d+) failed", output)
if m:
    failed = int(m.group(1))
m = re.search(r"(\d+) skipped", output)
if m:
    skipped = int(m.group(1))

# vitest summary: "X tests passed" or "Tests X passed"
if passed is None:
    m = re.search(r"(\d+)\s+passed", output, re.IGNORECASE)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", output, re.IGNORECASE)
    if m:
        failed = int(m.group(1))

record = {
    "timestamp": timestamp,
    "suite": suite,
    "duration_ms": elapsed_ms,
    "passed": passed,
    "failed": failed,
    "skipped": skipped,
    "exit_code": exit_code,
}
print(json.dumps(record))
PYEOF

    echo "  $suite: ${ELAPSED_MS}ms (exit $EXIT_CODE)"
}

echo "Timing test suites: $SUITES"

IFS=',' read -ra SUITE_LIST <<< "$SUITES"
for suite in "${SUITE_LIST[@]}"; do
    case "$suite" in
        essential-frontend)
            run_suite "essential-frontend" \
                bash -c "cd '$REPO_ROOT/frontend' && npx vitest run ../tests/essential/"
            ;;
        essential-backend)
            run_suite "essential-backend" \
                bash -c "cd '$REPO_ROOT/backend' && source venv/bin/activate 2>/dev/null || true && python -m pytest '$REPO_ROOT/tests/essential/' -q"
            ;;
        frontend)
            run_suite "frontend" \
                bash -c "cd '$REPO_ROOT/frontend' && npx vitest run ../tests/frontend/"
            ;;
        backend)
            run_suite "backend" \
                bash -c "cd '$REPO_ROOT/backend' && source venv/bin/activate 2>/dev/null || true && python -m pytest '$REPO_ROOT/tests/backend/' -q"
            ;;
        pipeline)
            run_suite "pipeline" \
                bash -c "cd '$REPO_ROOT' && source backend/venv/bin/activate 2>/dev/null || true && python -m pytest tests/pipeline/ -q"
            ;;
        *)
            echo "WARNING: Unknown suite '$suite', skipping." >&2
            ;;
    esac
done

echo "Test timing recorded → $METRICS_FILE"
