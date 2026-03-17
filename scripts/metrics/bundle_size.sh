#!/usr/bin/env bash
# Measure the built frontend bundle size and append a JSONL record to metrics/bundle_size.jsonl.
# Must be run after `npm run build` (frontend/dist/ must exist).
#
# Usage:
#   bash scripts/metrics/bundle_size.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$REPO_ROOT/frontend/dist"
METRICS_FILE="$REPO_ROOT/metrics/bundle_size.jsonl"

if [ ! -d "$DIST_DIR" ]; then
    echo "ERROR: $DIST_DIR does not exist. Run 'npm run build' first." >&2
    exit 1
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Total size of the dist directory in bytes.
TOTAL_BYTES=$(du -sb "$DIST_DIR" | awk '{print $1}')

# Size of the assets subdirectory (JS/CSS chunks).
ASSETS_BYTES=0
if [ -d "$DIST_DIR/assets" ]; then
    ASSETS_BYTES=$(du -sb "$DIST_DIR/assets" | awk '{print $1}')
fi

# Size of index.html.
INDEX_BYTES=0
if [ -f "$DIST_DIR/index.html" ]; then
    INDEX_BYTES=$(stat -c%s "$DIST_DIR/index.html")
fi

# Count of JS and CSS chunks in assets/.
JS_CHUNKS=0
CSS_CHUNKS=0
if [ -d "$DIST_DIR/assets" ]; then
    JS_CHUNKS=$(find "$DIST_DIR/assets" -name "*.js" | wc -l)
    CSS_CHUNKS=$(find "$DIST_DIR/assets" -name "*.css" | wc -l)
fi

# Build the JSON record using python (avoids jq dependency).
python3 - <<EOF >> "$METRICS_FILE"
import json
record = {
    "timestamp": "$TIMESTAMP",
    "total_bytes": $TOTAL_BYTES,
    "assets_bytes": $ASSETS_BYTES,
    "index_bytes": $INDEX_BYTES,
    "js_chunks": $JS_CHUNKS,
    "css_chunks": $CSS_CHUNKS,
}
print(json.dumps(record))
EOF

echo "Bundle size recorded: total=${TOTAL_BYTES} bytes → $METRICS_FILE"
