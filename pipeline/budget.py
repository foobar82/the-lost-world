"""Budget tracking — monitors API spend against daily and weekly caps."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .constants import COST_PER_TOKEN_GBP, DAILY_CAP_GBP, WEEKLY_CAP_GBP

logger = logging.getLogger(__name__)

BUDGET_FILE = Path(__file__).resolve().parent / "data" / "budget.json"
KILL_SWITCH_FILE = Path(__file__).resolve().parent / "data" / "STOP"


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


def record_task() -> None:
    """Record that one task was built, incrementing today's task counter."""
    data = _load_budget()
    today = _today_str()
    data.setdefault("tasks_daily", {})
    data["tasks_daily"][today] = data["tasks_daily"].get(today, 0) + 1
    _save_budget(data)
    logger.info("Recorded task — daily total: %d", data["tasks_daily"][today])


def check_task_limits(max_per_day: int) -> dict:
    """Return daily task count and whether more tasks are allowed.

    Returns a dict with keys:
        today_count, daily_remaining, daily_allowed (bool)
    """
    data = _load_budget()
    today = _today_str()
    today_count = data.get("tasks_daily", {}).get(today, 0)
    daily_remaining = max(0, max_per_day - today_count)
    return {
        "today_count": today_count,
        "daily_remaining": daily_remaining,
        "daily_allowed": daily_remaining > 0,
    }


def check_kill_switch() -> dict:
    """Check whether the manual kill switch has been activated.

    The kill switch is a plain file at ``pipeline/data/STOP``.  Create it
    (e.g. ``touch pipeline/data/STOP`` over SSH) to halt any batch that has
    not yet started or is between tasks.  Remove it to re-enable the pipeline.

    Returns a dict with keys:
        active (bool), path (str)
    """
    active = KILL_SWITCH_FILE.exists()
    if active:
        logger.warning(
            "Kill switch active — %s exists. Remove it to re-enable the pipeline.",
            KILL_SWITCH_FILE,
        )
    return {"active": active, "path": str(KILL_SWITCH_FILE)}


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
