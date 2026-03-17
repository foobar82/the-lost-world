#!/usr/bin/env bash
# Measure page load time and Core Web Vitals synthetically.
# Tier 1 (always): TTFB via curl — zero new dependencies.
# Tier 2 (if Lighthouse available): LCP, FCP, CLS, TBT from lighthouse.sh output.
#
# Usage:
#   URL=http://localhost:8000 bash scripts/metrics/page_load.sh
#   bash scripts/metrics/page_load.sh   # defaults to http://localhost:8000
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
METRICS_FILE="$REPO_ROOT/metrics/page_load.jsonl"
TARGET_URL="${URL:-http://localhost:8000}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- Tier 1: TTFB via curl ---
echo "Measuring TTFB for $TARGET_URL ..."

# Run 3 requests and take the median to reduce noise.
read_times=()
for _ in 1 2 3; do
    t=$(curl -o /dev/null -s \
        --write-out '%{time_starttransfer}' \
        --max-time 10 \
        "$TARGET_URL" 2>/dev/null || echo "0")
    read_times+=("$t")
done

# Compute median with python.
TTFB_MS=$(python3 -c "
times = sorted([float(x) for x in '${read_times[*]}'.split()])
median = times[len(times)//2]
print(round(median * 1000))
" 2>/dev/null || echo "null")

# Total transfer time (full page load including body).
TOTAL_MS=$(curl -o /dev/null -s \
    --write-out '%{time_total}' \
    --max-time 30 \
    "$TARGET_URL" 2>/dev/null \
    | python3 -c "import sys; print(round(float(sys.stdin.read().strip()) * 1000))" \
    || echo "null")

# --- Tier 2: CWV via Lighthouse (optional) ---
LCP_MS="null"; FCP_MS="null"; CLS="null"; TBT_MS="null"; TTI_MS="null"

if command -v npx >/dev/null 2>&1; then
    echo "Collecting Core Web Vitals via Lighthouse ..."
    TMP_LH=$(mktemp /tmp/lh_cwv_XXXXXX.json)
    trap 'rm -f "$TMP_LH"' EXIT

    cd "$REPO_ROOT/frontend"
    if npx --yes lighthouse@12 \
        "$TARGET_URL" \
        --output json \
        --output-path "$TMP_LH" \
        --chrome-flags="--headless --no-sandbox --disable-dev-shm-usage" \
        --only-categories=performance \
        --quiet 2>/dev/null; then

        eval "$(python3 - "$TMP_LH" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
audits = data.get("audits", {})
def ms(key):
    v = audits.get(key, {}).get("numericValue")
    return round(v) if v is not None else None
def val(key):
    v = audits.get(key, {}).get("numericValue")
    return round(v, 4) if v is not None else None
print(f"LCP_MS={ms('largest-contentful-paint') or 'null'}")
print(f"FCP_MS={ms('first-contentful-paint') or 'null'}")
print(f"TBT_MS={ms('total-blocking-time') or 'null'}")
print(f"CLS={val('cumulative-layout-shift') or 'null'}")
print(f"TTI_MS={ms('interactive') or 'null'}")
PYEOF
        )"
    fi
else
    echo "Lighthouse not available; recording TTFB only."
fi

# --- Write JSONL record ---
python3 - <<EOF >> "$METRICS_FILE"
import json
record = {
    "timestamp": "$TIMESTAMP",
    "url": "$TARGET_URL",
    "ttfb_ms": $TTFB_MS,
    "total_ms": $TOTAL_MS,
    "lcp_ms": $LCP_MS,
    "fcp_ms": $FCP_MS,
    "tbt_ms": $TBT_MS,
    "cls": $CLS,
    "tti_ms": $TTI_MS,
}
print(json.dumps(record))
EOF

echo "Page load metrics recorded: TTFB=${TTFB_MS}ms → $METRICS_FILE"
