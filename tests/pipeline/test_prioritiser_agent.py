"""Tests for the prioritiser agent with mocked Ollama and budget."""

import json
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


def _make_input(clusters, ollama_url: str = "http://localhost:11434") -> AgentInput:
    return AgentInput(data=clusters, context={"ollama_url": ollama_url})


def _ollama_rank_response(ranking: list[int]) -> httpx.Response:
    """Build a fake Ollama /api/chat response containing a ranking array."""
    return httpx.Response(
        200,
        json={
            "message": {"content": json.dumps(ranking)},
            "eval_count": 20,
            "prompt_eval_count": 10,
        },
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )


CLUSTER_A = {
    "references": ["LW-001"],
    "documents": ["Add fish to the lake"],
}
CLUSTER_B = {
    "references": ["LW-002", "LW-003"],
    "documents": ["Change colour scheme", "Darker colours please"],
}
CLUSTER_C = {
    "references": ["LW-004", "LW-005", "LW-006"],
    "documents": ["Make it faster", "Performance is slow", "Speed up loading"],
}


# ---------------------------------------------------------------------------
# Empty / no-op cases
# ---------------------------------------------------------------------------


class TestPrioritiserAgentEmpty:
    def test_none_input_returns_empty(self, agent):
        result = agent.run(_make_input(None))
        assert isinstance(result, AgentOutput)
        assert result.success is True
        assert result.data["clusters"] == []

    def test_empty_list_returns_empty(self, agent):
        result = agent.run(_make_input([]))
        assert result.success is True
        assert result.data["clusters"] == []


# ---------------------------------------------------------------------------
# Single cluster — no LLM call
# ---------------------------------------------------------------------------


class TestPrioritiserSingleCluster:
    def test_single_cluster_returned_without_llm_call(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            result = agent.run(_make_input([CLUSTER_A]))

        assert result.success is True
        assert result.data["clusters"] == [CLUSTER_A]
        mock_post.assert_not_called()

    def test_single_cluster_uses_zero_tokens(self, agent):
        result = agent.run(_make_input([CLUSTER_A]))
        assert result.tokens_used == 0


# ---------------------------------------------------------------------------
# Ordering via mocked Ollama
# ---------------------------------------------------------------------------


class TestPrioritiserOrdering:
    def test_reorders_clusters_per_ollama_ranking(self, agent):
        """Ollama says [2, 0, 1] → cluster C, A, B."""
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_rank_response([2, 0, 1])
            result = agent.run(_make_input([CLUSTER_A, CLUSTER_B, CLUSTER_C]))

        clusters = result.data["clusters"]
        assert clusters[0] is CLUSTER_C
        assert clusters[1] is CLUSTER_A
        assert clusters[2] is CLUSTER_B

    def test_all_clusters_preserved_when_ranked(self, agent):
        """All clusters appear in the output regardless of ranking."""
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_rank_response([1, 0])
            result = agent.run(_make_input([CLUSTER_A, CLUSTER_B]))

        assert len(result.data["clusters"]) == 2

    def test_unmentioned_clusters_appended_at_end(self, agent):
        """If Ollama omits an index, that cluster is appended at the end."""
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            # Only ranks 0 and 2, omits 1 (CLUSTER_B).
            mock_post.return_value = _ollama_rank_response([2, 0])
            result = agent.run(_make_input([CLUSTER_A, CLUSTER_B, CLUSTER_C]))

        clusters = result.data["clusters"]
        assert clusters[0] is CLUSTER_C
        assert clusters[1] is CLUSTER_A
        assert clusters[2] is CLUSTER_B  # appended at end

    def test_sends_cluster_info_in_prompt(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_rank_response([1, 0])
            agent.run(_make_input([CLUSTER_A, CLUSTER_B]))

        payload = mock_post.call_args.kwargs["json"]
        user_msg = payload["messages"][0]["content"]
        assert "Add fish to the lake" in user_msg
        assert "Change colour scheme" in user_msg


# ---------------------------------------------------------------------------
# Ollama unavailable — size-based fallback
# ---------------------------------------------------------------------------


class TestPrioritiserOllamaUnavailable:
    def test_connection_error_falls_back_to_size_order(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            result = agent.run(_make_input([CLUSTER_A, CLUSTER_B, CLUSTER_C]))

        assert result.success is True
        clusters = result.data["clusters"]
        # Falls back to size order: C (3), B (2), A (1).
        assert clusters[0] is CLUSTER_C
        assert clusters[1] is CLUSTER_B
        assert clusters[2] is CLUSTER_A

    def test_unparseable_response_falls_back_to_size_order(self, agent):
        bad_response = httpx.Response(
            200,
            json={"message": {"content": "I think you should do the biggest one first."}},
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.return_value = bad_response
            result = agent.run(_make_input([CLUSTER_A, CLUSTER_B, CLUSTER_C]))

        clusters = result.data["clusters"]
        assert clusters[0] is CLUSTER_C

    def test_uses_zero_tokens(self, agent):
        with patch("pipeline.agents.prioritiser_agent.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("down")
            result = agent.run(_make_input([CLUSTER_A, CLUSTER_B]))

        assert result.tokens_used == 0


# ---------------------------------------------------------------------------
# Budget exhausted
# ---------------------------------------------------------------------------


class TestPrioritiserBudget:
    def test_budget_exhausted_falls_back_to_size_order(self, agent):
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
            result = agent.run(_make_input([CLUSTER_A, CLUSTER_B]))

        assert result.success is True
        # Falls back to size order: B (2) before A (1).
        clusters = result.data["clusters"]
        assert clusters[0] is CLUSTER_B
        assert clusters[1] is CLUSTER_A


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


class TestPrioritiserOutput:
    def test_output_has_clusters_key(self, agent):
        result = agent.run(_make_input([CLUSTER_A]))
        assert "clusters" in result.data

    def test_clusters_are_list(self, agent):
        result = agent.run(_make_input([CLUSTER_A]))
        assert isinstance(result.data["clusters"], list)

    def test_uses_zero_tokens(self, agent):
        result = agent.run(_make_input([CLUSTER_A]))
        assert result.tokens_used == 0
