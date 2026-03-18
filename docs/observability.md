# Observability & Metrics

This document describes the seven metrics added to track application health,
performance, and code quality over time. All metrics write append-only JSONL
records to a `metrics/` directory at the repo root. The `metrics/*.jsonl` files
are gitignored (only `.gitkeep` is committed).

---

## Dependencies

All new dependencies are installed automatically by the session-start hook.

| Dependency | Version | Tracked in | Purpose |
|---|---|---|---|
| `lighthouse` | `@12` (major-pinned) | `npx --yes` (ephemeral) | Lighthouse CLI for Metrics 2 & 3 — ~180 transitive deps, not worth adding to lockfile for an optional metrics tool |
| `pip-audit` | `2.8.0` | `backend/requirements.txt` | CVE scanning for Python deps (Metric 5) |
| `radon` | `6.0.1` | `backend/requirements.txt` | Cyclomatic complexity for Python (Metric 6) |
| `jscpd` | latest | `npx --yes` (ephemeral) | Duplication detection for Metric 6 |
| Chromium / Chrome | system | OS package manager | Required by Lighthouse headless (Metrics 2 & 3) |

> `jscpd` is the only dependency not pinned in a lockfile. It is downloaded
> on demand by `npx --yes` and is used only for duplication analysis.

---

## Metric 1 — Bundle Size

**Script:** `scripts/metrics/bundle_size.sh`
**When to run:** After `npm run build` (i.e., post-build, not post-deploy).
**Output file:** `metrics/bundle_size.jsonl`

Measures the built `frontend/dist/` directory. Fails fast if the dist directory
does not exist.

```bash
# Build first, then measure:
cd frontend && npm run build && cd ..
bash scripts/metrics/bundle_size.sh
```

**JSONL fields:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC |
| `total_bytes` | int | Total size of `frontend/dist/` in bytes |
| `assets_bytes` | int | Size of `frontend/dist/assets/` (JS + CSS chunks) |
| `index_bytes` | int | Size of `frontend/dist/index.html` |
| `js_chunks` | int | Number of `.js` files in `assets/` |
| `css_chunks` | int | Number of `.css` files in `assets/` |

**Example record:**
```json
{"timestamp": "2026-03-16T12:00:00Z", "total_bytes": 312456, "assets_bytes": 280000, "index_bytes": 2500, "js_chunks": 3, "css_chunks": 1}
```

**Threshold to watch:** `total_bytes` above ~400 000 (400 KB) warrants investigation.

---

## Metric 2 — Lighthouse Scores

**Script:** `scripts/metrics/lighthouse.sh`
**When to run:** After deployment, against a running server.
**Output file:** `metrics/lighthouse.jsonl`
**Requires:** Chromium installed on the host.

```bash
URL=http://localhost:8000 bash scripts/metrics/lighthouse.sh
# URL defaults to http://localhost:8000 if not set.
```

**JSONL fields:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC |
| `url` | string | Target URL |
| `performance` | float | Lighthouse performance score (0–1) |
| `accessibility` | float | Lighthouse accessibility score (0–1) |
| `best_practices` | float | Lighthouse best-practices score (0–1) |
| `seo` | float | Lighthouse SEO score (0–1) |
| `lcp_ms` | int | Largest Contentful Paint (ms) |
| `fcp_ms` | int | First Contentful Paint (ms) |
| `tbt_ms` | int | Total Blocking Time (ms) |
| `cls` | float | Cumulative Layout Shift (unitless) |
| `tti_ms` | int | Time to Interactive (ms) |
| `speed_index_ms` | int | Speed Index (ms) |

**Example record:**
```json
{"timestamp": "2026-03-16T12:00:00Z", "url": "http://localhost:8000", "performance": 0.94, "accessibility": 0.98, "best_practices": 1.0, "seo": 0.90, "lcp_ms": 1200, "fcp_ms": 800, "tbt_ms": 15, "cls": 0.01, "tti_ms": 1350, "speed_index_ms": 950}
```

**Thresholds to watch:** `performance` below 0.9; `lcp_ms` above 2500.

---

## Metric 3 — Page Load Time / Core Web Vitals

**Script:** `scripts/metrics/page_load.sh`
**When to run:** After deployment, against a running server.
**Output file:** `metrics/page_load.jsonl`

