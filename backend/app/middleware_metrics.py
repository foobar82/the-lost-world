"""
HTTP request/error rate tracking middleware.

Maintains in-memory counters for all requests, grouped by HTTP status bucket.
Flushes a snapshot to metrics/error_rate.jsonl every FLUSH_INTERVAL requests
so trends are persisted across server restarts.

Usage (in main.py):
    from .middleware_metrics import MetricsMiddleware, get_counters
    app.add_middleware(MetricsMiddleware)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# How many requests between automatic flushes to disk.
FLUSH_INTERVAL = 100

# Counters are module-level so they survive middleware re-instantiation within
# a single process; they reset on process restart.
_counters: dict[str, int] = {
    "total": 0,
    "2xx": 0,
    "3xx": 0,
    "4xx": 0,
    "5xx": 0,
    "other": 0,
}

# Path to the JSONL file relative to the repo root.
# __file__ is backend/app/middleware_metrics.py → parents[2] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_METRICS_FILE = _REPO_ROOT / "metrics" / "error_rate.jsonl"


def get_counters() -> dict[str, int | float]:
    """Return current counters plus derived error-rate fields."""
    total = _counters["total"]
    result: dict[str, int | float] = dict(_counters)
    result["error_rate_4xx"] = round(_counters["4xx"] / total, 4) if total else 0.0
    result["error_rate_5xx"] = round(_counters["5xx"] / total, 4) if total else 0.0
    return result


def _flush_to_jsonl() -> None:
    """Append a snapshot of current counters to the JSONL metrics file."""
    try:
        _METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            **get_counters(),
        }
        with _METRICS_FILE.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        logger.exception("Failed to flush error-rate metrics to %s", _METRICS_FILE)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Count every HTTP response by status bucket; flush to disk periodically."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        code = response.status_code
        bucket = f"{code // 100}xx"

        _counters["total"] += 1
        _counters[bucket] = _counters.get(bucket, 0) + 1

        if _counters["total"] % FLUSH_INTERVAL == 0:
            _flush_to_jsonl()

        return response
