"""Tests for the prioritiser agent with mocked Ollama and budget."""

import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.agents.base import AgentInput, AgentOutput  # noqa: E402
from pipeline.agents.prioritiser_agent import PrioritiserAgent  # noqa: E402
from pipeline.budget import DAILY_CAP_GBP, WEEKLY_CAP_GBP  # noqa: E402


@pytest.fixture(autouse=True)
def _tmp_budget_file(tmp_path, monkeypatch):
    """Point budget file at a temp path for every test."""
    budget_file = tmp_path / "budget.json"
    monkeypatch.setattr("pipeline.budget.BUDGET_FILE", budget_file)


@pytest.fixture()
def agent():
    return PrioritiserAgent()


def _make_input(clusters: list[dict] | None, ollama_url: str = "http://localhost:11434") -> AgentInput:
    return AgentInput(data=clusters, context={"ollama_url": ollama_url})


def _ollama_summary_response(summary: str, eval_count: int = 200, prompt_eval_count: int = 100) -> httpx.Response:
    """Build a fake Ollama /api/chat response with token counts."""
    return httpx.Response(
        200,
        json={
            "message": {"content": summary},
            "eval_count": eval_count,
            "prompt_eval_count": prompt_eval_count,
        },
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )


SAMPLE_CLUSTER = {
    "references": ["LW-001", "LW-002"],
    "documents": ["Add fish to the lake", "More aquatic life please"],
}


# ---------------------------------------------------------------------------
# Empty / no-op cases
# ---------------------------------------------------------------------------


class TestPrioritiserAgentEmpty:
    def test_none_input_returns_empty(self, agent):
        result = agent.run(_make_input(None))
        assert isinstance(result, AgentOutput)
        assert result.success is True
        assert result.data["tasks"] == []

    def test_empty_list_returns_empty(self, agent):
        result = agent.run(_make_input([]))
        assert result.success is True
        assert result.data["tasks"] == []


# ---------------------------------------------------------------------------
# Summarisation with mocked Ollama
# ---------------------------------------------------------------------------


class TestPrioritiserSummarisation:
    def test_summarises_single_cluster(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_summary_response("Add aquatic wildlife to the lake")
            result = agent.run(_make_input([SAMPLE_CLUSTER]))

        assert result.success is True
        tasks = result.data["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["summary"] == "Add aquatic wildlife to the lake"
        assert tasks[0]["references"] == ["LW-001", "LW-002"]
        assert tasks[0]["cluster_size"] == 2

    def test_summarises_multiple_clusters(self, agent):
        cluster_2 = {
            "references": ["LW-003"],
            "documents": ["Change the colour scheme"],
        }
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.side_effect = [
                _ollama_summary_response("Add aquatic wildlife"),
                _ollama_summary_response("Update visual theme"),
            ]
            result = agent.run(_make_input([SAMPLE_CLUSTER, cluster_2]))

        tasks = result.data["tasks"]
        assert len(tasks) == 2
        assert tasks[0]["summary"] == "Add aquatic wildlife"
        assert tasks[1]["summary"] == "Update visual theme"

    def test_tracks_token_usage(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_summary_response("Summary", eval_count=150, prompt_eval_count=50)
            result = agent.run(_make_input([SAMPLE_CLUSTER]))

        assert result.tokens_used == 200  # 150 + 50

    def test_sends_documents_in_prompt(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_summary_response("Summary")
            agent.run(_make_input([SAMPLE_CLUSTER]))

        payload = mock_post.call_args.kwargs["json"]
        user_msg = payload["messages"][0]["content"]
        assert "Add fish to the lake" in user_msg
        assert "More aquatic life please" in user_msg


# ---------------------------------------------------------------------------
# Ollama unavailable fallback
# ---------------------------------------------------------------------------


class TestPrioritiserOllamaUnavailable:
    def test_connection_error_uses_fallback_summary(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            result = agent.run(_make_input([SAMPLE_CLUSTER]))

        assert result.success is True
        tasks = result.data["tasks"]
        assert len(tasks) == 1
        assert "2" in tasks[0]["summary"]  # mentions the count
        assert result.tokens_used == 0

    def test_timeout_uses_fallback_summary(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ReadTimeout("Timed out")
            result = agent.run(_make_input([SAMPLE_CLUSTER]))

        tasks = result.data["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["references"] == ["LW-001", "LW-002"]


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


class TestPrioritiserBudget:
    def test_skips_all_when_budget_exhausted(self, agent):
        with patch("pipeline.agents.prioritiser_agent.check_budget") as mock_budget:
            mock_budget.return_value = {
                "daily_spent": DAILY_CAP_GBP,
                "daily_remaining": 0.0,
                "daily_cap": DAILY_CAP_GBP,
                "weekly_spent": DAILY_CAP_GBP,
                "weekly_remaining": WEEKLY_CAP_GBP - DAILY_CAP_GBP,
                "weekly_cap": WEEKLY_CAP_GBP,
                "allowed": False,
            }
            result = agent.run(_make_input([SAMPLE_CLUSTER]))

        assert result.success is True
        assert result.data["tasks"] == []
        assert "exhausted" in result.message.lower()

    def test_stops_summarising_when_daily_budget_low(self, agent):
        """When budget drops too low mid-run, stop processing further clusters."""
        cluster_2 = {
            "references": ["LW-003"],
            "documents": ["Change colours"],
        }

        call_count = [0]

        def budget_side_effect():
            call_count[0] += 1
            if call_count[0] <= 2:
                # First two calls (initial guard + first loop check): budget OK.
                return {
                    "daily_spent": 0.0,
                    "daily_remaining": DAILY_CAP_GBP,
                    "daily_cap": DAILY_CAP_GBP,
                    "weekly_spent": 0.0,
                    "weekly_remaining": WEEKLY_CAP_GBP,
                    "weekly_cap": WEEKLY_CAP_GBP,
                    "allowed": True,
                }
            else:
                # Third call (second loop check): budget near-zero.
                return {
                    "daily_spent": DAILY_CAP_GBP,
                    "daily_remaining": 0.0001,
                    "daily_cap": DAILY_CAP_GBP,
                    "weekly_spent": DAILY_CAP_GBP,
                    "weekly_remaining": WEEKLY_CAP_GBP - DAILY_CAP_GBP,
                    "weekly_cap": WEEKLY_CAP_GBP,
                    "allowed": True,
                }

        with patch("pipeline.agents.prioritiser_agent.check_budget", side_effect=budget_side_effect):
            with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
                mock_post.return_value = _ollama_summary_response("Summary")
                with patch("pipeline.agents.prioritiser_agent.record_usage"):
                    result = agent.run(_make_input([SAMPLE_CLUSTER, cluster_2]))

        # Only the first cluster should have been summarised.
        assert len(result.data["tasks"]) == 1


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


class TestPrioritiserOutput:
    def test_task_has_required_keys(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_summary_response("Summary")
            result = agent.run(_make_input([SAMPLE_CLUSTER]))

        task = result.data["tasks"][0]
        assert "references" in task
        assert "documents" in task
        assert "summary" in task
        assert "cluster_size" in task
