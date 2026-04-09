"""Tests for the user emulation agent (simulator package).

Covers:
- context_builder: source reading, git log, done-feedback fetch
- UserSimulatorAgent: happy path, budget exhaustion, JSON parse failure,
  deduplication skip, dry-run mode
- Persona harness: default persona, unknown persona fallback
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.agents.base import AgentInput, AgentOutput
from pipeline.simulator.context_builder import (
    _fetch_done_feedback,
    _git_log,
    _read_simulation_source,
    build_context,
)
from pipeline.simulator.persona import DEFAULT_PERSONA, PERSONAS, Persona
from pipeline.simulator.user_simulator import UserSimulatorAgent, _extract_json


# ── Persona tests ──────────────────────────────────────────────────────────────


def test_default_persona_in_personas_dict():
    assert "curious_explorer" in PERSONAS
    assert PERSONAS["curious_explorer"] is DEFAULT_PERSONA


def test_persona_has_required_fields():
    p = DEFAULT_PERSONA
    assert p.name
    assert p.description
    assert p.technical_level
    assert p.engagement_style


# ── context_builder: _read_simulation_source ──────────────────────────────────


def test_read_simulation_source_missing_files(tmp_path):
    result = _read_simulation_source(str(tmp_path))
    assert result == "(No simulation source files found)"


def test_read_simulation_source_reads_existing_files(tmp_path):
    sim_dir = tmp_path / "frontend" / "src" / "simulation"
    sim_dir.mkdir(parents=True)
    types_file = sim_dir / "types.ts"
    types_file.write_text("export type Species = 'plant' | 'herbivore' | 'predator';")

    result = _read_simulation_source(str(tmp_path))
    assert "types.ts" in result
    assert "Species" in result


def test_read_simulation_source_truncates_large_files(tmp_path):
    sim_dir = tmp_path / "frontend" / "src" / "simulation"
    sim_dir.mkdir(parents=True)
    big_content = "x" * 20_000
    (sim_dir / "types.ts").write_text(big_content)

    result = _read_simulation_source(str(tmp_path))
    assert "truncated" in result
    assert len(result) < 20_000


# ── context_builder: _git_log ──────────────────────────────────────────────────


def test_git_log_returns_string(tmp_path):
    result = _git_log(str(tmp_path), n=5)
    # Either log output or a fallback message — always a string
    assert isinstance(result, str)
    assert len(result) > 0


def test_git_log_fallback_on_missing_git(tmp_path):
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = _git_log(str(tmp_path))
    assert "unavailable" in result.lower()


# ── context_builder: _fetch_done_feedback ─────────────────────────────────────


def test_fetch_done_feedback_happy_path():
    fake_items = [
        {"reference": "LW-001", "content": "Add fish", "agent_notes": "Added fish species"},
        {"reference": "LW-002", "content": "More plants", "agent_notes": None},
    ]
    mock_response = httpx.Response(
        200,
        json=fake_items,
        request=httpx.Request("GET", "http://localhost:8000/api/feedback"),
    )
    with patch("httpx.get", return_value=mock_response):
        result = _fetch_done_feedback("http://localhost:8000", limit=10)

    assert "LW-001" in result
    assert "Add fish" in result
    assert "Added fish species" in result
    assert "LW-002" in result


def test_fetch_done_feedback_empty():
    mock_response = httpx.Response(
        200,
        json=[],
        request=httpx.Request("GET", "http://localhost:8000/api/feedback"),
    )
    with patch("httpx.get", return_value=mock_response):
        result = _fetch_done_feedback("http://localhost:8000")

    assert "No completed" in result


def test_fetch_done_feedback_api_unavailable():
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        result = _fetch_done_feedback("http://localhost:8000")
    assert "unavailable" in result.lower()


# ── context_builder: build_context ────────────────────────────────────────────


def test_build_context_returns_all_keys(tmp_path):
    with (
        patch("pipeline.simulator.context_builder._git_log", return_value="git log"),
        patch(
            "pipeline.simulator.context_builder._fetch_done_feedback",
            return_value="done feedback",
        ),
    ):
        ctx = build_context(str(tmp_path), "http://localhost:8000")

    assert "source_summary" in ctx
    assert "recent_changes" in ctx
    assert "recently_completed" in ctx
    assert ctx["recent_changes"] == "git log"
    assert ctx["recently_completed"] == "done feedback"


# ── _extract_json ──────────────────────────────────────────────────────────────


def test_extract_json_clean():
    raw = '{"feedback_items": ["a", "b"], "reasoning": "test"}'
    result = _extract_json(raw)
    assert result == {"feedback_items": ["a", "b"], "reasoning": "test"}


def test_extract_json_with_markdown_fence():
    raw = '```json\n{"feedback_items": ["a"], "reasoning": "r"}\n```'
    result = _extract_json(raw)
    assert result is not None
    assert result["feedback_items"] == ["a"]


def test_extract_json_invalid():
    assert _extract_json("not json at all") is None


# ── UserSimulatorAgent ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _tmp_budget(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.budget.BUDGET_FILE", tmp_path / "budget.json")


@pytest.fixture(autouse=True)
def _tmp_trace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "pipeline.simulator.user_simulator._TRACE_DIR", tmp_path / "simulator"
    )


def _make_input(n=2, dry_run=True, persona="curious_explorer"):
    return AgentInput(
        data={
            "n_items": n,
            "persona_name": persona,
            "api_base_url": "http://localhost:8000",
            "repo_path": ".",
            "dry_run": dry_run,
        },
        context={"writer_model": "claude-test", "ollama_url": "http://localhost:11434"},
    )


def _mock_anthropic_response(items: list[str], reasoning: str = "test reasoning"):
    """Build a minimal mock for anthropic.Anthropic().messages.create()."""
    content_text = json.dumps({"feedback_items": items, "reasoning": reasoning})
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=content_text)]
    mock_message.usage.input_tokens = 100
    mock_message.usage.output_tokens = 50
    return mock_message


def test_agent_happy_path_dry_run():
    agent = UserSimulatorAgent()
    mock_msg = _mock_anthropic_response(["Add more plants", "Predators move oddly"])

    with (
        patch("pipeline.simulator.user_simulator.anthropic") as mock_anthropic,
        patch("pipeline.simulator.context_builder._git_log", return_value="log"),
        patch(
            "pipeline.simulator.context_builder._fetch_done_feedback",
            return_value="none",
        ),
        patch("pipeline.simulator.context_builder._read_simulation_source", return_value="src"),
        patch.object(agent, "_check_duplicate", return_value=None),
    ):
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_msg
        result = agent.run(_make_input(n=2, dry_run=True))

    assert result.success
    assert result.tokens_used == 150
    assert len(result.data["submitted"]) == 2
    assert result.data["dry_run"] is True


def test_agent_deduplication_skips_similar_items():
    agent = UserSimulatorAgent()
    mock_msg = _mock_anthropic_response(["Add fish", "More trees"])

    with (
        patch("pipeline.simulator.user_simulator.anthropic") as mock_anthropic,
        patch("pipeline.simulator.context_builder._git_log", return_value="log"),
        patch(
            "pipeline.simulator.context_builder._fetch_done_feedback",
            return_value="none",
        ),
        patch("pipeline.simulator.context_builder._read_simulation_source", return_value="src"),
        patch.object(
            agent,
            "_check_duplicate",
            side_effect=["Too similar to LW-001", None],
        ),
    ):
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_msg
        result = agent.run(_make_input(n=2, dry_run=True))

    assert result.success
    assert len(result.data["submitted"]) == 1
    assert len(result.data["skipped"]) == 1
    assert result.data["submitted"][0] == "More trees"


def test_agent_budget_exhausted():
    from pipeline.budget import DAILY_CAP_GBP, WEEKLY_CAP_GBP, record_usage

    # Exhaust the budget.
    tokens_to_exhaust = int(DAILY_CAP_GBP / 0.000012) + 1
    record_usage(tokens_to_exhaust)

    agent = UserSimulatorAgent()
    result = agent.run(_make_input())

    assert result.success  # Graceful — not a failure
    assert "Budget exhausted" in result.message
    assert result.tokens_used == 0


def test_agent_unparseable_response():
    agent = UserSimulatorAgent()
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="not valid json at all")]
    mock_msg.usage.input_tokens = 50
    mock_msg.usage.output_tokens = 20

    with (
        patch("pipeline.simulator.user_simulator.anthropic") as mock_anthropic,
        patch("pipeline.simulator.context_builder._git_log", return_value="log"),
        patch(
            "pipeline.simulator.context_builder._fetch_done_feedback",
            return_value="none",
        ),
        patch("pipeline.simulator.context_builder._read_simulation_source", return_value="src"),
    ):
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_msg
        result = agent.run(_make_input(dry_run=True))

    assert not result.success
    assert "parse" in result.message.lower()


def test_agent_unknown_persona_falls_back_to_default():
    agent = UserSimulatorAgent()
    mock_msg = _mock_anthropic_response(["Something"])

    with (
        patch("pipeline.simulator.user_simulator.anthropic") as mock_anthropic,
        patch("pipeline.simulator.context_builder._git_log", return_value="log"),
        patch(
            "pipeline.simulator.context_builder._fetch_done_feedback",
            return_value="none",
        ),
        patch("pipeline.simulator.context_builder._read_simulation_source", return_value="src"),
        patch.object(agent, "_check_duplicate", return_value=None),
    ):
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_msg
        inp = AgentInput(
            data={
                "n_items": 1,
                "persona_name": "nonexistent_persona",
                "api_base_url": "http://localhost:8000",
                "repo_path": ".",
                "dry_run": True,
            },
            context={"writer_model": "claude-test", "ollama_url": "http://localhost:11434"},
        )
        result = agent.run(inp)

    # Should not crash — falls back to DEFAULT_PERSONA
    assert result.success
    assert result.data["persona"] == DEFAULT_PERSONA.name


def test_agent_anthropic_unavailable():
    agent = UserSimulatorAgent()

    with patch("pipeline.simulator.user_simulator.anthropic", None):
        result = agent.run(_make_input())

    assert not result.success
    assert "anthropic" in result.message.lower()
