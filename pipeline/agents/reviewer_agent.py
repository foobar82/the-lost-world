"""Code Reviewer agent — reviews proposed changes via Anthropic API."""

import json
import logging
from pathlib import Path

import anthropic

from ..budget import check_budget, record_usage
from ..constants import DEFAULT_REVIEWER_MODEL, REVIEWER_MAX_TOKENS
from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)

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
    """Parse the structured JSON response from Claude."""
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


class ReviewerAgent(Agent):
    """Reviews code changes for correctness, security, and contract adherence."""

    @property
    def name(self) -> str:
        return "review"

    def run(self, input: AgentInput) -> AgentOutput:
        writer_data = input.data
        context = input.context
        repo_path = context.get("repo_path", ".")
        model = context.get("reviewer_model", DEFAULT_REVIEWER_MODEL)

        # Check budget before making an expensive API call.
        budget = check_budget()
        if not budget["allowed"]:
            logger.warning("Budget exhausted — skipping review")
            return AgentOutput(
                data={"verdict": "reject", "comments": "Budget exhausted",
                      "issues": []},
                success=False,
                message="Budget exhausted — cannot review changes",
                tokens_used=0,
            )

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

        # Build the prompt.
        contract = _read_contract(repo_path)
        system = SYSTEM_PROMPT.format(contract=contract)

        changes_text = _format_changes_for_review(changes)
        user_message = (
            f"## Proposed Changes\n\n"
            f"**Summary:** {summary}\n\n"
            f"**Reasoning:** {reasoning}\n\n"
            f"## File Changes\n\n{changes_text}"
        )

        # Call the Anthropic API.
        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=model,
                max_tokens=REVIEWER_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as exc:
            logger.error("Anthropic API error: %s", exc)
            return AgentOutput(
                data={"verdict": "reject",
                      "comments": f"API error during review: {exc}",
                      "issues": []},
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
            review = _parse_reviewer_response(response_text)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("Failed to parse reviewer response: %s", exc)
            return AgentOutput(
                data={"verdict": "reject",
                      "comments": f"Failed to parse review: {exc}",
                      "issues": [], "raw_response": response_text},
                success=False,
                message=f"Failed to parse reviewer response: {exc}",
                tokens_used=total_tokens,
            )

        verdict = review["verdict"]
        logger.info(
            "Reviewer %s changes using %d tokens",
            "approved" if verdict == "approve" else "rejected",
            total_tokens,
        )
        return AgentOutput(
            data=review,
            success=True,
            message=f"Review complete: {verdict} — {review['comments'][:100]}",
            tokens_used=total_tokens,
        )
