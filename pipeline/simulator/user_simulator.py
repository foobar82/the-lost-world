"""User Emulation Agent — generates synthetic user feedback via an LLM.

The agent reads the current app state and generates feedback as a user
with a defined persona would write it. See docs/user-emulation-agent.md
for the full design rationale.

Output has two channels:
1. Synthetic feedback items submitted to the backend API (source: "simulator")
2. A reasoning trace saved to pipeline/data/simulator/<timestamp>.json
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..agents.base import Agent, AgentInput, AgentOutput
from ..budget import check_budget, record_usage
from ..constants import DEFAULT_WRITER_MODEL, HTTP_TIMEOUT_SECONDS
from ..utils.embeddings import generate_embedding, get_collection
from .context_builder import build_context
from .persona import DEFAULT_PERSONA, PERSONAS, Persona

logger = logging.getLogger(__name__)

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]
    logger.warning("anthropic package not installed — UserSimulatorAgent unavailable")

_TRACE_DIR = Path(__file__).resolve().parents[2] / "pipeline" / "data" / "simulator"

_SYSTEM_PROMPT = """\
You are a user emulation agent for "The Lost World" — an evolving 2D ecosystem simulation.

Your job is to simulate how a real user would experience the app and what feedback they \
might submit. You are NOT pretending to be human: you are an agent reasoning about \
human experience.

Use this framing throughout: "I am an agent and I believe a user would notice X, \
causing them to do Z, given they have characteristics Y."

Rules:
- Write each feedback item as the user would type it — direct, plain language, no \
  technical jargon (unless the persona is technical).
- Focus on observations and desires about the ecosystem, not implementation details.
- Express problems, not solutions: "the predators seem to disappear too quickly" \
  rather than "increase predator respawn rate".
- Also consider: what would cause a user to disengage without saying anything? If you \
  identify such a scenario, include it as a feedback item even if the real user might \
  not articulate it — approximate their likely phrasing.
- Do not repeat requests that are already pending or recently completed (the context \
  will show you what exists).

Respond ONLY with valid JSON. No markdown fences. No text outside the JSON.

Output format:
{
  "feedback_items": ["...", "..."],
  "reasoning": "Brief explanation: what you noticed, what you considered, why you \
generated these specific items"
}
"""


def _build_user_prompt(
    persona: Persona,
    source_summary: str,
    recent_changes: str,
    recently_completed: str,
    n_items: int,
) -> str:
    return f"""\
## Your persona
{persona.description}

## What exists in the app currently
{source_summary}

## What has changed recently
{recent_changes}

## What has already been requested and built
{recently_completed}

