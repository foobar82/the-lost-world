"""Prioritisation agent — selects and summarises top clusters via Ollama."""

import logging

import httpx

from ..budget import COST_PER_TOKEN_GBP, check_budget, record_usage
from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
CHAT_MODEL = "llama3.1:8b"

# Estimated token overhead per summarisation call (Ollama doesn't always
# report exact token counts, so we use a conservative estimate).
ESTIMATED_TOKENS_PER_SUMMARY = 500


class PrioritiserAgent(Agent):
    """Selects the highest-priority feedback clusters and summarises them."""

    @property
    def name(self) -> str:
        return "prioritise"

    def run(self, input: AgentInput) -> AgentOutput:
        clusters: list[dict] = input.data if isinstance(input.data, list) else []
        ollama_url = input.context.get("ollama_url", OLLAMA_URL)

        if not clusters:
            logger.info("No clusters to prioritise")
            return AgentOutput(
                data={"tasks": []},
                success=True,
                message="No clusters provided",
                tokens_used=0,
            )

        budget = check_budget()
        if not budget["allowed"]:
            logger.warning("Budget exhausted — skipping prioritisation")
            return AgentOutput(
                data={"tasks": []},
                success=True,
                message="Budget exhausted — no tasks selected",
                tokens_used=0,
            )

        tasks = []
        total_tokens = 0

        for cluster in clusters:
            # Check budget before each summarisation call.
            remaining = check_budget()
            estimated_cost = ESTIMATED_TOKENS_PER_SUMMARY * COST_PER_TOKEN_GBP
            if remaining["daily_remaining"] < estimated_cost:
                logger.info("Daily budget too low for another summary — stopping")
                break

            documents = cluster.get("documents", [])
            references = cluster.get("references", [])

            summary, tokens_used = self._summarise_cluster(documents, ollama_url)
            total_tokens += tokens_used

            if tokens_used > 0:
                record_usage(tokens_used)

            tasks.append({
                "references": references,
                "documents": documents,
                "summary": summary,
                "cluster_size": len(references),
            })

        logger.info("Prioritised %d task(s) using %d tokens", len(tasks), total_tokens)
        return AgentOutput(
            data={"tasks": tasks},
            success=True,
            message=f"Prioritised {len(tasks)} task(s)",
            tokens_used=total_tokens,
        )

    def _summarise_cluster(self, documents: list[str], ollama_url: str) -> tuple[str, int]:
        """Generate a brief task summary for a cluster of feedback documents.

        Returns (summary_text, tokens_used).
        """
        combined = "\n".join(f"- {doc}" for doc in documents)
        prompt = (
            "Below is a group of related user feedback submissions for a software project. "
            "Write a single brief task summary (1-2 sentences) that captures the common "
            "theme or request.\n\n"
            f"{combined}\n\n"
            "Task summary:"
        )

        try:
            response = httpx.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": CHAT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                timeout=30,
            )
            response.raise_for_status()
            body = response.json()
            summary = body["message"]["content"].strip()

            # Ollama may report token counts in eval_count / prompt_eval_count.
            tokens = body.get("eval_count", 0) + body.get("prompt_eval_count", 0)
            if tokens == 0:
                tokens = ESTIMATED_TOKENS_PER_SUMMARY

            return summary, tokens
        except (httpx.HTTPError, KeyError, ValueError):
            logger.warning("Ollama unavailable for summarisation — using fallback",
                           exc_info=True)
            fallback = f"Cluster of {len(documents)} related feedback item(s)"
            return fallback, 0
