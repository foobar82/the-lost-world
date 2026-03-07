"""Tests for the ThemeAgent with mocked Ollama and budget."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.agents.base import AgentInput, AgentOutput  # noqa: E402
from pipeline.agents.theme_agent import ThemeAgent, _extract_json, _fallback_themes  # noqa: E402
from pipeline.budget import DAILY_CAP_GBP, WEEKLY_CAP_GBP  # noqa: E402


@pytest.fixture(autouse=True)
def _tmp_budget_file(tmp_path, monkeypatch):
    """Point budget file at a temp path for every test."""
    budget_file = tmp_path / "budget.json"
    monkeypatch.setattr("pipeline.budget.BUDGET_FILE", budget_file)


@pytest.fixture()
def agent():
    return ThemeAgent()


def _make_input(clusters, ollama_url: str = "http://localhost:11434") -> AgentInput:
    return AgentInput(data=clusters, context={"ollama_url": ollama_url})


def _ollama_themes_response(themes: list[dict], eval_count: int = 300, prompt_eval_count: int = 150) -> httpx.Response:
    """Build a fake Ollama /api/chat response containing a themes JSON payload."""
    content = json.dumps({"themes": themes})
    return httpx.Response(
        200,
        json={
            "message": {"content": content},
            "eval_count": eval_count,
            "prompt_eval_count": prompt_eval_count,
        },
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )


CLUSTER_COLOUR_BROWN = {
    "references": ["LW-001"],
    "documents": ["Make the background brown"],
}
CLUSTER_COLOUR_GREY = {
    "references": ["LW-002"],
    "documents": ["Make the background grey"],
}
CLUSTER_CONTRAST = {
    "references": ["LW-003"],
    "documents": ["More visual contrast please"],
}
CLUSTER_FISH = {
    "references": ["LW-004", "LW-005"],
    "documents": ["Add fish to the lake", "More aquatic life please"],
}

SYNTHESIZED_COLOUR_THEME = {
    "title": "Configurable background colour",
    "rationale": "Users want control over the background colour",
    "conflicting_signals": ["Make the background brown", "Make the background grey"],
    "references": ["LW-001", "LW-002", "LW-003"],
    "documents": [
        "Make the background brown",
        "Make the background grey",
        "More visual contrast please",
    ],
}

FISH_THEME = {
    "title": "Aquatic life in the lake",
    "rationale": "Users want more aquatic creatures",
    "conflicting_signals": [],
    "references": ["LW-004", "LW-005"],
    "documents": ["Add fish to the lake", "More aquatic life please"],
}


# ---------------------------------------------------------------------------
# Empty / no-op cases
# ---------------------------------------------------------------------------


class TestThemeAgentEmpty:
    def test_none_input_returns_empty(self, agent):
        result = agent.run(_make_input(None))
        assert isinstance(result, AgentOutput)
        assert result.success is True
        assert result.data["themes"] == []
        assert result.tokens_used == 0

    def test_empty_list_returns_empty(self, agent):
        result = agent.run(_make_input([]))
        assert result.success is True
        assert result.data["themes"] == []


# ---------------------------------------------------------------------------
# Happy path — LLM synthesizes themes
# ---------------------------------------------------------------------------


class TestThemeAgentHappyPath:
    def test_single_cluster_passes_through(self, agent):
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_themes_response([FISH_THEME])
            result = agent.run(_make_input([CLUSTER_FISH]))

        assert result.success is True
        themes = result.data["themes"]
        assert len(themes) == 1
        assert themes[0]["title"] == "Configurable background colour" or themes[0]["title"] == "Aquatic life in the lake"

    def test_conflicting_clusters_merged_into_one_theme(self, agent):
        """Brown + grey + contrast clusters should merge into one configurable theme."""
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_themes_response([SYNTHESIZED_COLOUR_THEME])
            result = agent.run(
                _make_input([CLUSTER_COLOUR_BROWN, CLUSTER_COLOUR_GREY, CLUSTER_CONTRAST])
            )

        themes = result.data["themes"]
        assert len(themes) == 1
        assert themes[0]["title"] == "Configurable background colour"
        assert len(themes[0]["conflicting_signals"]) == 2
        assert set(themes[0]["references"]) == {"LW-001", "LW-002", "LW-003"}

    def test_multiple_distinct_themes_preserved(self, agent):
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_themes_response(
                [SYNTHESIZED_COLOUR_THEME, FISH_THEME]
            )
            result = agent.run(
                _make_input([CLUSTER_COLOUR_BROWN, CLUSTER_COLOUR_GREY, CLUSTER_FISH])
            )

        themes = result.data["themes"]
        assert len(themes) == 2

    def test_token_usage_reported(self, agent):
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_themes_response(
                [FISH_THEME], eval_count=200, prompt_eval_count=100
            )
            result = agent.run(_make_input([CLUSTER_FISH]))

        assert result.tokens_used == 300  # 200 + 100

    def test_all_clusters_included_in_prompt(self, agent):
        """All feedback documents should appear in the Ollama request."""
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_themes_response([FISH_THEME])
            agent.run(_make_input([CLUSTER_COLOUR_BROWN, CLUSTER_FISH]))

        payload = mock_post.call_args.kwargs["json"]
        combined = " ".join(
            m["content"] for m in payload["messages"]
        )
        assert "Make the background brown" in combined
        assert "Add fish to the lake" in combined


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_plain_json(self):
        text = '{"themes": []}'
        assert _extract_json(text) == {"themes": []}

    def test_strips_markdown_fences(self):
        text = "```json\n{\"themes\": []}\n```"
        assert _extract_json(text) == {"themes": []}

    def test_strips_bare_fences(self):
        text = "```\n{\"themes\": []}\n```"
        assert _extract_json(text) == {"themes": []}

    def test_invalid_json_returns_none(self):
        assert _extract_json("not json at all") is None

    def test_empty_string_returns_none(self):
        assert _extract_json("") is None


# ---------------------------------------------------------------------------
# Fallback helper
# ---------------------------------------------------------------------------


class TestFallbackThemes:
    def test_one_theme_per_cluster(self):
        clusters = [CLUSTER_FISH, CLUSTER_COLOUR_BROWN]
        themes = _fallback_themes(clusters)
        assert len(themes) == 2

    def test_references_preserved(self):
        themes = _fallback_themes([CLUSTER_FISH])
        assert themes[0]["references"] == ["LW-004", "LW-005"]

    def test_documents_preserved(self):
        themes = _fallback_themes([CLUSTER_FISH])
        assert themes[0]["documents"] == CLUSTER_FISH["documents"]

    def test_extra_fields_empty(self):
        themes = _fallback_themes([CLUSTER_FISH])
        assert themes[0]["title"] != ""  # has a default title
        assert themes[0]["rationale"] == ""
        assert themes[0]["conflicting_signals"] == []


# ---------------------------------------------------------------------------
# Ollama unavailable — fallback to raw clusters
# ---------------------------------------------------------------------------


class TestThemeAgentOllamaUnavailable:
    def test_connection_error_falls_back(self, agent):
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            result = agent.run(_make_input([CLUSTER_FISH, CLUSTER_COLOUR_BROWN]))

        assert result.success is True
        themes = result.data["themes"]
        assert len(themes) == 2  # one per input cluster
        assert result.tokens_used == 0

    def test_timeout_falls_back(self, agent):
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ReadTimeout("Timed out")
            result = agent.run(_make_input([CLUSTER_FISH]))

        assert result.success is True
        assert len(result.data["themes"]) == 1
        assert result.data["themes"][0]["references"] == ["LW-004", "LW-005"]

    def test_malformed_json_response_falls_back(self, agent):
        bad_response = httpx.Response(
            200,
            json={"message": {"content": "Sorry, I cannot help with that."}},
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.return_value = bad_response
            result = agent.run(_make_input([CLUSTER_FISH]))

        assert result.success is True
        # Falls back: still returns one theme per cluster
        assert len(result.data["themes"]) == 1

    def test_themes_key_missing_falls_back(self, agent):
        bad_response = httpx.Response(
            200,
            json={"message": {"content": '{"something_else": []}'}},
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.return_value = bad_response
            result = agent.run(_make_input([CLUSTER_FISH]))

        assert result.success is True
        assert len(result.data["themes"]) == 1


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


class TestThemeAgentBudget:
    def test_skips_llm_when_budget_exhausted(self, agent):
        with patch("pipeline.agents.theme_agent.check_budget") as mock_budget:
            mock_budget.return_value = {
                "daily_spent": DAILY_CAP_GBP,
                "daily_remaining": 0.0,
                "daily_cap": DAILY_CAP_GBP,
                "weekly_spent": DAILY_CAP_GBP,
                "weekly_remaining": WEEKLY_CAP_GBP - DAILY_CAP_GBP,
                "weekly_cap": WEEKLY_CAP_GBP,
                "allowed": False,
            }
            with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
                result = agent.run(_make_input([CLUSTER_FISH]))

        # Should not call Ollama at all.
        mock_post.assert_not_called()
        # Falls back to raw cluster themes.
        assert result.success is True
        assert len(result.data["themes"]) == 1
        assert result.tokens_used == 0


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


class TestThemeAgentOutput:
    def test_theme_has_required_keys(self, agent):
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_themes_response([FISH_THEME])
            result = agent.run(_make_input([CLUSTER_FISH]))

        theme = result.data["themes"][0]
        assert "title" in theme
        assert "rationale" in theme
        assert "conflicting_signals" in theme
        assert "references" in theme
        assert "documents" in theme

    def test_agent_name(self, agent):
        assert agent.name == "theme"

    def test_malformed_theme_entry_dropped(self, agent):
        """Themes missing references/documents should be silently dropped."""
        bad_themes = [
            {"title": "No refs here"},  # missing references + documents
            FISH_THEME,
        ]
        with patch("pipeline.agents.theme_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_themes_response(bad_themes)
            result = agent.run(_make_input([CLUSTER_FISH, CLUSTER_COLOUR_BROWN]))

        # Only the valid theme should remain.
        themes = result.data["themes"]
        assert len(themes) == 1
        assert themes[0]["title"] == FISH_THEME["title"]