Two-tier collection:
- **Tier 1 (always):** TTFB and total transfer time via `curl`. No extra dependencies.
- **Tier 2 (if `npx` is available):** Core Web Vitals from a Lighthouse run. Requires Chromium.

```bash
URL=http://localhost:8000 bash scripts/metrics/page_load.sh
```

**JSONL fields:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC |
| `url` | string | Target URL |
| `ttfb_ms` | int | Time to First Byte — median of 3 curl requests (ms) |
| `total_ms` | int | Total transfer time for the full page (ms) |
| `lcp_ms` | int \| null | Largest Contentful Paint (ms); null if Lighthouse unavailable |
| `fcp_ms` | int \| null | First Contentful Paint (ms) |
| `tbt_ms` | int \| null | Total Blocking Time (ms) |
| `cls` | float \| null | Cumulative Layout Shift |
| `tti_ms` | int \| null | Time to Interactive (ms) |

**Example record (Tier 1 + 2):**
```json
{"timestamp": "2026-03-16T12:00:00Z", "url": "http://localhost:8000", "ttfb_ms": 42, "total_ms": 180, "lcp_ms": 1200, "fcp_ms": 800, "tbt_ms": 15, "cls": 0.01, "tti_ms": 1350}
```

**Thresholds to watch:** `ttfb_ms` above 200; `lcp_ms` above 2500.

---

## Metric 4 — Test Execution Time

**Script:** `scripts/metrics/test_timing.sh`
**When to run:** Any time; runs independently from `pipeline.sh`.
**Output file:** `metrics/test_timing.jsonl`

Times each test suite individually. Use the `SUITES` env var to run a subset.

```bash
bash scripts/metrics/test_timing.sh                              # all suites
SUITES=frontend,backend bash scripts/metrics/test_timing.sh     # specific suites
```

**Available suites:** `essential-frontend`, `essential-backend`, `frontend`, `backend`, `pipeline`.

One record is written per suite per run.

**JSONL fields:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC (same for all suites in one run) |
| `suite` | string | Suite name (e.g. `"frontend"`) |
| `duration_ms` | int | Wall-clock duration of the suite (ms) |
| `passed` | int \| null | Number of passing tests |
| `failed` | int \| null | Number of failing tests |
| `skipped` | int \| null | Number of skipped tests |
| `exit_code` | int | Process exit code (0 = success) |

**Example records:**
```json
{"timestamp": "2026-03-16T12:00:00Z", "suite": "frontend", "duration_ms": 4821, "passed": 12, "failed": 0, "skipped": null, "exit_code": 0}
{"timestamp": "2026-03-16T12:00:00Z", "suite": "backend", "duration_ms": 2103, "passed": 18, "failed": 0, "skipped": null, "exit_code": 0}
```

**Thresholds to watch:** A suite duration doubling week-over-week; any `failed > 0`.

---

## Metric 5 — Dependency Audit

**Script:** `scripts/metrics/dependency_audit.sh`
**When to run:** Weekly, or after any `npm install` / `pip install`.
**Output file:** `metrics/dependency_audit.jsonl`
**Requires:** `pip-audit` (installed via `backend/requirements.txt`).

```bash
bash scripts/metrics/dependency_audit.sh
```

**JSONL fields:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC |
| `frontend_direct_deps` | int | Direct deps in `package.json` (deps + devDeps) |
| `frontend_total_deps` | int | Total installed packages from `npm audit` metadata |
| `frontend_vuln_count` | int | Total vulnerabilities from `npm audit` |
| `frontend_vuln_severity` | object | Counts by severity: `{critical, high, moderate, low, info}` |
| `frontend_vulns` | array | Details of up to 10 vulnerabilities |
| `backend_deps` | int | Non-blank, non-comment lines in `requirements.txt` |
| `backend_vuln_count` | int | CVEs found by `pip-audit` |
| `backend_vulns` | array | Details of each CVE: `{name, version, id, description}` |

**Example record:**
```json
{"timestamp": "2026-03-16T12:00:00Z", "frontend_direct_deps": 17, "frontend_total_deps": 265, "frontend_vuln_count": 3, "frontend_vuln_severity": {"critical": 0, "high": 3, "moderate": 0, "low": 0, "info": 0}, "frontend_vulns": [...], "backend_deps": 21, "backend_vuln_count": 0, "backend_vulns": []}
```

