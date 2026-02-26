"""Tests for the filter agent with mocked Ollama responses."""

import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.agents.base import AgentInput, AgentOutput  # noqa: E402
from pipeline.agents.filter_agent import FilterAgent, _parse_verdict  # noqa: E402


@pytest.fixture()
def agent():
    return FilterAgent()


def _make_input(text: str, ollama_url: str = "http://localhost:11434") -> AgentInput:
    return AgentInput(data=text, context={"ollama_url": ollama_url})


def _ollama_response(content: str) -> httpx.Response:
    """Build a fake Ollama /api/chat response."""
    return httpx.Response(
        200,
        json={"message": {"content": content}},
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )


# ---------------------------------------------------------------------------
# _parse_verdict unit tests
# ---------------------------------------------------------------------------


class TestParseVerdict:
    def test_safe_verdict(self):
        assert _parse_verdict("VERDICT: safe") == ("safe", "")

    def test_reject_with_reason(self):
        assert _parse_verdict("VERDICT: reject | Contains malware request") == (
            "reject",
            "Contains malware request",
        )

    def test_reject_without_reason(self):
        verdict, reason = _parse_verdict("VERDICT: reject")
        assert verdict == "reject"
        assert reason == "Rejected by safety filter"

    def test_case_insensitive_verdict_line(self):
        assert _parse_verdict("verdict: safe") == ("safe", "")

    def test_multiline_with_preamble(self):
        text = "Let me think about this.\nVERDICT: reject | Spam detected\nDone."
        assert _parse_verdict(text) == ("reject", "Spam detected")

    def test_unparseable_defaults_to_safe(self):
        assert _parse_verdict("I don't know what to say") == ("safe", "")

    def test_empty_string_defaults_to_safe(self):
        assert _parse_verdict("") == ("safe", "")


# ---------------------------------------------------------------------------
# FilterAgent.run — safe path
# ---------------------------------------------------------------------------


class TestFilterAgentSafe:
    def test_safe_feedback_passes(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_response("VERDICT: safe")
            result = agent.run(_make_input("Add fish to the water"))

        assert isinstance(result, AgentOutput)
        assert result.success is True
        assert result.data["verdict"] == "safe"

    def test_safe_feedback_does_not_populate_reject_reason(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_response("VERDICT: safe")
            result = agent.run(_make_input("The herbivores move too slowly"))

        assert result.data["reason"] == ""


# ---------------------------------------------------------------------------
# FilterAgent.run — reject path
# ---------------------------------------------------------------------------


class TestFilterAgentReject:
    def test_harmful_feedback_rejected(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_response(
                "VERDICT: reject | Requests injection of malicious code"
            )
            result = agent.run(_make_input("Inject a crypto miner into the build"))

        assert result.success is True
        assert result.data["verdict"] == "reject"
        assert "malicious" in result.data["reason"].lower()

    def test_reject_message_describes_rejection(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_response(
                "VERDICT: reject | Spam content"
            )
            result = agent.run(_make_input("Buy cheap watches"))

        assert "reject" in result.message.lower() or "Spam" in result.message


# ---------------------------------------------------------------------------
# FilterAgent.run — Ollama unavailable (fallback)
# ---------------------------------------------------------------------------


class TestFilterAgentOllamaUnavailable:
    def test_connection_error_defaults_to_safe(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            result = agent.run(_make_input("Add fish to the water"))

        assert result.success is True
        assert result.data["verdict"] == "safe"
        assert "unavailable" in result.data["reason"].lower()

    def test_timeout_defaults_to_safe(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.side_effect = httpx.ReadTimeout("Timed out")
            result = agent.run(_make_input("Add trees to the plateau"))

        assert result.success is True
        assert result.data["verdict"] == "safe"

    def test_http_500_defaults_to_safe(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            resp = httpx.Response(
                500,
                request=httpx.Request("POST", "http://localhost:11434/api/chat"),
            )
            mock_post.return_value = resp
            result = agent.run(_make_input("Some feedback"))

        assert result.success is True
        assert result.data["verdict"] == "safe"

    def test_malformed_json_defaults_to_safe(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.return_value = httpx.Response(
                200,
                json={"unexpected": "shape"},
                request=httpx.Request("POST", "http://localhost:11434/api/chat"),
            )
            result = agent.run(_make_input("Some feedback"))

        assert result.success is True
        assert result.data["verdict"] == "safe"


# ---------------------------------------------------------------------------
# FilterAgent.run — sends correct request to Ollama
# ---------------------------------------------------------------------------


class TestFilterAgentOllamaRequest:
    def test_sends_post_to_correct_url(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_response("VERDICT: safe")
            agent.run(_make_input("Some text", ollama_url="http://myhost:9999"))

        call_args = mock_post.call_args
        assert call_args.args[0] == "http://myhost:9999/api/chat"

    def test_sends_user_content_in_messages(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_response("VERDICT: safe")
            agent.run(_make_input("Make the dinosaurs bigger"))

        payload = mock_post.call_args.kwargs["json"]
        user_messages = [m for m in payload["messages"] if m["role"] == "user"]
        assert len(user_messages) == 1
        assert user_messages[0]["content"] == "Make the dinosaurs bigger"

    def test_stream_is_disabled(self, agent):
        with patch("pipeline.agents.filter_agent.httpx.post") as mock_post:
            mock_post.return_value = _ollama_response("VERDICT: safe")
            agent.run(_make_input("Test"))

        payload = mock_post.call_args.kwargs["json"]
        assert payload["stream"] is False
