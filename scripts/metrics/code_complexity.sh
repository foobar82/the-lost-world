#!/usr/bin/env bash
# Collect code complexity metrics: file counts, line counts, cyclomatic complexity,
# and duplication percentage.
# Appends a JSONL record to metrics/code_complexity.jsonl.
#
# Requirements:
#   - radon (Python): pip install radon  — for cyclomatic complexity
#   - jscpd (Node):  npx jscpd          — for duplication (downloaded on first use via npx)
#
# Usage:
#   bash scripts/metrics/code_complexity.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
METRICS_FILE="$REPO_ROOT/metrics/code_complexity.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Activate Python venv if available.
if [ -f "$REPO_ROOT/backend/venv/bin/activate" ]; then
    source "$REPO_ROOT/backend/venv/bin/activate"
fi

# --- File & line counts ---
echo "Counting files and lines ..."

PY_FILES=$(find "$REPO_ROOT/backend/app" "$REPO_ROOT/pipeline" \
    -name "*.py" ! -path "*/venv/*" ! -path "*/__pycache__/*" | wc -l)
PY_LINES=$(find "$REPO_ROOT/backend/app" "$REPO_ROOT/pipeline" \
    -name "*.py" ! -path "*/venv/*" ! -path "*/__pycache__/*" \
    -exec cat {} + | wc -l)

TS_FILES=$(find "$REPO_ROOT/frontend/src" "$REPO_ROOT/tests/frontend" "$REPO_ROOT/tests/essential" \
    -name "*.ts" -o -name "*.tsx" 2>/dev/null | wc -l)
TS_LINES=$(find "$REPO_ROOT/frontend/src" "$REPO_ROOT/tests/frontend" "$REPO_ROOT/tests/essential" \
    \( -name "*.ts" -o -name "*.tsx" \) 2>/dev/null \
    -exec cat {} + | wc -l)

# --- Python cyclomatic complexity via radon ---
echo "Calculating Python cyclomatic complexity ..."
PY_AVG_COMPLEXITY="null"
PY_MAX_COMPLEXITY="null"
PY_HIGH_COMPLEXITY="null"

if command -v radon >/dev/null 2>&1; then
    TMP_RADON=$(mktemp /tmp/radon_XXXXXX.json)
    trap 'rm -f "$TMP_RADON"' EXIT
    radon cc "$REPO_ROOT/backend/app" "$REPO_ROOT/pipeline" \
        --json --min A > "$TMP_RADON" 2>/dev/null || true
    eval "$(python3 - "$TMP_RADON" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
complexities = [
    block["complexity"]
    for blocks in data.values()
    for block in blocks
]
if complexities:
    avg = round(sum(complexities) / len(complexities), 2)
    max_c = max(complexities)
    high = sum(1 for c in complexities if c >= 10)
    print(f"PY_AVG_COMPLEXITY={avg}")
    print(f"PY_MAX_COMPLEXITY={max_c}")
    print(f"PY_HIGH_COMPLEXITY={high}")
else:
    print("PY_AVG_COMPLEXITY=null")
    print("PY_MAX_COMPLEXITY=null")
    print("PY_HIGH_COMPLEXITY=null")
PYEOF
    )"
else
    echo "WARNING: radon not found. Install with: pip install radon" >&2
fi

# --- TypeScript complexity via ESLint ---
echo "Checking TypeScript complexity via ESLint ..."
TS_HIGH_COMPLEXITY="null"
TMP_ESLINT=$(mktemp /tmp/eslint_XXXXXX.json)
trap 'rm -f "$TMP_ESLINT"' EXIT

cd "$REPO_ROOT/frontend"
# Run ESLint with max-complexity rule override, output as JSON.
# We accept ESLint exit code 1 (lint warnings/errors) since we're just collecting data.
npx eslint src/ \
    --rule '{"complexity": ["warn", {"max": 5}]}' \
    --format json \
    --output-file "$TMP_ESLINT" 2>/dev/null || true

TS_HIGH_COMPLEXITY=$(python3 - "$TMP_ESLINT" <<'PYEOF'
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    count = sum(
        1 for file in data
        for msg in file.get("messages", [])
        if msg.get("ruleId") == "complexity"
    )
    print(count)
except Exception:
    print("null")
PYEOF
)

# --- Duplication via jscpd ---
echo "Checking code duplication via jscpd ..."
DUP_PCT="null"
DUP_LINES="null"
TMP_JSCPD_DIR=$(mktemp -d /tmp/jscpd_XXXXXX)
trap 'rm -rf "$TMP_JSCPD_DIR"' EXIT

cd "$REPO_ROOT"
if npx --yes jscpd \
    --min-lines 5 \
    --reporters json \
    --output "$TMP_JSCPD_DIR" \
    --ignore "**/node_modules/**,**/venv/**,**/__pycache__/**,**/dist/**" \
    frontend/src backend/app pipeline \
    --silent 2>/dev/null; then

    DUP_PCT=$(python3 - "$TMP_JSCPD_DIR" <<'PYEOF'
import json, sys, os, glob
try:
    files = glob.glob(os.path.join(sys.argv[1], "*.json"))
    if not files:
        print("null"); sys.exit()
    with open(files[0]) as f:
        data = json.load(f)
    stats = data.get("statistics", {}).get("total", {})
    pct = stats.get("percentage")
    print(round(pct, 2) if pct is not None else "null")
except Exception:
    print("null")
PYEOF
    )
    DUP_LINES=$(python3 - "$TMP_JSCPD_DIR" <<'PYEOF'
import json, sys, os, glob
try:
    files = glob.glob(os.path.join(sys.argv[1], "*.json"))
    if not files:
        print("null"); sys.exit()
    with open(files[0]) as f:
        data = json.load(f)
    stats = data.get("statistics", {}).get("total", {})
    print(stats.get("duplicatedLines", "null"))
except Exception:
    print("null")
PYEOF
    )
fi

# --- Write JSONL record ---
python3 - <<EOF >> "$METRICS_FILE"
import json
record = {
    "timestamp": "$TIMESTAMP",
    "py_files": $PY_FILES,
    "py_lines": $PY_LINES,
    "py_avg_complexity": $PY_AVG_COMPLEXITY,
    "py_max_complexity": $PY_MAX_COMPLEXITY,
    "py_high_complexity_fns": $PY_HIGH_COMPLEXITY,
    "ts_files": $TS_FILES,
    "ts_lines": $TS_LINES,
    "ts_high_complexity_fns": $TS_HIGH_COMPLEXITY,
    "duplication_pct": $DUP_PCT,
    "duplication_lines": $DUP_LINES,
}
print(json.dumps(record))
EOF

echo "Code complexity recorded → $METRICS_FILE"
