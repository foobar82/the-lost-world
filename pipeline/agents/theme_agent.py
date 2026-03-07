"""Theme agent — synthesizes feedback clusters into higher-level themes via Ollama.

Receives all embedding-based clusters simultaneously and applies product-manager
lateral thinking to identify the convex hull of the requests: underlying needs
that may span multiple clusters or synthesize conflicting surface requests into
a single flexible solution.
"""

import json
import logging
import re

import httpx

from ..budget import check_budget, record_usage
from ..constants import (
    ESTIMATED_TOKENS_PER_SUMMARY,
    HTTP_TIMEOUT_SECONDS,
    OLLAMA_CHAT_MODEL,
    OLLAMA_URL,
)
from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a skilled product manager reviewing user feedback for a software project.
Your job is to identify the CONVEX HULL of user requests: the underlying needs or
solutions that would satisfy multiple requests, even when they appear to conflict
on the surface.

Rules:
- You MAY merge groups that share a deeper underlying need.
- For conflicting surface requests (e.g. "make it brown" vs "make it grey"),
  synthesize ONE flexible solution (e.g. "make the colour configurable") rather
  than picking a winner. Record the original conflicting signals.
- Do not invent requirements not present in the feedback.
- Output ONLY valid JSON. No markdown fences. No explanation outside the JSON.

Output format (strict JSON):
{"themes": [{"title": "...", "rationale": "...", "conflicting_signals": ["...", "..."], "references": ["LW-001", ...], "documents": ["...", ...]}]}

- title: short theme name, ≤10 words
- rationale: why these requests belong together and what the synthesized solution is
- conflicting_signals: list of surface-level conflicts that were synthesized (empty list if none)
- references: all feedback reference IDs covered by this theme
- documents: all feedback document texts covered by this theme\
"""


def _format_clusters(clusters: list[dict]) -> str:
    """Format clusters as a numbered list for the prompt."""
    lines = []
    for i, cluster in enumerate(clusters, 1):
        refs = ", ".join(cluster.get("references", []))
        lines.append(f"Group {i} ({refs}):")
        for doc in cluster.get("documents", []):
            lines.append(f"  - {doc}")
    return "\n".join(lines)


def _fallback_themes(clusters: list[dict]) -> list[dict]:
    """Return one bare theme per cluster (no LLM enrichment)."""
    return [
        {
            "title": f"Cluster of {len(c.get('references', []))} item(s)",
            "rationale": "",
            "conflicting_signals": [],
            "references": c.get("references", []),
            "documents": c.get("documents", []),
        }
        for c in clusters
    ]


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from the model response, stripping markdown fences."""
    # Strip ```json ... ``` or ``` ... ``` fences if present.
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


class ThemeAgent(Agent):
    """Synthesizes feedback clusters into higher-level themes with LLM reasoning."""

    @property
    def name(self) -> str:
        return "theme"

    def run(self, input: AgentInput) -> AgentOutput:
        clusters: list[dict] = input.data if isinstance(input.data, list) else []
        ollama_url = input.context.get("ollama_url", OLLAMA_URL)

        if not clusters:
            logger.info("No clusters to theme")
            return AgentOutput(
                data={"themes": []},
                success=True,
                message="No clusters provided",
                tokens_used=0,
            )

        budget = check_budget()
        if not budget["allowed"]:
            logger.warning("Budget exhausted — skipping theme analysis")
            return AgentOutput(
                data={"themes": _fallback_themes(clusters)},
                success=True,
                message="Budget exhausted — returned raw clusters as themes",
                tokens_used=0,
            )

        themes, tokens_used = self._analyse_themes(clusters, ollama_url)

        if tokens_used > 0:
            record_usage(tokens_used)

        logger.info(
            "Identified %d theme(s) from %d cluster(s) using %d tokens",
            len(themes), len(clusters), tokens_used,
        )
        return AgentOutput(
            data={"themes": themes},
            success=True,
            message=f"Identified {len(themes)} theme(s) from {len(clusters)} cluster(s)",
            tokens_used=tokens_used,
        )

    def _analyse_themes(
        self, clusters: list[dict], ollama_url: str,
    ) -> tuple[list[dict], int]:
        """Call Ollama to synthesize clusters into themes.

        Returns (themes, tokens_used).  Falls back to one-theme-per-cluster on
        any error or unparseable response.
        """
        user_message = (
            "Below are groups of related user feedback (pre-grouped by similarity).\n\n"
            f"{_format_clusters(clusters)}\n\n"
            "Synthesize these into themes as instructed."
        )

        try:
            response = httpx.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": OLLAMA_CHAT_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "stream": False,
                },
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
            content = body["message"]["content"].strip()

            tokens = body.get("eval_count", 0) + body.get("prompt_eval_count", 0)
            if tokens == 0:
                tokens = ESTIMATED_TOKENS_PER_SUMMARY * len(clusters)

            parsed = _extract_json(content)
            if parsed is None or "themes" not in parsed:
                logger.warning(
                    "ThemeAgent: could not parse LLM response as JSON — using fallback"
                )
                return _fallback_themes(clusters), tokens

            themes = parsed["themes"]
            # Validate each theme has the required keys; drop malformed entries.
            valid_themes = []
            for t in themes:
                if isinstance(t, dict) and "references" in t and "documents" in t:
                    t.setdefault("title", "")
                    t.setdefault("rationale", "")
                    t.setdefault("conflicting_signals", [])
                    valid_themes.append(t)
                else:
                    logger.warning("ThemeAgent: dropping malformed theme entry: %s", t)

            if not valid_themes:
                logger.warning("ThemeAgent: no valid themes parsed — using fallback")
                return _fallback_themes(clusters), tokens

            return valid_themes, tokens

        except (httpx.HTTPError, KeyError, ValueError):
            logger.warning(
                "ThemeAgent: Ollama unavailable — falling back to raw clusters",
                exc_info=True,
            )
            return _fallback_themes(clusters), 0
