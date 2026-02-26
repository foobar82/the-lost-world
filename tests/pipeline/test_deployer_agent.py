"""Tests for the deployer agent with mocked git and subprocess calls."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.agents.base import AgentInput, AgentOutput  # noqa: E402
from pipeline.agents.deployer_agent import DeployerAgent  # noqa: E402


@pytest.fixture()
def agent():
    return DeployerAgent()


@pytest.fixture()
def git_repo(tmp_path):
    """Create a real git repo for testing file operations."""
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"],
                   cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=str(tmp_path), capture_output=True)
    # Create initial commit so we have a branch to work with.
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"],
                   cwd=str(tmp_path), capture_output=True)
    return str(tmp_path)


def _make_input(writer_data, repo_path="."):
    return AgentInput(data=writer_data, context={"repo_path": repo_path})


def _completed(stdout="", stderr="", returncode=0):
    """Build a mock subprocess.CompletedProcess."""
    cp = MagicMock()
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


# ---------------------------------------------------------------------------
# DeployerAgent._apply_changes (file operations)
# ---------------------------------------------------------------------------


class TestApplyChanges:
    def test_create_file(self, agent, tmp_path):
        changes = [{"path": "new.py", "action": "create", "content": "print('hi')"}]
        result = agent._apply_changes(changes, str(tmp_path))
        assert result["success"] is True
        assert (tmp_path / "new.py").read_text() == "print('hi')"

    def test_create_file_in_nested_dir(self, agent, tmp_path):
        changes = [{"path": "src/deep/module.py", "action": "create",
                     "content": "x = 1"}]
        result = agent._apply_changes(changes, str(tmp_path))
        assert result["success"] is True
        assert (tmp_path / "src" / "deep" / "module.py").exists()

    def test_modify_existing_file(self, agent, tmp_path):
        (tmp_path / "existing.py").write_text("old content")
        changes = [{"path": "existing.py", "action": "modify",
                     "content": "new content"}]
        result = agent._apply_changes(changes, str(tmp_path))
        assert result["success"] is True
        assert (tmp_path / "existing.py").read_text() == "new content"

    def test_modify_nonexistent_file_fails(self, agent, tmp_path):
        changes = [{"path": "missing.py", "action": "modify",
                     "content": "content"}]
        result = agent._apply_changes(changes, str(tmp_path))
        assert result["success"] is False
        assert "non-existent" in result["error"].lower()

    def test_delete_file(self, agent, tmp_path):
        (tmp_path / "to_delete.py").write_text("bye")
        changes = [{"path": "to_delete.py", "action": "delete", "content": ""}]
        result = agent._apply_changes(changes, str(tmp_path))
        assert result["success"] is True
        assert not (tmp_path / "to_delete.py").exists()

    def test_delete_nonexistent_file_succeeds(self, agent, tmp_path):
        changes = [{"path": "ghost.py", "action": "delete", "content": ""}]
        result = agent._apply_changes(changes, str(tmp_path))
        assert result["success"] is True

    def test_unknown_action_fails(self, agent, tmp_path):
        changes = [{"path": "a.py", "action": "rename", "content": ""}]
        result = agent._apply_changes(changes, str(tmp_path))
        assert result["success"] is False
        assert "unknown" in result["error"].lower()

    def test_multiple_changes_applied_in_order(self, agent, tmp_path):
        changes = [
            {"path": "a.py", "action": "create", "content": "file a"},
            {"path": "b.py", "action": "create", "content": "file b"},
        ]
        result = agent._apply_changes(changes, str(tmp_path))
        assert result["success"] is True
        assert (tmp_path / "a.py").read_text() == "file a"
        assert (tmp_path / "b.py").read_text() == "file b"


# ---------------------------------------------------------------------------
# DeployerAgent.run — empty changes
# ---------------------------------------------------------------------------


class TestDeployerEmptyChanges:
    def test_no_changes_returns_success(self, agent):
        result = agent.run(_make_input({"changes": [], "summary": "Nothing"}))
        assert result.success is True
        assert result.data["deployed"] is False
        assert result.tokens_used == 0

    def test_none_data_handled(self, agent):
        result = agent.run(_make_input(None))
        assert result.success is True
        assert result.data["deployed"] is False


# ---------------------------------------------------------------------------
# DeployerAgent.run — full pipeline (mocked subprocess)
# ---------------------------------------------------------------------------


class TestDeployerFullPipeline:
    @patch("pipeline.agents.deployer_agent._run_cmd")
    def test_successful_deploy(self, mock_run, agent, tmp_path):
        """Full happy path: clean dir, create branch, apply, commit, pipeline passes, merge, deploy."""
        changes = [{"path": "src/new.py", "action": "create", "content": "x = 1"}]
        writer_data = {"changes": changes, "summary": "Add new file"}

        # Set up mock responses in call order.
        mock_run.side_effect = [
            _completed(stdout=""),                        # git status --porcelain (clean)
            _completed(stdout="master\n"),                # git rev-parse --abbrev-ref HEAD
            _completed(),                                 # git checkout -b agent/xxx
            _completed(),                                 # git add -A
            _completed(),                                 # git commit
            _completed(),                                 # bash pipeline.sh (pass)
            _completed(),                                 # git checkout master
            _completed(),                                 # git merge --no-ff
            _completed(),                                 # git branch -d
            _completed(),                                 # bash deploy.sh
        ]

        # We also need to create the file for _apply_changes to work,
        # so we use a real tmp_path.
        result = agent.run(_make_input(writer_data, repo_path=str(tmp_path)))

        assert result.success is True
        assert result.data["deployed"] is True
        assert result.tokens_used == 0

    @patch("pipeline.agents.deployer_agent._run_cmd")
    def test_dirty_workdir_fails(self, mock_run, agent, tmp_path):
        mock_run.return_value = _completed(stdout="M src/main.py\n")  # dirty

        changes = [{"path": "a.py", "action": "create", "content": "x"}]
        result = agent.run(_make_input({"changes": changes, "summary": "Test"},
                                       repo_path=str(tmp_path)))

        assert result.success is False
        assert "clean" in result.message.lower() or "not clean" in result.message.lower() or "dirty" in result.message.lower()

    @patch("pipeline.agents.deployer_agent._run_cmd")
    def test_pipeline_failure_does_not_merge(self, mock_run, agent, tmp_path):
        """When pipeline.sh fails, changes should not be merged."""
        changes = [{"path": "bad.py", "action": "create", "content": "syntax error"}]
        writer_data = {"changes": changes, "summary": "Bad change"}

        mock_run.side_effect = [
            _completed(stdout=""),                         # git status (clean)
            _completed(stdout="master\n"),                 # rev-parse HEAD
            _completed(),                                  # checkout -b
            _completed(),                                  # git add
            _completed(),                                  # git commit
            _completed(returncode=1, stderr="Lint failed"),  # pipeline FAILS
            _completed(),                                  # git checkout master (cleanup)
            _completed(),                                  # git branch -D (cleanup)
        ]

        result = agent.run(_make_input(writer_data, repo_path=str(tmp_path)))

        assert result.success is False
        assert result.data["deployed"] is False
        assert "pipeline_stderr" in result.data

    @patch("pipeline.agents.deployer_agent._run_cmd")
    def test_branch_creation_failure(self, mock_run, agent, tmp_path):
        mock_run.side_effect = [
            _completed(stdout=""),                         # git status (clean)
            _completed(stdout="master\n"),                 # rev-parse HEAD
            _completed(returncode=1, stderr="Branch exists"),  # checkout -b fails
        ]

        changes = [{"path": "a.py", "action": "create", "content": "x"}]
        result = agent.run(_make_input({"changes": changes, "summary": "Test"},
                                       repo_path=str(tmp_path)))

        assert result.success is False
        assert "branch" in result.message.lower()

    @patch("pipeline.agents.deployer_agent._run_cmd")
    def test_merge_failure_aborts(self, mock_run, agent, tmp_path):
        """If merge fails, the agent should abort and clean up."""
        changes = [{"path": "a.py", "action": "create", "content": "x"}]
        writer_data = {"changes": changes, "summary": "Test"}

        mock_run.side_effect = [
            _completed(stdout=""),                         # git status (clean)
            _completed(stdout="master\n"),                 # rev-parse HEAD
            _completed(),                                  # checkout -b
            _completed(),                                  # git add
            _completed(),                                  # git commit
            _completed(),                                  # pipeline passes
            _completed(),                                  # checkout master
            _completed(returncode=1, stderr="CONFLICT"),   # merge fails
            _completed(),                                  # merge --abort
            _completed(),                                  # branch -D
        ]

        result = agent.run(_make_input(writer_data, repo_path=str(tmp_path)))

        assert result.success is False
        assert result.data["deployed"] is False

    @patch("pipeline.agents.deployer_agent._run_cmd")
    def test_deploy_script_failure_still_succeeds(self, mock_run, agent, tmp_path):
        """If deploy.sh fails, changes are still merged, but deployed=False."""
        changes = [{"path": "a.py", "action": "create", "content": "x"}]
        writer_data = {"changes": changes, "summary": "Test"}

        mock_run.side_effect = [
            _completed(stdout=""),                         # git status (clean)
            _completed(stdout="master\n"),                 # rev-parse HEAD
            _completed(),                                  # checkout -b
            _completed(),                                  # git add
            _completed(),                                  # git commit
            _completed(),                                  # pipeline passes
            _completed(),                                  # checkout master
            _completed(),                                  # merge succeeds
            _completed(),                                  # branch -d
            _completed(returncode=1, stderr="Deploy err"),   # deploy.sh FAILS
        ]

        result = agent.run(_make_input(writer_data, repo_path=str(tmp_path)))

        assert result.success is True
        assert result.data["deployed"] is False
        assert "deployment failed" in result.message.lower()


# ---------------------------------------------------------------------------
# DeployerAgent.run — file application with real git repo
# ---------------------------------------------------------------------------


class TestDeployerRealGitRepo:
    """Integration tests using a real temporary git repo (no subprocess mocking)."""

    def test_apply_changes_creates_files_in_real_repo(self, agent, git_repo):
        """Verify _apply_changes works with a real git repository."""
        changes = [
            {"path": "src/feature.py", "action": "create",
             "content": "def greet(): return 'hello'\n"},
        ]
        result = agent._apply_changes(changes, git_repo)
        assert result["success"] is True
        assert (Path(git_repo) / "src" / "feature.py").exists()

    def test_apply_and_verify_git_status(self, agent, git_repo):
        """After applying changes, git should detect them."""
        import subprocess

        changes = [
            {"path": "new_file.py", "action": "create", "content": "x = 42\n"},
        ]
        agent._apply_changes(changes, git_repo)

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_repo, capture_output=True, text=True,
        )
        assert "new_file.py" in status.stdout


# ---------------------------------------------------------------------------
# DeployerAgent.run — timeout handling
# ---------------------------------------------------------------------------


class TestDeployerTimeout:
    @patch("pipeline.agents.deployer_agent._run_cmd")
    def test_timeout_returns_failure(self, mock_run, agent, tmp_path):
        import subprocess

        mock_run.side_effect = [
            _completed(stdout=""),              # git status (clean)
            _completed(stdout="master\n"),      # rev-parse HEAD
        ]
        # After getting through status and rev-parse, raise timeout on checkout.
        original_side_effect = mock_run.side_effect

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                return [_completed(stdout=""), _completed(stdout="master\n")][call_count[0] - 1]
            raise subprocess.TimeoutExpired(cmd="git", timeout=300)

        mock_run.side_effect = side_effect

        changes = [{"path": "a.py", "action": "create", "content": "x"}]
        result = agent.run(_make_input({"changes": changes, "summary": "Test"},
                                       repo_path=str(tmp_path)))

        assert result.success is False
        assert "timed out" in result.message.lower()
