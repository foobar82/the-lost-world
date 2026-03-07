"""Prioritisation agent — ranks clusters by implementation priority using Ollama."""

import json
import logging

import httpx

from ..budget import check_budget
from ..constants import (
    HTTP_TIMEOUT_SECONDS,
    OLLAMA_CHAT_MODEL,
    OLLAMA_URL,
)
from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class PrioritiserAgent(Agent):
    """Ranks feedback clusters by implementation priority using Ollama."""

    @property
    def name(self) -> str:
        return "prioritise"

    def run(self, input: AgentInput) -> AgentOutput:
        clusters: list[dict] = input.data if isinstance(input.data, list) else []
        ollama_url = input.context.get("ollama_url", OLLAMA_URL)

        if not clusters:
            logger.info("No clusters to prioritise")
            return AgentOutput(
                data={"clusters": []},
                success=True,
                message="No clusters provided",
                tokens_used=0,
            )

        if len(clusters) == 1:
            logger.info("Single cluster — no prioritisation needed")
            return AgentOutput(
                data={"clusters": clusters},
                success=True,
                message="Single cluster — returned as-is",
                tokens_used=0,
            )

        budget = check_budget()
        if not budget["allowed"]:
            logger.warning("Budget exhausted — falling back to size-based ordering")
            return AgentOutput(
                data={"clusters": self._sort_by_size(clusters)},
                success=True,
                message="Budget exhausted — clusters ordered by size",
                tokens_used=0,
            )

        ordered = self._rank_clusters(clusters, ollama_url)
        logger.info("Prioritised %d cluster(s)", len(ordered))
        return AgentOutput(
            data={"clusters": ordered},
            success=True,
            message=f"Prioritised {len(ordered)} cluster(s)",
            tokens_used=0,
        )

    def _rank_clusters(self, clusters: list[dict], ollama_url: str) -> list[dict]:
        """Ask Ollama to rank clusters by implementation priority.

        Falls back to size-based ordering if Ollama is unavailable or the
        response cannot be parsed.
        """
        summaries = []
        for i, cluster in enumerate(clusters):
            docs = cluster.get("documents", [])
            snippet = "; ".join(docs[:3])
            summaries.append(
                f"{i}: [size={len(cluster.get('references', []))}] {snippet}"
            )

        prompt = (
            "You are a software project manager. Below are groups of user feedback "
            "requests, each with an index, size, and sample content. "
            "Rank them by implementation priority, considering: user impact (cluster size), "
            "urgency or severity implied by the language, and whether requests conflict. "
            "Reply with ONLY a JSON array of indices in priority order, highest first. "
            "Example: [2, 0, 1]\n\n"
            + "\n".join(summaries)
        )

        try:
            response = httpx.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": OLLAMA_CHAT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
            content = body["message"]["content"].strip()

            # Extract JSON array from response.
            start = content.find("[")
            end = content.rfind("]") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON array in response")
            ranking: list[int] = json.loads(content[start:end])
            if not isinstance(ranking, list):
                raise ValueError("Response is not a list")

            # Reorder clusters; append any not mentioned by Ollama at the end.
            seen: set[int] = set()
            ordered: list[dict] = []
            for idx in ranking:
                if isinstance(idx, int) and 0 <= idx < len(clusters) and idx not in seen:
                    ordered.append(clusters[idx])
                    seen.add(idx)
            for i, cluster in enumerate(clusters):
                if i not in seen:
                    ordered.append(cluster)

            return ordered
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
            logger.warning(
                "Ollama unavailable or returned unparseable response — "
                "falling back to size-based ordering",
                exc_info=True,
            )
            return self._sort_by_size(clusters)

    @staticmethod
    def _sort_by_size(clusters: list[dict]) -> list[dict]:
        return sorted(clusters, key=lambda c: len(c.get("references", [])), reverse=True)
