"""Local Reviewer agent — reviews proposed changes via Ollama (smoke-test mode)."""

import json
import logging
from pathlib import Path

import httpx

from ..constants import HTTP_TIMEOUT_SECONDS, OLLAMA_URL
from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)

LOCAL_MODEL = "llama3.1:8b"

SYSTEM_PROMPT = """\
You are a code reviewer for The Lost World Plateau, a bounded 2D ecosystem that \
evolves autonomously through user feedback.

Your job is to review proposed code changes for:
1. **Correctness** — Will the changes work as intended? Are there logic errors?
2. **Security** — Do the changes introduce vulnerabilities (XSS, injection, etc.)?
3. **Contract adherence** — Do the changes respect the architectural contract below?
4. **Test safety** — Are existing tests likely to still pass?
5. **Minimality** — Are the changes focused, or do they include unnecessary modifications?

--- CONTRACT ---
{contract}
--- END CONTRACT ---

Return your review as a JSON object with this exact structure:
{{
  "verdict": "approve" or "reject",
  "comments": "Detailed review comments explaining your decision",
  "issues": [
    {{
      "file": "path/to/file",
      "description": "What is wrong and how to fix it"
    }}
  ]
}}

If you approve, "issues" should be an empty list.
If you reject, "comments" must include specific, actionable feedback that the writer \
can use to fix the problems. Be precise about what needs to change and why.

Return ONLY the JSON object. No markdown fences, no commentary outside the JSON."""


def _read_contract(repo_path: str) -> str:
    """Read the contract file from the repository."""
    contract_path = Path(repo_path) / "contract.md"
    if contract_path.exists():
        return contract_path.read_text()
    return "(No contract file found)"


def _format_changes_for_review(changes: list[dict]) -> str:
    """Format the proposed changes into a readable string for the reviewer."""
    parts = []
    for change in changes:
        action = change.get("action", "unknown")
        path = change.get("path", "unknown")
        content = change.get("content", "")

        header = f"### {action.upper()}: {path}"
        if action == "delete":
            parts.append(f"{header}\n(File to be deleted)")
        else:
            parts.append(f"{header}\n```\n{content}\n```")
    return "\n\n".join(parts)


def _parse_reviewer_response(text: str) -> dict:
    """Parse the structured JSON response from the model."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    verdict = data.get("verdict", "reject")
    if verdict not in ("approve", "reject"):
        verdict = "reject"
    return {
        "verdict": verdict,
        "comments": data.get("comments", ""),
        "issues": data.get("issues", []),
    }


class OllamaReviewerAgent(Agent):
    """Reviews code changes using a local Ollama model (smoke-test mode)."""

    @property
    def name(self) -> str:
        return "review"

    def run(self, input: AgentInput) -> AgentOutput:
        writer_data = input.data
        context = input.context
        repo_path = context.get("repo_path", ".")
        ollama_url = context.get("ollama_url", OLLAMA_URL)

        changes = writer_data.get("changes", []) if isinstance(writer_data, dict) else []
        summary = writer_data.get("summary", "") if isinstance(writer_data, dict) else ""
        reasoning = writer_data.get("reasoning", "") if isinstance(writer_data, dict) else ""

        if not changes:
            return AgentOutput(
                data={"verdict": "approve", "comments": "No changes to review",
                      "issues": []},
                success=True,
                message="No changes to review — auto-approved",
                tokens_used=0,
            )

        # Build the prompt (same as the API reviewer).
        contract = _read_contract(repo_path)
        system = SYSTEM_PROMPT.format(contract=contract)

        changes_text = _format_changes_for_review(changes)
        user_message = (
            f"## Proposed Changes\n\n"
            f"**Summary:** {summary}\n\n"
            f"**Reasoning:** {reasoning}\n\n"
            f"## File Changes\n\n{changes_text}"
        )

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
                },
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Ollama error (local reviewer): %s", exc)
            return AgentOutput(
                data={"verdict": "reject",
                      "comments": f"Ollama error during review: {exc}",
                      "issues": []},
                success=False,
                message=f"Ollama error: {exc}",
                tokens_used=0,
            )

        # Extract token counts (free, but tracked for accounting).
        tokens_used = body.get("eval_count", 0) + body.get("prompt_eval_count", 0)

        # Parse the response.
        response_text = body.get("message", {}).get("content", "")
        try:
            review = _parse_reviewer_response(response_text)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("Failed to parse local reviewer response: %s", exc)
            return AgentOutput(
                data={"verdict": "reject",
                      "comments": f"Failed to parse review: {exc}",
                      "issues": [], "raw_response": response_text},
                success=False,
                message=f"Failed to parse local reviewer response: {exc}",
                tokens_used=tokens_used,
            )

        verdict = review["verdict"]
        logger.info(
            "Local reviewer %s changes using %d tokens",
            "approved" if verdict == "approve" else "rejected",
            tokens_used,
        )
        return AgentOutput(
            data=review,
            success=True,
            message=f"Review complete: {verdict} — {review['comments'][:100]}",
            tokens_used=tokens_used,
        )
