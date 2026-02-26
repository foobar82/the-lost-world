"""Tests for the reviewer agent with mocked Anthropic API responses."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.agents.base import AgentInput, AgentOutput  # noqa: E402
from pipeline.agents.reviewer_agent import (  # noqa: E402
    ReviewerAgent,
    _format_changes_for_review,
    _parse_reviewer_response,
    _read_contract,
)


@pytest.fixture()
def agent():
    return ReviewerAgent()


@pytest.fixture()
def tmp_repo(tmp_path):
    """Create a minimal repo with a contract file."""
    (tmp_path / "contract.md").write_text("No breaking changes allowed.")
    return str(tmp_path)


def _make_input(writer_data, repo_path=".", **extra_context):
    context = {"repo_path": repo_path}
    context.update(extra_context)
    return AgentInput(data=writer_data, context=context)


def _sample_changes():
    return [
        {"path": "src/main.py", "action": "modify",
         "content": "print('updated')"},
    ]


def _anthropic_response(verdict, comments="", issues=None,
                        input_tokens=80, output_tokens=150):
    """Build a mock Anthropic API response."""
    response_data = {
        "verdict": verdict,
        "comments": comments,
        "issues": issues or [],
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(response_data))]
    mock_response.usage = MagicMock(
        input_tokens=input_tokens, output_tokens=output_tokens,
    )
    return mock_response


# ---------------------------------------------------------------------------
# _parse_reviewer_response
# ---------------------------------------------------------------------------


class TestParseReviewerResponse:
    def test_parses_approve(self):
        data = {"verdict": "approve", "comments": "LGTM", "issues": []}
        result = _parse_reviewer_response(json.dumps(data))
        assert result["verdict"] == "approve"
        assert result["comments"] == "LGTM"
        assert result["issues"] == []

    def test_parses_reject_with_issues(self):
        data = {
            "verdict": "reject",
            "comments": "Security issue found",
            "issues": [
                {"file": "main.py", "description": "SQL injection risk"},
            ],
        }
        result = _parse_reviewer_response(json.dumps(data))
        assert result["verdict"] == "reject"
        assert len(result["issues"]) == 1
        assert result["issues"][0]["file"] == "main.py"

    def test_strips_markdown_fences(self):
        data = {"verdict": "approve", "comments": "OK", "issues": []}
        wrapped = f"```json\n{json.dumps(data)}\n```"
        result = _parse_reviewer_response(wrapped)
        assert result["verdict"] == "approve"

    def test_invalid_verdict_defaults_to_reject(self):
        data = {"verdict": "maybe", "comments": "Unsure", "issues": []}
        result = _parse_reviewer_response(json.dumps(data))
        assert result["verdict"] == "reject"

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_reviewer_response("not json")

    def test_missing_issues_defaults_to_empty(self):
        data = {"verdict": "approve", "comments": "Fine"}
        result = _parse_reviewer_response(json.dumps(data))
        assert result["issues"] == []


# ---------------------------------------------------------------------------
# _format_changes_for_review
# ---------------------------------------------------------------------------


class TestFormatChangesForReview:
    def test_formats_modify(self):
        changes = [{"path": "a.py", "action": "modify", "content": "new code"}]
        result = _format_changes_for_review(changes)
        assert "MODIFY" in result
        assert "a.py" in result
        assert "new code" in result

    def test_formats_delete(self):
        changes = [{"path": "old.py", "action": "delete", "content": ""}]
        result = _format_changes_for_review(changes)
        assert "DELETE" in result
        assert "old.py" in result
        assert "deleted" in result.lower()

    def test_formats_multiple_changes(self):
        changes = [
            {"path": "a.py", "action": "create", "content": "new"},
            {"path": "b.py", "action": "modify", "content": "updated"},
        ]
        result = _format_changes_for_review(changes)
        assert "a.py" in result
        assert "b.py" in result


# ---------------------------------------------------------------------------
# ReviewerAgent.run — approval
# ---------------------------------------------------------------------------


class TestReviewerAgentApproval:
    @patch("pipeline.agents.reviewer_agent.record_usage")
    @patch("pipeline.agents.reviewer_agent.check_budget")
    @patch("pipeline.agents.reviewer_agent.anthropic.Anthropic")
    def test_approves_good_changes(self, mock_anthropic_cls, mock_budget,
                                   mock_record, agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response(
            "approve", comments="Changes look correct",
        )
        mock_anthropic_cls.return_value = mock_client

        writer_data = {
            "changes": _sample_changes(),
            "summary": "Updated greeting",
            "reasoning": "User requested it",
        }
        result = agent.run(_make_input(writer_data, repo_path=tmp_repo))

        assert isinstance(result, AgentOutput)
        assert result.success is True
        assert result.data["verdict"] == "approve"

    @patch("pipeline.agents.reviewer_agent.record_usage")
    @patch("pipeline.agents.reviewer_agent.check_budget")
    @patch("pipeline.agents.reviewer_agent.anthropic.Anthropic")
    def test_tracks_token_usage(self, mock_anthropic_cls, mock_budget,
                                mock_record, agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response(
            "approve", input_tokens=200, output_tokens=100,
        )
        mock_anthropic_cls.return_value = mock_client

        writer_data = {"changes": _sample_changes(), "summary": "", "reasoning": ""}
        result = agent.run(_make_input(writer_data, repo_path=tmp_repo))

        assert result.tokens_used == 300
        mock_record.assert_called_once_with(300)


# ---------------------------------------------------------------------------
# ReviewerAgent.run — rejection
# ---------------------------------------------------------------------------


class TestReviewerAgentRejection:
    @patch("pipeline.agents.reviewer_agent.record_usage")
    @patch("pipeline.agents.reviewer_agent.check_budget")
    @patch("pipeline.agents.reviewer_agent.anthropic.Anthropic")
    def test_rejects_with_issues(self, mock_anthropic_cls, mock_budget,
                                 mock_record, agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        issues = [{"file": "src/main.py", "description": "Missing input validation"}]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response(
            "reject", comments="Security concern", issues=issues,
        )
        mock_anthropic_cls.return_value = mock_client

        writer_data = {"changes": _sample_changes(), "summary": "Added endpoint", "reasoning": ""}
        result = agent.run(_make_input(writer_data, repo_path=tmp_repo))

        assert result.success is True  # Agent ran successfully, even though verdict is reject
        assert result.data["verdict"] == "reject"
        assert len(result.data["issues"]) == 1
        assert "validation" in result.data["issues"][0]["description"].lower()

    @patch("pipeline.agents.reviewer_agent.record_usage")
    @patch("pipeline.agents.reviewer_agent.check_budget")
    @patch("pipeline.agents.reviewer_agent.anthropic.Anthropic")
    def test_rejection_comments_can_be_used_as_feedback(self, mock_anthropic_cls,
                                                         mock_budget, mock_record,
                                                         agent, tmp_repo):
        """Rejection comments should contain actionable feedback."""
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response(
            "reject",
            comments="Add null check before accessing user.name on line 15",
        )
        mock_anthropic_cls.return_value = mock_client

        writer_data = {"changes": _sample_changes(), "summary": "Test", "reasoning": ""}
        result = agent.run(_make_input(writer_data, repo_path=tmp_repo))

        assert result.data["verdict"] == "reject"
        assert "null check" in result.data["comments"].lower()


# ---------------------------------------------------------------------------
# ReviewerAgent.run — empty changes
# ---------------------------------------------------------------------------


class TestReviewerAgentEmptyChanges:
    def test_empty_changes_auto_approved(self, agent, tmp_repo):
        writer_data = {"changes": [], "summary": "", "reasoning": ""}
        result = agent.run(_make_input(writer_data, repo_path=tmp_repo))

        assert result.success is True
        assert result.data["verdict"] == "approve"
        assert result.tokens_used == 0

    def test_none_data_handled(self, agent, tmp_repo):
        result = agent.run(_make_input(None, repo_path=tmp_repo))

        assert result.success is True
        assert result.data["verdict"] == "approve"
        assert result.tokens_used == 0


# ---------------------------------------------------------------------------
# ReviewerAgent.run — budget exhausted
# ---------------------------------------------------------------------------


class TestReviewerAgentBudget:
    @patch("pipeline.agents.reviewer_agent.check_budget")
    def test_budget_exhausted_rejects(self, mock_budget, agent):
        mock_budget.return_value = {"allowed": False}
        writer_data = {"changes": _sample_changes(), "summary": "", "reasoning": ""}
        result = agent.run(_make_input(writer_data))

        assert result.success is False
        assert result.data["verdict"] == "reject"
        assert "budget" in result.message.lower()
        assert result.tokens_used == 0


# ---------------------------------------------------------------------------
# ReviewerAgent.run — API errors
# ---------------------------------------------------------------------------


class TestReviewerAgentErrors:
    @patch("pipeline.agents.reviewer_agent.check_budget")
    @patch("pipeline.agents.reviewer_agent.anthropic.Anthropic")
    def test_api_error_returns_reject(self, mock_anthropic_cls, mock_budget,
                                     agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = __import__("anthropic").APIError(
            message="Server error",
            request=MagicMock(),
            body=None,
        )
        mock_anthropic_cls.return_value = mock_client

        writer_data = {"changes": _sample_changes(), "summary": "", "reasoning": ""}
        result = agent.run(_make_input(writer_data, repo_path=tmp_repo))

        assert result.success is False
        assert result.data["verdict"] == "reject"
        assert result.tokens_used == 0

    @patch("pipeline.agents.reviewer_agent.record_usage")
    @patch("pipeline.agents.reviewer_agent.check_budget")
    @patch("pipeline.agents.reviewer_agent.anthropic.Anthropic")
    def test_malformed_response_returns_reject(self, mock_anthropic_cls,
                                               mock_budget, mock_record,
                                               agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="This is not JSON")]
        mock_resp.usage = MagicMock(input_tokens=40, output_tokens=10)
        mock_client.messages.create.return_value = mock_resp
        mock_anthropic_cls.return_value = mock_client

        writer_data = {"changes": _sample_changes(), "summary": "", "reasoning": ""}
        result = agent.run(_make_input(writer_data, repo_path=tmp_repo))

        assert result.success is False
        assert result.data["verdict"] == "reject"
        assert result.tokens_used == 50

    @patch("pipeline.agents.reviewer_agent.record_usage")
    @patch("pipeline.agents.reviewer_agent.check_budget")
    @patch("pipeline.agents.reviewer_agent.anthropic.Anthropic")
    def test_sends_contract_in_system_prompt(self, mock_anthropic_cls,
                                             mock_budget, mock_record, agent,
                                             tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response("approve")
        mock_anthropic_cls.return_value = mock_client

        writer_data = {"changes": _sample_changes(), "summary": "", "reasoning": ""}
        agent.run(_make_input(writer_data, repo_path=tmp_repo))

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "No breaking changes allowed" in call_kwargs["system"]
