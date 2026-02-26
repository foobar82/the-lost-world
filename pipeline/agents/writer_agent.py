"""Code Writer agent — generates code changes via Anthropic API."""

import json
import logging
from pathlib import Path

import anthropic

from ..budget import check_budget, record_usage
from .base import Agent, AgentInput, AgentOutput, FileChange, WriterOutput

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """\
You are a code writer for The Lost World Plateau, a bounded 2D ecosystem that \
evolves autonomously through user feedback.

Your job is to implement a specific task by producing minimal, focused code changes. \
Follow these rules strictly:

1. Make ONLY the changes needed to implement the requested task.
2. Do NOT refactor, rename, or reorganise unrelated code.
3. Do NOT add comments, docstrings, or type annotations to code you did not change.
4. Ensure existing tests still pass — do not break existing behaviour.
5. Respect the architectural contract below. You must not violate any invariant it defines.

--- CONTRACT ---
{contract}
--- END CONTRACT ---

Return your changes as a JSON object with this exact structure:
{{
  "changes": [
    {{
      "path": "relative/path/to/file.ext",
      "action": "create" | "modify" | "delete",
      "content": "full file content for create/modify, empty string for delete"
    }}
  ],
  "summary": "Brief human-readable description of what was changed",
  "reasoning": "Why these changes were made"
}}

Return ONLY the JSON object. No markdown fences, no commentary outside the JSON."""


def _read_contract(repo_path: str) -> str:
    """Read the contract file from the repository."""
    contract_path = Path(repo_path) / "contract.md"
    if contract_path.exists():
        return contract_path.read_text()
    return "(No contract file found)"


def _gather_source_files(repo_path: str) -> str:
    """Collect source files for context.

    For now, includes all source files since the codebase is small.
    Excludes: test files, node_modules, build output, config files.
    """
    root = Path(repo_path)
    source_lines = []
    extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html"}
    exclude_dirs = {
        "node_modules", "dist", "build", ".git", "__pycache__",
        "venv", ".venv", "data",
    }
    exclude_prefixes = ("test_", "conftest")

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue
        # Skip excluded directories.
        rel = path.relative_to(root)
        if any(part in exclude_dirs for part in rel.parts):
            continue
        # Skip test files.
        if rel.name.startswith(exclude_prefixes):
            continue
        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        source_lines.append(f"--- {rel} ---\n{content}\n")

    return "\n".join(source_lines) if source_lines else "(No source files found)"


def _parse_writer_response(text: str) -> WriterOutput:
    """Parse the structured JSON response from Claude into a WriterOutput."""
    # Strip markdown fences if present.
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (with optional language tag).
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    changes = []
    for change in data.get("changes", []):
        changes.append(FileChange(
            path=change["path"],
            action=change["action"],
            content=change.get("content", ""),
        ))
    return WriterOutput(
        changes=changes,
        summary=data.get("summary", ""),
        reasoning=data.get("reasoning", ""),
    )


class WriterAgent(Agent):
    """Generates code changes to implement a prioritised task."""

    @property
    def name(self) -> str:
        return "write"

    def run(self, input: AgentInput) -> AgentOutput:
        task = input.data
        context = input.context
        repo_path = context.get("repo_path", ".")
        model = context.get("writer_model", DEFAULT_MODEL)
        reviewer_feedback = context.get("reviewer_feedback")

        # Check budget before making an expensive API call.
        budget = check_budget()
        if not budget["allowed"]:
            logger.warning("Budget exhausted — skipping writer")
            return AgentOutput(
                data=WriterOutput().__dict__,
                success=False,
                message="Budget exhausted — cannot generate changes",
                tokens_used=0,
            )

        # Build the prompt.
        contract = _read_contract(repo_path)
        system = SYSTEM_PROMPT.format(contract=contract)
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

        # Call the Anthropic API.
        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as exc:
            logger.error("Anthropic API error: %s", exc)
            return AgentOutput(
                data=WriterOutput().__dict__,
                success=False,
                message=f"Anthropic API error: {exc}",
                tokens_used=0,
            )

        # Track token usage.
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens
        record_usage(total_tokens)

        # Parse the response.
        response_text = response.content[0].text
        try:
            writer_output = _parse_writer_response(response_text)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("Failed to parse writer response: %s", exc)
            return AgentOutput(
                data={"changes": [], "summary": "", "reasoning": "",
                      "raw_response": response_text},
                success=False,
                message=f"Failed to parse writer response: {exc}",
                tokens_used=total_tokens,
            )

        logger.info(
            "Writer produced %d change(s) using %d tokens",
            len(writer_output.changes), total_tokens,
        )
        return AgentOutput(
            data={
                "changes": [
                    {"path": c.path, "action": c.action, "content": c.content}
                    for c in writer_output.changes
                ],
                "summary": writer_output.summary,
                "reasoning": writer_output.reasoning,
            },
            success=True,
            message=f"Generated {len(writer_output.changes)} change(s): {writer_output.summary}",
            tokens_used=total_tokens,
        )
