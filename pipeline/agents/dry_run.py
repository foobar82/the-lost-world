"""Dry-run agents — mock Anthropic API calls and log deployment steps.

Used by ``batch.py --dry-run`` to validate the full pipeline flow
(embeddings, ChromaDB, clustering, prioritisation, budget tracking)
without spending real API credits.

Ollama / ChromaDB agents are NOT replaced — they run for real (free).
Only the Anthropic-backed writer/reviewer and the deployer are mocked.
"""

import logging

from ..budget import COST_PER_TOKEN_GBP
from .base import Agent, AgentInput, AgentOutput
from .reviewer_agent import (
    SYSTEM_PROMPT as REVIEWER_SYSTEM_PROMPT,
)
from .reviewer_agent import (
    _format_changes_for_review,
)
from .writer_agent import (
    SYSTEM_PROMPT as WRITER_SYSTEM_PROMPT,
)
from .writer_agent import (
    _gather_source_files,
    _read_contract,
)

logger = logging.getLogger(__name__)

# Conservative output-token estimates used for budget projections.
_ESTIMATED_OUTPUT_TOKENS_WRITER = 500
_ESTIMATED_OUTPUT_TOKENS_REVIEWER = 300


def _estimate_tokens(text: str) -> int:
    """Rough token count: ~4 characters per token."""
    return max(1, len(text) // 4)


# ── Writer ────────────────────────────────────────────────────────────


class DryRunWriterAgent(Agent):
    """Builds the real prompt but returns a mock response instead of calling Anthropic."""

    @property
    def name(self) -> str:
        return "write"

    def run(self, input: AgentInput) -> AgentOutput:
        task = input.data
        context = input.context
        repo_path = context.get("repo_path", ".")
        model = context.get("writer_model", "claude-sonnet-4-20250514")
        reviewer_feedback = context.get("reviewer_feedback")

        # Build the full prompt (same as the real writer) to validate
        # prompt construction, contract reading, and source-file gathering.
        contract = _read_contract(repo_path)
        system = WRITER_SYSTEM_PROMPT.format(contract=contract)
        source_files = _gather_source_files(repo_path)

        task_summary = task.get("summary", str(task)) if isinstance(task, dict) else str(task)
        documents = task.get("documents", []) if isinstance(task, dict) else []

        user_parts = [f"## Task\n{task_summary}"]
        if documents:
            user_parts.append(
                "## User Feedback\n" + "\n".join(f"- {doc}" for doc in documents)
            )
        if reviewer_feedback:
            user_parts.append(
                f"## Reviewer Feedback (address these issues)\n{reviewer_feedback}"
            )
        user_parts.append(f"## Source Files\n{source_files}")
        user_message = "\n\n".join(user_parts)

        # Estimate tokens.
        input_tokens = _estimate_tokens(system + user_message)
        output_tokens = _ESTIMATED_OUTPUT_TOKENS_WRITER
        total_tokens = input_tokens + output_tokens
        estimated_cost = total_tokens * COST_PER_TOKEN_GBP

        logger.info(
            "[DRY RUN] Writer would call %s with ~%d input tokens "
            "(system: %d chars, user: %d chars). Estimated cost: £%.4f",
            model, input_tokens, len(system), len(user_message), estimated_cost,
        )

        # Return a mock response with a trivial, safe change.
        mock_summary = f"[DRY RUN] Mock change for: {task_summary[:100]}"
        mock_changes = [
            {
                "path": "pipeline/__init__.py",
                "action": "modify",
                "content": "# Auto-generated change (dry-run mock)\n",
            },
        ]

        return AgentOutput(
            data={
                "changes": mock_changes,
                "summary": mock_summary,
                "reasoning": "[DRY RUN] No real API call was made.",
            },
            success=True,
            message=f"[DRY RUN] Mock: 1 file change, ~{total_tokens} tokens estimated",
            tokens_used=total_tokens,
        )


# ── Reviewer ──────────────────────────────────────────────────────────


class DryRunReviewerAgent(Agent):
    """Logs the review request and auto-approves."""

    @property
    def name(self) -> str:
        return "review"

    def run(self, input: AgentInput) -> AgentOutput:
        writer_data = input.data
        context = input.context
        repo_path = context.get("repo_path", ".")
        model = context.get("reviewer_model", "claude-sonnet-4-20250514")

        changes = writer_data.get("changes", []) if isinstance(writer_data, dict) else []
        summary = writer_data.get("summary", "") if isinstance(writer_data, dict) else ""
        reasoning = writer_data.get("reasoning", "") if isinstance(writer_data, dict) else ""

        if not changes:
            return AgentOutput(
                data={"verdict": "approve", "comments": "[DRY RUN] No changes to review",
                      "issues": []},
                success=True,
                message="[DRY RUN] No changes to review — auto-approved",
                tokens_used=0,
            )

        # Build the full prompt (same as the real reviewer).
        contract = _read_contract(repo_path)
        system = REVIEWER_SYSTEM_PROMPT.format(contract=contract)
        changes_text = _format_changes_for_review(changes)
        user_message = (
            f"## Proposed Changes\n\n"
            f"**Summary:** {summary}\n\n"
            f"**Reasoning:** {reasoning}\n\n"
            f"## File Changes\n\n{changes_text}"
        )

        # Estimate tokens.
        input_tokens = _estimate_tokens(system + user_message)
        output_tokens = _ESTIMATED_OUTPUT_TOKENS_REVIEWER
        total_tokens = input_tokens + output_tokens
        estimated_cost = total_tokens * COST_PER_TOKEN_GBP

        logger.info(
            "[DRY RUN] Reviewer would call %s with ~%d input tokens. "
            "Estimated cost: £%.4f",
            model, input_tokens, estimated_cost,
        )

        return AgentOutput(
            data={
                "verdict": "approve",
                "comments": "[DRY RUN] Auto-approved (no real API call)",
                "issues": [],
            },
            success=True,
            message=f"[DRY RUN] Mock review: approved, ~{total_tokens} tokens estimated",
            tokens_used=total_tokens,
        )


# ── Deployer ──────────────────────────────────────────────────────────


class DryRunDeployerAgent(Agent):
    """Logs deployment steps without touching git."""

    @property
    def name(self) -> str:
        return "deploy"

    def run(self, input: AgentInput) -> AgentOutput:
        writer_data = input.data

        changes = writer_data.get("changes", []) if isinstance(writer_data, dict) else []
        summary = writer_data.get("summary", "") if isinstance(writer_data, dict) else ""

        logger.info("[DRY RUN] Deployer would perform these steps:")
        logger.info("[DRY RUN]   1. Create branch: agent/<uuid>")
        for change in changes:
            action = change.get("action", "?").capitalize()
            path = change.get("path", "?")
            logger.info("[DRY RUN]   2. %s file: %s", action, path)
        logger.info("[DRY RUN]   3. git add -A && git commit -m 'agent: %s'",
                     summary[:80])
        logger.info("[DRY RUN]   4. Run scripts/pipeline.sh")
        logger.info("[DRY RUN]   5. Merge to current branch (--no-ff)")
        logger.info("[DRY RUN]   6. Run scripts/deploy.sh")

        return AgentOutput(
            data={
                "branch": "agent/dry-run",
                "deployed": False,
                "dry_run": True,
            },
            success=True,
            message="[DRY RUN] Deployment skipped — logged steps only",
            tokens_used=0,
        )
