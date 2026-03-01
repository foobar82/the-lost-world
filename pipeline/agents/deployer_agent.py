"""Deployer agent — applies changes, runs CI/CD, and merges."""

import logging
import subprocess
import uuid
from pathlib import Path

from ..constants import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    DEPLOY_SCRIPT_TIMEOUT_SECONDS,
    OUTPUT_TRUNCATION_LENGTH,
    PIPELINE_SCRIPT_TIMEOUT_SECONDS,
)
from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


def _run_cmd(cmd: list[str], cwd: str, timeout: int = DEFAULT_COMMAND_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Run a shell command, returning the CompletedProcess result."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class DeployerAgent(Agent):
    """Creates a branch, applies changes, runs the pipeline, and merges."""

    @property
    def name(self) -> str:
        return "deploy"

    def run(self, input: AgentInput) -> AgentOutput:
        context = input.context
        repo_path = context.get("repo_path", ".")
        writer_data = input.data

        changes = writer_data.get("changes", []) if isinstance(writer_data, dict) else []
        summary = writer_data.get("summary", "Agent-generated changes") if isinstance(writer_data, dict) else "Agent-generated changes"

        if not changes:
            return AgentOutput(
                data={"branch": "", "deployed": False},
                success=True,
                message="No changes to deploy",
                tokens_used=0,
            )

        branch_name = f"agent/{uuid.uuid4().hex[:8]}"
        pipeline_script = str(Path(repo_path) / "scripts" / "pipeline.sh")
        deploy_script = str(Path(repo_path) / "scripts" / "deploy.sh")

        try:
            # 1. Ensure working directory is clean.
            status = _run_cmd(["git", "status", "--porcelain"], cwd=repo_path)
            if status.stdout.strip():
                return AgentOutput(
                    data={"branch": "", "deployed": False},
                    success=False,
                    message=f"Working directory is not clean:\n{status.stdout.strip()}",
                    tokens_used=0,
                )

            # 2. Create and switch to a feature branch from main.
            current_branch = _run_cmd(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path,
            )
            original_branch = current_branch.stdout.strip()

            result = _run_cmd(
                ["git", "checkout", "-b", branch_name], cwd=repo_path,
            )
            if result.returncode != 0:
                return AgentOutput(
                    data={"branch": "", "deployed": False},
                    success=False,
                    message=f"Failed to create branch {branch_name}: {result.stderr}",
                    tokens_used=0,
                )

            # 3. Apply the file changes.
            applied = self._apply_changes(changes, repo_path)
            if not applied["success"]:
                # Abort: switch back to original branch, delete failed branch.
                _run_cmd(["git", "checkout", original_branch], cwd=repo_path)
                _run_cmd(["git", "branch", "-D", branch_name], cwd=repo_path)
                return AgentOutput(
                    data={"branch": branch_name, "deployed": False},
                    success=False,
                    message=f"Failed to apply changes: {applied['error']}",
                    tokens_used=0,
                )

            # 4. Stage and commit.
            _run_cmd(["git", "add", "-A"], cwd=repo_path)
            commit_result = _run_cmd(
                ["git", "commit", "-m", f"agent: {summary}"],
                cwd=repo_path,
            )
            if commit_result.returncode != 0:
                _run_cmd(["git", "checkout", original_branch], cwd=repo_path)
                _run_cmd(["git", "branch", "-D", branch_name], cwd=repo_path)
                return AgentOutput(
                    data={"branch": branch_name, "deployed": False},
                    success=False,
                    message=f"Failed to commit: {commit_result.stderr}",
                    tokens_used=0,
                )

            # 5. Run the CI/CD pipeline.
            logger.info("Running pipeline on branch %s", branch_name)
            pipeline_result = _run_cmd(
                ["bash", pipeline_script], cwd=repo_path, timeout=PIPELINE_SCRIPT_TIMEOUT_SECONDS,
            )

            if pipeline_result.returncode != 0:
                # Pipeline failed — do NOT merge.
                logger.warning("Pipeline failed on branch %s", branch_name)
                _run_cmd(["git", "checkout", original_branch], cwd=repo_path)
                _run_cmd(["git", "branch", "-D", branch_name], cwd=repo_path)
                return AgentOutput(
                    data={
                        "branch": branch_name,
                        "deployed": False,
                        "pipeline_stdout": pipeline_result.stdout[-OUTPUT_TRUNCATION_LENGTH:],
                        "pipeline_stderr": pipeline_result.stderr[-OUTPUT_TRUNCATION_LENGTH:],
                    },
                    success=False,
                    message=f"Pipeline failed on branch {branch_name}",
                    tokens_used=0,
                )

            # 6. Pipeline passed — merge to main.
            logger.info("Pipeline passed — merging %s to %s", branch_name, original_branch)
            _run_cmd(["git", "checkout", original_branch], cwd=repo_path)
            merge_result = _run_cmd(
                ["git", "merge", "--no-ff", branch_name, "-m",
                 f"Merge {branch_name}: {summary}"],
                cwd=repo_path,
            )
            if merge_result.returncode != 0:
                _run_cmd(["git", "merge", "--abort"], cwd=repo_path)
                _run_cmd(["git", "branch", "-D", branch_name], cwd=repo_path)
                return AgentOutput(
                    data={"branch": branch_name, "deployed": False},
                    success=False,
                    message=f"Merge failed: {merge_result.stderr}",
                    tokens_used=0,
                )

            # 7. Clean up the feature branch.
            _run_cmd(["git", "branch", "-d", branch_name], cwd=repo_path)

            # 8. Run deployment.
            logger.info("Running deployment")
            deploy_result = _run_cmd(
                ["bash", deploy_script], cwd=repo_path, timeout=DEPLOY_SCRIPT_TIMEOUT_SECONDS,
            )

            deployed = deploy_result.returncode == 0
            if not deployed:
                logger.warning("Deployment script failed (changes are merged)")

            return AgentOutput(
                data={
                    "branch": branch_name,
                    "deployed": deployed,
                    "deploy_output": deploy_result.stdout[-OUTPUT_TRUNCATION_LENGTH:] if not deployed else "",
                },
                success=True,
                message=(
                    f"Changes merged and deployed from {branch_name}"
                    if deployed
                    else f"Changes merged from {branch_name} but deployment failed"
                ),
                tokens_used=0,
            )

        except subprocess.TimeoutExpired:
            logger.error("Command timed out during deployment")
            # Try to get back to a clean state — best effort.
            try:
                _run_cmd(["git", "checkout", original_branch], cwd=repo_path)
                _run_cmd(["git", "branch", "-D", branch_name], cwd=repo_path)
            except Exception:
                logger.warning("Cleanup after timeout also failed")
            return AgentOutput(
                data={"branch": branch_name, "deployed": False},
                success=False,
                message="Deployment timed out",
                tokens_used=0,
            )
        except Exception as exc:
            logger.error("Unexpected error during deployment: %s", exc)
            return AgentOutput(
                data={"branch": "", "deployed": False},
                success=False,
                message=f"Unexpected error: {exc}",
                tokens_used=0,
            )

    def _apply_changes(self, changes: list[dict], repo_path: str) -> dict:
        """Apply a list of FileChange dicts to the working tree.

        Returns {"success": True} or {"success": False, "error": "..."}.
        """
        root = Path(repo_path).resolve()
        for change in changes:
            path = (root / change["path"]).resolve()
            if not path.is_relative_to(root):
                return {
                    "success": False,
                    "error": f"Path escapes repository: {change['path']}",
                }
            action = change["action"]
            content = change.get("content", "")

            try:
                if action == "create":
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content)
                elif action == "modify":
                    if not path.exists():
                        return {
                            "success": False,
                            "error": f"Cannot modify non-existent file: {change['path']}",
                        }
                    path.write_text(content)
                elif action == "delete":
                    if path.exists():
                        path.unlink()
                else:
                    return {
                        "success": False,
                        "error": f"Unknown action '{action}' for {change['path']}",
                    }
            except OSError as exc:
                return {"success": False, "error": f"File operation failed: {exc}"}

        return {"success": True}
