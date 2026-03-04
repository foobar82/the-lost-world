"""Local Writer agent — generates code changes via Ollama (smoke-test mode)."""

import json
import logging
from pathlib import Path

import httpx

from ..constants import OLLAMA_URL, OLLAMA_WRITER_TIMEOUT_SECONDS
from .base import Agent, AgentInput, AgentOutput, FileChange, WriterOutput

logger = logging.getLogger(__name__)

LOCAL_MODEL = "llama3.1:8b"

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
    """Collect source files for context."""
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
        rel = path.relative_to(root)
        if any(part in exclude_dirs for part in rel.parts):
            continue
        if rel.name.startswith(exclude_prefixes):
            continue
        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        source_lines.append(f"--- {rel} ---\n{content}\n")

    return "\n".join(source_lines) if source_lines else "(No source files found)"


def _parse_writer_response(text: str) -> WriterOutput:
    """Parse the structured JSON response into a WriterOutput."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
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


class OllamaWriterAgent(Agent):
    """Generates code changes using a local Ollama model (smoke-test mode)."""

    @property
    def name(self) -> str:
        return "write"

    def run(self, input: AgentInput) -> AgentOutput:
        task = input.data
        context = input.context
        repo_path = context.get("repo_path", ".")
        ollama_url = context.get("ollama_url", OLLAMA_URL)
        reviewer_feedback = context.get("reviewer_feedback")

        # Build the prompt (same as the API writer).
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
        logger.debug("System prompt for local writer agent: %s", system)
        logger.debug("Sending message to local writer agent: %s", user_message)

        # Call Ollama.
        try:
            response = httpx.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": LOCAL_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                    "stream": False,
                    "format": "json",
                },
                timeout=OLLAMA_WRITER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Ollama error (local writer): %s", exc)
            return AgentOutput(
                data=WriterOutput().__dict__,
                success=False,
                message=f"Ollama error: {exc}",
                tokens_used=0,
            )

        # Extract token counts (free, but tracked for accounting).
        tokens_used = body.get("eval_count", 0) + body.get("prompt_eval_count", 0)

        # Parse the response.
        response_text = body.get("message", {}).get("content", "")
        logger.info("Received response from local writer agent: %s", response_text)
        try:
            writer_output = _parse_writer_response(response_text)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("Failed to parse local writer response: %s", exc)
            return AgentOutput(
                data={"changes": [], "summary": "", "reasoning": "",
                      "raw_response": response_text},
                success=False,
                message=f"Failed to parse local writer response: {exc}",
                tokens_used=tokens_used,
            )

        logger.info(
            "Local writer produced %d change(s) using %d tokens",
            len(writer_output.changes), tokens_used,
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
            tokens_used=tokens_used,
        )
