#!/usr/bin/env bash
# Run Lighthouse against a deployed URL and record scores to metrics/lighthouse.jsonl.
# Requires Chromium (or Chrome) installed on the host.
# lighthouse is listed in frontend/package.json devDependencies and installed via npm install.
#
# Usage:
#   URL=http://localhost:8000 bash scripts/metrics/lighthouse.sh
#   bash scripts/metrics/lighthouse.sh                # defaults to http://localhost:8000
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
METRICS_FILE="$REPO_ROOT/metrics/lighthouse.jsonl"
TARGET_URL="${URL:-http://localhost:8000}"
TMP_JSON=$(mktemp /tmp/lighthouse_XXXXXX.json)
trap 'rm -f "$TMP_JSON"' EXIT

echo "Running Lighthouse against $TARGET_URL ..."

# Run Lighthouse, writing JSON to stdout and capturing it.
# --only-categories limits the run to the four scored categories (faster).
cd "$REPO_ROOT/frontend"
npx lighthouse \
    "$TARGET_URL" \
    --output json \
    --output-path "$TMP_JSON" \
    --chrome-flags="--headless --no-sandbox --disable-dev-shm-usage" \
    --only-categories=performance,accessibility,best-practices,seo \
    --quiet 2>/dev/null || {
    echo "ERROR: Lighthouse run failed. Is the server reachable at $TARGET_URL?" >&2
    exit 1
}

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Extract scores and key CWV audits from the JSON report.
python3 - "$TMP_JSON" "$TIMESTAMP" "$TARGET_URL" <<'EOF' >> "$METRICS_FILE"
import json, sys

report_path, timestamp, url = sys.argv[1], sys.argv[2], sys.argv[3]
with open(report_path) as f:
    data = json.load(f)

cats = data.get("categories", {})
audits = data.get("audits", {})

def score(key):
    return cats.get(key, {}).get("score")

def audit_ms(key):
    v = audits.get(key, {}).get("numericValue")
    return round(v) if v is not None else None

def audit_val(key):
    v = audits.get(key, {}).get("numericValue")
    return round(v, 4) if v is not None else None

record = {
    "timestamp": timestamp,
    "url": url,
    "performance": score("performance"),
    "accessibility": score("accessibility"),
    "best_practices": score("best-practices"),
    "seo": score("seo"),
    # Core Web Vitals
    "lcp_ms": audit_ms("largest-contentful-paint"),
    "fcp_ms": audit_ms("first-contentful-paint"),
    "tbt_ms": audit_ms("total-blocking-time"),
    "cls": audit_val("cumulative-layout-shift"),
    "tti_ms": audit_ms("interactive"),
    "speed_index_ms": audit_ms("speed-index"),
}
print(json.dumps(record))
EOF

echo "Lighthouse scores recorded → $METRICS_FILE"
