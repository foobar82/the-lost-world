#!/usr/bin/env bash
# Measure code churn for a commit range and append a JSONL record to metrics/code_churn.jsonl.
# Uses only git (always available) and python3 (stdlib only).
#
# Usage:
#   bash scripts/metrics/code_churn.sh                              # last 24 hours
#   SINCE="7 days ago" bash scripts/metrics/code_churn.sh          # last week
#   FROM_REF=main TO_REF=HEAD bash scripts/metrics/code_churn.sh   # ref range
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
METRICS_FILE="$REPO_ROOT/metrics/code_churn.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cd "$REPO_ROOT"

# Determine range: ref-based (FROM_REF..TO_REF) or time-based (--since=SINCE).
FROM_REF="${FROM_REF:-}"
TO_REF="${TO_REF:-HEAD}"
SINCE="${SINCE:-24 hours ago}"

if [ -n "$FROM_REF" ]; then
    RANGE_DESC="${FROM_REF}..${TO_REF}"
    LOG_ARGS=("${FROM_REF}..${TO_REF}")
else
    RANGE_DESC="since ${SINCE}"
    LOG_ARGS=("--since=${SINCE}" "HEAD")
fi

# Commit count and unique author emails for the range.
COMMIT_COUNT=$(git log --oneline "${LOG_ARGS[@]}" | wc -l | tr -d ' ')
AUTHOR_COUNT=$(git log --format="%ae" "${LOG_ARGS[@]}" | sort -u | wc -l | tr -d ' ')

# Total files currently tracked by git.
TOTAL_TRACKED=$(git ls-files | wc -l | tr -d ' ')

# Write numstat (lines added/removed per file) to a temp file to avoid
# embedding multi-line shell output inside a Python heredoc.
TMP_NUMSTAT=$(mktemp /tmp/churn_numstat_XXXXXX.txt)
trap 'rm -f "$TMP_NUMSTAT"' EXIT
git log --numstat --format="" "${LOG_ARGS[@]}" > "$TMP_NUMSTAT"

python3 - "$TIMESTAMP" "$RANGE_DESC" "$COMMIT_COUNT" "$AUTHOR_COUNT" "$TOTAL_TRACKED" "$TMP_NUMSTAT" <<'PYEOF' >> "$METRICS_FILE"
import json, sys

timestamp, range_desc, commit_count_s, author_count_s, total_tracked_s, numstat_file = sys.argv[1:]
commit_count   = int(commit_count_s)
author_count   = int(author_count_s)
total_tracked  = int(total_tracked_s)

# Parse numstat: "<added>\t<removed>\t<filepath>"
# Binary files show "-\t-\t<file>" — skip those.
file_stats   = {}
lines_added   = 0
lines_removed = 0

with open(numstat_file) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t', 2)
        if len(parts) != 3:
            continue
        added_s, removed_s, filepath = parts
        if added_s == '-' or removed_s == '-':
            continue  # binary file
        added   = int(added_s)
        removed = int(removed_s)
        lines_added   += added
        lines_removed += removed
        if filepath not in file_stats:
            file_stats[filepath] = [0, 0]
        file_stats[filepath][0] += added
        file_stats[filepath][1] += removed

files_touched = len(file_stats)
files_pct     = round(files_touched / total_tracked * 100, 2) if total_tracked > 0 else 0.0

# Top 10 files by total lines changed.
top_files = sorted(
    [{"file": f, "added": s[0], "removed": s[1]} for f, s in file_stats.items()],
    key=lambda x: x["added"] + x["removed"],
    reverse=True,
)[:10]

record = {
    "timestamp":           timestamp,
    "range":               range_desc,
    "commits":             commit_count,
    "authors":             author_count,
    "lines_added":         lines_added,
    "lines_removed":       lines_removed,
    "net_lines":           lines_added - lines_removed,
    "files_touched":       files_touched,
    "total_tracked_files": total_tracked,
    "files_pct":           files_pct,
    "top_files":           top_files,
}
print(json.dumps(record))
PYEOF

echo "Code churn recorded (${RANGE_DESC}): ${COMMIT_COUNT} commits, ${AUTHOR_COUNT} authors → $METRICS_FILE"
