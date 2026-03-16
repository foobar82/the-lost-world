#!/usr/bin/env bash
# Audit dependency counts and known CVEs for both frontend (npm) and backend (pip).
# Appends a JSONL record to metrics/dependency_audit.jsonl.
#
# Requirements:
#   - npm audit (bundled with npm, no install needed)
#   - pip-audit (must be installed: pip install pip-audit)
#
# Usage:
#   bash scripts/metrics/dependency_audit.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
METRICS_FILE="$REPO_ROOT/metrics/dependency_audit.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TMP_NPM=$(mktemp /tmp/npm_audit_XXXXXX.json)
TMP_PIP=$(mktemp /tmp/pip_audit_XXXXXX.json)
trap 'rm -f "$TMP_NPM" "$TMP_PIP"' EXIT

# --- Frontend: npm audit ---
echo "Running npm audit ..."
cd "$REPO_ROOT/frontend"
# npm audit exits non-zero if vulns found; we capture output regardless.
npm audit --json > "$TMP_NPM" 2>/dev/null || true

# Count direct dependencies from package.json.
FRONTEND_DIRECT_DEPS=$(python3 -c "
import json
with open('$REPO_ROOT/frontend/package.json') as f:
    pkg = json.load(f)
deps = len(pkg.get('dependencies', {}))
dev_deps = len(pkg.get('devDependencies', {}))
print(deps + dev_deps)
")

# --- Backend: pip-audit ---
echo "Running pip-audit ..."
cd "$REPO_ROOT/backend"
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

if command -v pip-audit >/dev/null 2>&1; then
    pip-audit --format json --output "$TMP_PIP" 2>/dev/null || true
else
    echo '{"dependencies": [], "vulnerabilities": []}' > "$TMP_PIP"
    echo "WARNING: pip-audit not found. Install with: pip install pip-audit" >&2
fi

# Count backend deps from requirements.txt (non-blank, non-comment lines).
BACKEND_DEPS=$(grep -cE '^[^#[:space:]]' "$REPO_ROOT/backend/requirements.txt" || true)

# --- Parse and write JSONL record ---
python3 - "$TMP_NPM" "$TMP_PIP" "$TIMESTAMP" "$FRONTEND_DIRECT_DEPS" "$BACKEND_DEPS" <<'PYEOF' >> "$METRICS_FILE"
import json, sys

npm_path, pip_path, timestamp, fe_direct, be_count = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])

# Parse npm audit output.
fe_total = 0
fe_vulns = []
fe_vuln_count = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "info": 0}
try:
    with open(npm_path) as f:
        npm = json.load(f)
    # npm audit v2+ format
    if "metadata" in npm:
        fe_total = npm["metadata"].get("totalDependencies", 0)
        vulns = npm.get("metadata", {}).get("vulnerabilities", {})
        for sev, count in vulns.items():
            if sev in fe_vuln_count:
                fe_vuln_count[sev] = count
        # Collect advisory details (top 10 to keep record small).
        for _id, vuln in list(npm.get("vulnerabilities", {}).items())[:10]:
            fe_vulns.append({
                "name": vuln.get("name"),
                "severity": vuln.get("severity"),
                "via": [v if isinstance(v, str) else v.get("title") for v in vuln.get("via", [])[:3]],
            })
    elif "advisories" in npm:
        # npm audit v1 format
        for adv in npm["advisories"].values():
            fe_vulns.append({"name": adv.get("module_name"), "severity": adv.get("severity"), "title": adv.get("title")})
except Exception:
    pass

# Parse pip-audit output.
be_vulns = []
be_vuln_count = 0
try:
    with open(pip_path) as f:
        pip = json.load(f)
    # pip-audit format: list of {"name", "version", "vulns": [...]}
    deps_list = pip if isinstance(pip, list) else pip.get("dependencies", [])
    for dep in deps_list:
        for v in dep.get("vulns", []):
            be_vuln_count += 1
            be_vulns.append({
                "name": dep.get("name"),
                "version": dep.get("version"),
                "id": v.get("id"),
                "description": (v.get("description") or "")[:120],
            })
except Exception:
    pass

fe_total_vulns = sum(fe_vuln_count.values())
record = {
    "timestamp": timestamp,
    "frontend_direct_deps": fe_direct,
    "frontend_total_deps": fe_total,
    "frontend_vuln_count": fe_total_vulns,
    "frontend_vuln_severity": fe_vuln_count,
    "frontend_vulns": fe_vulns,
    "backend_deps": be_count,
    "backend_vuln_count": be_vuln_count,
    "backend_vulns": be_vulns,
}
print(json.dumps(record))
PYEOF

echo "Dependency audit recorded → $METRICS_FILE"
