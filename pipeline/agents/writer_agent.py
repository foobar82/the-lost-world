"""Code Writer agent — generates code changes via Anthropic API."""

import logging

from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class WriterAgent(Agent):
    """Generates code changes to implement a prioritised task."""

    @property
    def name(self) -> str:
        return "write"

    def run(self, input: AgentInput) -> AgentOutput:
        logger.info("Would generate code changes via Anthropic API")
        return AgentOutput(
            data={"changes": [], "summary": "", "reasoning": ""},
            success=True,
            message="Writer agent placeholder — returned empty changeset",
            tokens_used=0,
        )
