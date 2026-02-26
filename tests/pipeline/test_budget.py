"""Tests for pipeline.budget — budget tracking, reset logic, cap enforcement."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.budget import (  # noqa: E402
    COST_PER_TOKEN_GBP,
    DAILY_CAP_GBP,
    WEEKLY_CAP_GBP,
    _load_budget,
    _save_budget,
    check_budget,
    record_usage,
)


@pytest.fixture(autouse=True)
def _tmp_budget_file(tmp_path, monkeypatch):
    """Point BUDGET_FILE at a temporary path for every test."""
    budget_file = tmp_path / "budget.json"
    monkeypatch.setattr("pipeline.budget.BUDGET_FILE", budget_file)
    yield budget_file


# ---------------------------------------------------------------------------
# Basic recording
# ---------------------------------------------------------------------------


class TestRecordUsage:
    def test_records_daily_spend(self, _tmp_budget_file):
        record_usage(1000)
        data = json.loads(_tmp_budget_file.read_text())
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert data["daily"][today] == pytest.approx(1000 * COST_PER_TOKEN_GBP)

    def test_records_weekly_spend(self, _tmp_budget_file):
        record_usage(1000)
        data = json.loads(_tmp_budget_file.read_text())
        now = datetime.now(timezone.utc)
        monday = (now.date() - timedelta(days=now.weekday())).isoformat()
        assert data["weekly"][monday] == pytest.approx(1000 * COST_PER_TOKEN_GBP)

    def test_accumulates_multiple_calls(self, _tmp_budget_file):
        record_usage(1000)
        record_usage(2000)
        data = json.loads(_tmp_budget_file.read_text())
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert data["daily"][today] == pytest.approx(3000 * COST_PER_TOKEN_GBP)

    def test_creates_budget_file_if_missing(self, _tmp_budget_file):
        assert not _tmp_budget_file.exists()
        record_usage(100)
        assert _tmp_budget_file.exists()


# ---------------------------------------------------------------------------
# check_budget
# ---------------------------------------------------------------------------


class TestCheckBudget:
    def test_fresh_budget_is_fully_available(self):
        budget = check_budget()
        assert budget["daily_remaining"] == pytest.approx(DAILY_CAP_GBP)
        assert budget["weekly_remaining"] == pytest.approx(WEEKLY_CAP_GBP)
        assert budget["allowed"] is True

    def test_partial_spend_reduces_remaining(self):
        record_usage(10000)
        budget = check_budget()
        expected_cost = 10000 * COST_PER_TOKEN_GBP
        assert budget["daily_spent"] == pytest.approx(expected_cost)
        assert budget["daily_remaining"] == pytest.approx(DAILY_CAP_GBP - expected_cost)
        assert budget["allowed"] is True

    def test_returns_correct_caps(self):
        budget = check_budget()
        assert budget["daily_cap"] == DAILY_CAP_GBP
        assert budget["weekly_cap"] == WEEKLY_CAP_GBP


# ---------------------------------------------------------------------------
# Cap enforcement
# ---------------------------------------------------------------------------


class TestCapEnforcement:
    def test_daily_cap_blocks_when_exceeded(self):
        # Spend enough to exceed the daily cap.
        tokens_to_exceed = int(DAILY_CAP_GBP / COST_PER_TOKEN_GBP) + 1
        record_usage(tokens_to_exceed)
        budget = check_budget()
        assert budget["daily_remaining"] == 0.0
        assert budget["allowed"] is False

    def test_weekly_cap_blocks_when_exceeded(self):
        # Spend enough to exceed the weekly cap in one go.
        tokens_to_exceed = int(WEEKLY_CAP_GBP / COST_PER_TOKEN_GBP) + 1
        record_usage(tokens_to_exceed)
        budget = check_budget()
        assert budget["weekly_remaining"] == 0.0
        assert budget["allowed"] is False

    def test_remaining_never_goes_negative(self):
        huge = int((WEEKLY_CAP_GBP * 2) / COST_PER_TOKEN_GBP)
        record_usage(huge)
        budget = check_budget()
        assert budget["daily_remaining"] >= 0.0
        assert budget["weekly_remaining"] >= 0.0


# ---------------------------------------------------------------------------
# Reset logic
# ---------------------------------------------------------------------------


class TestResetLogic:
    def test_daily_resets_on_new_day(self, _tmp_budget_file):
        """Spending recorded yesterday does not count towards today's budget."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        data = {
            "daily": {yesterday: DAILY_CAP_GBP},
            "weekly": {},
        }
        _tmp_budget_file.write_text(json.dumps(data))

        budget = check_budget()
        assert budget["daily_spent"] == 0.0
        assert budget["daily_remaining"] == pytest.approx(DAILY_CAP_GBP)
        assert budget["allowed"] is True

    def test_weekly_resets_on_new_week(self, _tmp_budget_file):
        """Spending recorded last week does not count towards this week's budget."""
        last_monday = (
            datetime.now(timezone.utc).date()
            - timedelta(days=datetime.now(timezone.utc).weekday())
            - timedelta(weeks=1)
        )
        data = {
            "daily": {},
            "weekly": {last_monday.isoformat(): WEEKLY_CAP_GBP},
        }
        _tmp_budget_file.write_text(json.dumps(data))

        budget = check_budget()
        assert budget["weekly_spent"] == 0.0
        assert budget["weekly_remaining"] == pytest.approx(WEEKLY_CAP_GBP)
        assert budget["allowed"] is True

    def test_weekly_does_not_reset_mid_week(self, _tmp_budget_file):
        """Spending recorded on this week's Monday still counts."""
        now = datetime.now(timezone.utc)
        this_monday = (now.date() - timedelta(days=now.weekday())).isoformat()
        data = {
            "daily": {},
            "weekly": {this_monday: 5.0},
        }
        _tmp_budget_file.write_text(json.dumps(data))

        budget = check_budget()
        assert budget["weekly_spent"] == pytest.approx(5.0)
        assert budget["weekly_remaining"] == pytest.approx(WEEKLY_CAP_GBP - 5.0)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_load_missing_file_returns_defaults(self, _tmp_budget_file):
        data = _load_budget()
        assert data == {"daily": {}, "weekly": {}}

    def test_load_corrupt_file_returns_defaults(self, _tmp_budget_file):
        _tmp_budget_file.write_text("not valid json!!!")
        data = _load_budget()
        assert data == {"daily": {}, "weekly": {}}

    def test_save_and_load_roundtrip(self, _tmp_budget_file):
        original = {"daily": {"2025-01-01": 1.5}, "weekly": {"2025-01-01": 3.0}}
        _save_budget(original)
        loaded = _load_budget()
        assert loaded == original
