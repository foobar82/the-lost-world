"""Budget tracking — monitors API spend against daily and weekly caps."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BUDGET_FILE = Path(__file__).resolve().parent / "data" / "budget.json"

DAILY_CAP_GBP = 2.00
WEEKLY_CAP_GBP = 8.00

# Approximate cost per token in GBP (based on Anthropic pricing).
# These are rough estimates — input and output tokens have different rates,
# but we use a blended average for simplicity.
COST_PER_TOKEN_GBP = 0.000012


def _today_str() -> str:
    """Return today's date as an ISO string in UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _monday_str() -> str:
    """Return the Monday of the current week as an ISO string in UTC."""
    now = datetime.now(timezone.utc)
    monday = now.date() - __import__("datetime").timedelta(days=now.weekday())
    return monday.isoformat()


def _load_budget() -> dict:
    """Load budget data from disk, returning sensible defaults if missing."""
    if not BUDGET_FILE.exists():
        return {"daily": {}, "weekly": {}}
    try:
        return json.loads(BUDGET_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read budget file — starting fresh")
        return {"daily": {}, "weekly": {}}


def _save_budget(data: dict) -> None:
    """Persist budget data to disk."""
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(data, indent=2))


def record_usage(tokens: int) -> None:
    """Record *tokens* of API usage, updating both daily and weekly totals."""
    cost = tokens * COST_PER_TOKEN_GBP
    data = _load_budget()

    today = _today_str()
    week = _monday_str()

    data.setdefault("daily", {})
    data.setdefault("weekly", {})

    data["daily"][today] = data["daily"].get(today, 0.0) + cost
    data["weekly"][week] = data["weekly"].get(week, 0.0) + cost

    _save_budget(data)
    logger.info("Recorded %d tokens (£%.4f) — daily: £%.4f, weekly: £%.4f",
                tokens, cost, data["daily"][today], data["weekly"][week])


def check_budget() -> dict:
    """Return remaining daily and weekly budget in GBP.

    Returns a dict with keys:
        daily_spent, daily_remaining, daily_cap,
        weekly_spent, weekly_remaining, weekly_cap,
        allowed (bool — True if both daily and weekly budgets have room)
    """
    data = _load_budget()

    today = _today_str()
    week = _monday_str()

    daily_spent = data.get("daily", {}).get(today, 0.0)
    weekly_spent = data.get("weekly", {}).get(week, 0.0)

    daily_remaining = max(0.0, DAILY_CAP_GBP - daily_spent)
    weekly_remaining = max(0.0, WEEKLY_CAP_GBP - weekly_spent)

    return {
        "daily_spent": daily_spent,
        "daily_remaining": daily_remaining,
        "daily_cap": DAILY_CAP_GBP,
        "weekly_spent": weekly_spent,
        "weekly_remaining": weekly_remaining,
        "weekly_cap": WEEKLY_CAP_GBP,
        "allowed": daily_remaining > 0 and weekly_remaining > 0,
    }