**Thresholds to watch:** Any `critical` or `high` severity; `backend_vuln_count > 0`.

---

## Metric 6 — Code Complexity

**Script:** `scripts/metrics/code_complexity.sh`
**When to run:** Weekly, or after large refactors.
**Output file:** `metrics/code_complexity.jsonl`
**Requires:** `radon` (installed via `backend/requirements.txt`). `jscpd` is fetched via `npx`.

```bash
bash scripts/metrics/code_complexity.sh
```

**JSONL fields:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC |
| `py_files` | int | Python source files in `backend/app/` and `pipeline/` |
| `py_lines` | int | Total lines across those files |
| `py_avg_complexity` | float \| null | Mean cyclomatic complexity (radon) |
| `py_max_complexity` | int \| null | Highest cyclomatic complexity of any function |
| `py_high_complexity_fns` | int \| null | Functions with complexity ≥ 10 |
| `ts_files` | int | TypeScript files in `frontend/src/` and test directories |
| `ts_lines` | int | Total lines across those files |
| `ts_high_complexity_fns` | int \| null | Functions violating ESLint `complexity` rule (max 5) |
| `duplication_pct` | float \| null | Percentage of duplicated lines (jscpd) |
| `duplication_lines` | int \| null | Number of duplicated lines |

**Example record:**
```json
{"timestamp": "2026-03-16T12:00:00Z", "py_files": 12, "py_lines": 1840, "py_avg_complexity": 2.3, "py_max_complexity": 8, "py_high_complexity_fns": 0, "ts_files": 6, "ts_lines": 920, "ts_high_complexity_fns": 0, "duplication_pct": 1.2, "duplication_lines": 22}
```

**Thresholds to watch:** `py_max_complexity ≥ 10`; `duplication_pct > 5`.

---

## Metric 7 — HTTP Error Rate (live)

**Source:** `backend/app/middleware_metrics.py` + `/api/metrics` endpoint
**When to read:** Any time the backend server is running.
**Output file:** `metrics/error_rate.jsonl` (snapshot appended every 100 requests)

The `MetricsMiddleware` Starlette middleware counts every HTTP response by
status-code bucket. Counters are in-memory and reset on process restart; the
JSONL file preserves history across restarts.

```bash
curl http://localhost:8000/api/metrics
```

**Response / JSONL fields:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC (JSONL snapshots only) |
| `total` | int | Total requests since server start |
| `2xx` | int | 2xx responses |
| `3xx` | int | 3xx responses |
| `4xx` | int | 4xx responses |
| `5xx` | int | 5xx responses |
| `other` | int | Responses outside standard buckets |
| `error_rate_4xx` | float | `4xx / total` (0–1) |
| `error_rate_5xx` | float | `5xx / total` (0–1) |

**Example response:**
```json
{"total": 1500, "2xx": 1470, "3xx": 0, "4xx": 28, "5xx": 2, "other": 0, "error_rate_4xx": 0.0187, "error_rate_5xx": 0.0013}
```

**Thresholds to watch:** `error_rate_5xx > 0.01` (>1%); `error_rate_4xx > 0.05` (>5%).

---

## Quick Reference

| # | Metric | Script / Endpoint | Output file | When to run |
|---|---|---|---|---|
| 1 | Bundle size | `scripts/metrics/bundle_size.sh` | `metrics/bundle_size.jsonl` | Post-build |
| 2 | Lighthouse scores | `scripts/metrics/lighthouse.sh` | `metrics/lighthouse.jsonl` | Post-deploy |
| 3 | Page load / CWV | `scripts/metrics/page_load.sh` | `metrics/page_load.jsonl` | Post-deploy |
| 4 | Test timing | `scripts/metrics/test_timing.sh` | `metrics/test_timing.jsonl` | Any time |
| 5 | Dependency audit | `scripts/metrics/dependency_audit.sh` | `metrics/dependency_audit.jsonl` | Weekly |
| 6 | Code complexity | `scripts/metrics/code_complexity.sh` | `metrics/code_complexity.jsonl` | Weekly |
| 7 | HTTP error rate | `GET /api/metrics` | `metrics/error_rate.jsonl` | Live |
