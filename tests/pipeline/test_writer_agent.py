"""Tests for the writer agent with mocked Anthropic API responses."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.agents.base import AgentInput, AgentOutput, FileChange, WriterOutput  # noqa: E402
from pipeline.agents.writer_agent import (  # noqa: E402
    WriterAgent,
    _gather_source_files,
    _parse_writer_response,
    _read_contract,
)


@pytest.fixture()
def agent():
    return WriterAgent()


@pytest.fixture()
def tmp_repo(tmp_path):
    """Create a minimal repo structure for testing."""
    (tmp_path / "contract.md").write_text("No breaking changes allowed.")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")
    (tmp_path / "src" / "utils.py").write_text("def add(a, b): return a + b\n")
    return str(tmp_path)


def _make_input(task, repo_path=".", **extra_context):
    context = {"repo_path": repo_path}
    context.update(extra_context)
    return AgentInput(data=task, context=context)


def _anthropic_response(changes, summary="Test summary", reasoning="Test reasoning",
                        input_tokens=100, output_tokens=200):
    """Build a mock Anthropic API response."""
    response_data = {
        "changes": changes,
        "summary": summary,
        "reasoning": reasoning,
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(response_data))]
    mock_response.usage = MagicMock(
        input_tokens=input_tokens, output_tokens=output_tokens,
    )
    return mock_response


# ---------------------------------------------------------------------------
# _parse_writer_response
# ---------------------------------------------------------------------------


class TestParseWriterResponse:
    def test_parses_valid_json(self):
        data = {
            "changes": [{"path": "a.py", "action": "modify", "content": "new"}],
            "summary": "Changed a.py",
            "reasoning": "Because",
        }
        result = _parse_writer_response(json.dumps(data))
        assert len(result.changes) == 1
        assert result.changes[0].path == "a.py"
        assert result.changes[0].action == "modify"
        assert result.summary == "Changed a.py"

    def test_strips_markdown_fences(self):
        data = {
            "changes": [{"path": "b.py", "action": "create", "content": "x"}],
            "summary": "Created b.py",
            "reasoning": "Needed",
        }
        wrapped = f"```json\n{json.dumps(data)}\n```"
        result = _parse_writer_response(wrapped)
        assert len(result.changes) == 1
        assert result.changes[0].path == "b.py"

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_writer_response("not json at all")

    def test_empty_changes_list(self):
        data = {"changes": [], "summary": "", "reasoning": ""}
        result = _parse_writer_response(json.dumps(data))
        assert result.changes == []

    def test_delete_action_with_empty_content(self):
        data = {
            "changes": [{"path": "old.py", "action": "delete"}],
            "summary": "Removed old.py",
            "reasoning": "Unused",
        }
        result = _parse_writer_response(json.dumps(data))
        assert result.changes[0].action == "delete"
        assert result.changes[0].content == ""


# ---------------------------------------------------------------------------
# _read_contract
# ---------------------------------------------------------------------------


class TestReadContract:
    def test_reads_existing_contract(self, tmp_repo):
        text = _read_contract(tmp_repo)
        assert "No breaking changes allowed" in text

    def test_returns_fallback_when_missing(self, tmp_path):
        text = _read_contract(str(tmp_path))
        assert "No contract" in text


# ---------------------------------------------------------------------------
# _gather_source_files
# ---------------------------------------------------------------------------


class TestGatherSourceFiles:
    def test_includes_python_files(self, tmp_repo):
        result = _gather_source_files(tmp_repo)
        assert "main.py" in result
        assert "utils.py" in result

    def test_excludes_test_files(self, tmp_repo):
        (Path(tmp_repo) / "tests").mkdir()
        (Path(tmp_repo) / "tests" / "test_main.py").write_text("pass")
        result = _gather_source_files(tmp_repo)
        assert "test_main.py" not in result

    def test_excludes_node_modules(self, tmp_repo):
        nm = Path(tmp_repo) / "node_modules" / "lib"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}")
        result = _gather_source_files(tmp_repo)
        assert "node_modules" not in result

    def test_returns_fallback_for_empty_dir(self, tmp_path):
        result = _gather_source_files(str(tmp_path))
        assert "No source files" in result


# ---------------------------------------------------------------------------
# WriterAgent.run — happy path
# ---------------------------------------------------------------------------


class TestWriterAgentHappyPath:
    @patch("pipeline.agents.writer_agent.record_usage")
    @patch("pipeline.agents.writer_agent.check_budget")
    @patch("pipeline.agents.writer_agent.anthropic.Anthropic")
    def test_returns_file_changes(self, mock_anthropic_cls, mock_budget,
                                  mock_record, agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        changes = [{"path": "src/main.py", "action": "modify",
                     "content": "print('updated')"}]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response(changes)
        mock_anthropic_cls.return_value = mock_client

        task = {"summary": "Update greeting", "documents": ["Change greeting"]}
        result = agent.run(_make_input(task, repo_path=tmp_repo))

        assert isinstance(result, AgentOutput)
        assert result.success is True
        assert len(result.data["changes"]) == 1
        assert result.data["changes"][0]["path"] == "src/main.py"

    @patch("pipeline.agents.writer_agent.record_usage")
    @patch("pipeline.agents.writer_agent.check_budget")
    @patch("pipeline.agents.writer_agent.anthropic.Anthropic")
    def test_tracks_token_usage(self, mock_anthropic_cls, mock_budget,
                                mock_record, agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response(
            [], input_tokens=500, output_tokens=300,
        )
        mock_anthropic_cls.return_value = mock_client

        result = agent.run(_make_input({"summary": "Test"}, repo_path=tmp_repo))

        assert result.tokens_used == 800
        mock_record.assert_called_once_with(800)

    @patch("pipeline.agents.writer_agent.record_usage")
    @patch("pipeline.agents.writer_agent.check_budget")
    @patch("pipeline.agents.writer_agent.anthropic.Anthropic")
    def test_includes_summary_and_reasoning(self, mock_anthropic_cls,
                                            mock_budget, mock_record, agent,
                                            tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response(
            [], summary="Did the thing", reasoning="Because it was needed",
        )
        mock_anthropic_cls.return_value = mock_client

        result = agent.run(_make_input({"summary": "Task"}, repo_path=tmp_repo))

        assert result.data["summary"] == "Did the thing"
        assert result.data["reasoning"] == "Because it was needed"

    @patch("pipeline.agents.writer_agent.record_usage")
    @patch("pipeline.agents.writer_agent.check_budget")
    @patch("pipeline.agents.writer_agent.anthropic.Anthropic")
    def test_sends_contract_in_system_prompt(self, mock_anthropic_cls,
                                             mock_budget, mock_record, agent,
                                             tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response([])
        mock_anthropic_cls.return_value = mock_client

        agent.run(_make_input({"summary": "Test"}, repo_path=tmp_repo))

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "No breaking changes allowed" in call_kwargs["system"]

    @patch("pipeline.agents.writer_agent.record_usage")
    @patch("pipeline.agents.writer_agent.check_budget")
    @patch("pipeline.agents.writer_agent.anthropic.Anthropic")
    def test_includes_reviewer_feedback_when_provided(self, mock_anthropic_cls,
                                                      mock_budget,
                                                      mock_record, agent,
                                                      tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response([])
        mock_anthropic_cls.return_value = mock_client

        task = {"summary": "Fix the bug"}
        inp = _make_input(task, repo_path=tmp_repo,
                          reviewer_feedback="Missing null check in line 42")
        agent.run(inp)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        assert "Missing null check in line 42" in user_msg

    @patch("pipeline.agents.writer_agent.record_usage")
    @patch("pipeline.agents.writer_agent.check_budget")
    @patch("pipeline.agents.writer_agent.anthropic.Anthropic")
    def test_multiple_changes_returned(self, mock_anthropic_cls, mock_budget,
                                       mock_record, agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        changes = [
            {"path": "a.py", "action": "create", "content": "new file"},
            {"path": "b.py", "action": "modify", "content": "updated"},
            {"path": "c.py", "action": "delete", "content": ""},
        ]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response(changes)
        mock_anthropic_cls.return_value = mock_client

        result = agent.run(_make_input({"summary": "Multi-change"}, repo_path=tmp_repo))

        assert result.success is True
        assert len(result.data["changes"]) == 3
        actions = [c["action"] for c in result.data["changes"]]
        assert actions == ["create", "modify", "delete"]


# ---------------------------------------------------------------------------
# WriterAgent.run — budget exhausted
# ---------------------------------------------------------------------------


class TestWriterAgentBudget:
    @patch("pipeline.agents.writer_agent.check_budget")
    def test_budget_exhausted_returns_failure(self, mock_budget, agent):
        mock_budget.return_value = {"allowed": False}
        result = agent.run(_make_input({"summary": "Test"}))

        assert result.success is False
        assert "budget" in result.message.lower()
        assert result.tokens_used == 0


# ---------------------------------------------------------------------------
# WriterAgent.run — API errors
# ---------------------------------------------------------------------------


class TestWriterAgentErrors:
    @patch("pipeline.agents.writer_agent.check_budget")
    @patch("pipeline.agents.writer_agent.anthropic.Anthropic")
    def test_api_error_returns_failure(self, mock_anthropic_cls, mock_budget,
                                      agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = __import__("anthropic").APIError(
            message="Rate limited",
            request=MagicMock(),
            body=None,
        )
        mock_anthropic_cls.return_value = mock_client

        result = agent.run(_make_input({"summary": "Test"}, repo_path=tmp_repo))

        assert result.success is False
        assert result.tokens_used == 0

    @patch("pipeline.agents.writer_agent.record_usage")
    @patch("pipeline.agents.writer_agent.check_budget")
    @patch("pipeline.agents.writer_agent.anthropic.Anthropic")
    def test_malformed_response_returns_failure(self, mock_anthropic_cls,
                                                mock_budget, mock_record,
                                                agent, tmp_repo):
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="This is not JSON")]
        mock_resp.usage = MagicMock(input_tokens=50, output_tokens=20)
        mock_client.messages.create.return_value = mock_resp
        mock_anthropic_cls.return_value = mock_client

        result = agent.run(_make_input({"summary": "Test"}, repo_path=tmp_repo))

        assert result.success is False
        assert result.tokens_used == 70
        assert "raw_response" in result.data

    @patch("pipeline.agents.writer_agent.record_usage")
    @patch("pipeline.agents.writer_agent.check_budget")
    @patch("pipeline.agents.writer_agent.anthropic.Anthropic")
    def test_string_task_input_handled(self, mock_anthropic_cls, mock_budget,
                                       mock_record, agent, tmp_repo):
        """Writer should handle plain string task input (not just dicts)."""
        mock_budget.return_value = {"allowed": True}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _anthropic_response([])
        mock_anthropic_cls.return_value = mock_client

        result = agent.run(_make_input("A simple string task", repo_path=tmp_repo))

        assert result.success is True