## Your task
Generate {n_items} feedback submission(s) as this user would write them.
"""


def _extract_json(text: str) -> dict | None:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _save_trace(trace: dict) -> Path:
    _TRACE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = _TRACE_DIR / f"{ts}.json"
    path.write_text(json.dumps(trace, indent=2))
    return path


class UserSimulatorAgent(Agent):
    """Generates synthetic user feedback using a persona and app context."""

    @property
    def name(self) -> str:
        return "user_simulator"

    def run(self, input: AgentInput) -> AgentOutput:
        """
        input.data: dict with keys:
            n_items (int): number of feedback items to generate
            persona_name (str): key into PERSONAS dict
            api_base_url (str): e.g. "http://localhost:8000"
            repo_path (str): path to the repo root
            dry_run (bool): if True, skip submission and DB write
        input.context: pipeline config dict
        """
        if anthropic is None:
            return AgentOutput(
                data={}, success=False,
                message="anthropic package not installed",
                tokens_used=0,
            )

        params = input.data or {}
        n_items: int = params.get("n_items", 3)
        persona_name: str = params.get("persona_name", "curious_explorer")
        api_base_url: str = params.get("api_base_url", "http://localhost:8000")
        repo_path: str = params.get("repo_path", ".")
        dry_run: bool = params.get("dry_run", False)
        model: str = input.context.get("writer_model", DEFAULT_WRITER_MODEL)
        ollama_url: str = input.context.get("ollama_url", "http://localhost:11434")

        persona = PERSONAS.get(persona_name, DEFAULT_PERSONA)

        budget = check_budget()
        if not budget["allowed"]:
            return AgentOutput(
                data={}, success=True,
                message="Budget exhausted — skipping simulation",
                tokens_used=0,
            )

        # Build context from source files, git log, and done feedback.
        context = build_context(repo_path=repo_path, api_base_url=api_base_url)

        user_prompt = _build_user_prompt(
            persona=persona,
            source_summary=context["source_summary"],
            recent_changes=context["recent_changes"],
            recently_completed=context["recently_completed"],
            n_items=n_items,
        )

        # Call the LLM.
        client = anthropic.Anthropic()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception:
            logger.exception("UserSimulatorAgent: Anthropic API call failed")
            return AgentOutput(
                data={}, success=False,
                message="Anthropic API call failed",
                tokens_used=0,
            )

        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        record_usage(tokens_used)

        raw_text = response.content[0].text.strip()
        parsed = _extract_json(raw_text)

        if parsed is None or "feedback_items" not in parsed:
            logger.warning("UserSimulatorAgent: could not parse LLM response as JSON")
            trace = {
                "persona": persona.name,
                "model": model,
                "tokens_used": tokens_used,
                "raw_response": raw_text,
                "submitted": [],
                "skipped": [],
                "error": "Could not parse LLM response as JSON",
            }
            if not dry_run:
                _save_trace(trace)
            return AgentOutput(
                data=trace, success=False,
                message="Could not parse LLM response as JSON",
                tokens_used=tokens_used,
            )

        feedback_items: list[str] = parsed.get("feedback_items", [])
        reasoning: str = parsed.get("reasoning", "")

        submitted, skipped = self._submit_items(
            items=feedback_items,
            api_base_url=api_base_url,
            ollama_url=ollama_url,
            dry_run=dry_run,
        )

        trace = {
            "persona": persona.name,
            "model": model,
            "tokens_used": tokens_used,
            "reasoning": reasoning,
            "submitted": submitted,
            "skipped": skipped,
            "dry_run": dry_run,
        }

        if not dry_run:
            trace_path = _save_trace(trace)
            logger.info("Saved reasoning trace to %s", trace_path)

        msg = f"Submitted {len(submitted)} item(s), skipped {len(skipped)} duplicate(s)"
        if dry_run:
            msg = f"[dry-run] {msg}"

        logger.info("UserSimulatorAgent: %s", msg)
        return AgentOutput(
            data=trace,
            success=True,
            message=msg,
            tokens_used=tokens_used,
        )

    def _submit_items(
        self,
        items: list[str],
        api_base_url: str,
        ollama_url: str,
        dry_run: bool,
    ) -> tuple[list[str], list[dict]]:
        """Deduplicate against ChromaDB then submit each item.

        Returns (submitted_items, skipped_items).
        """
        submitted: list[str] = []
        skipped: list[dict] = []

        for item in items:
            # Deduplication: check semantic similarity against existing feedback.
            skip_reason = self._check_duplicate(item, ollama_url=ollama_url)
            if skip_reason:
                skipped.append({"item": item, "reason": skip_reason})
                logger.info("Skipping duplicate: %s — %s", item[:60], skip_reason)
                continue

            if dry_run:
                submitted.append(item)
                continue

            try:
                response = httpx.post(
                    f"{api_base_url}/api/feedback",
                    json={"content": item, "source": "simulator"},
                    timeout=HTTP_TIMEOUT_SECONDS * 2,
                )
                response.raise_for_status()
                submitted.append(item)
                logger.info("Submitted: %s", item[:80])
            except (httpx.HTTPError, httpx.TimeoutException):
                logger.warning("Failed to submit item: %s", item[:80], exc_info=True)
                skipped.append({"item": item, "reason": "API submission failed"})

        return submitted, skipped

    def _check_duplicate(self, text: str, ollama_url: str) -> str | None:
        """Return a reason string if text is too similar to existing feedback, else None."""
        from ..constants import CLUSTER_DISTANCE_THRESHOLD

        embedding = generate_embedding(text, ollama_url=ollama_url)
        if embedding is None:
            # Can't check — allow through rather than block on unavailable Ollama.
            return None

        try:
            collection = get_collection()
            count = collection.count()
            if count == 0:
                return None

            results = collection.query(
                query_embeddings=[embedding],
                n_results=min(count, 5),
                include=["documents", "distances"],
            )

            ids = results["ids"][0]
            distances = results["distances"][0]
            docs = results["documents"][0]

            for rid, dist, doc in zip(ids, distances, docs):
                if dist <= CLUSTER_DISTANCE_THRESHOLD:
                    return f"Too similar to existing item {rid}: '{doc[:60]}' (distance={dist:.3f})"

        except Exception:
            logger.debug("ChromaDB deduplication check failed — allowing item through", exc_info=True)

        return None
