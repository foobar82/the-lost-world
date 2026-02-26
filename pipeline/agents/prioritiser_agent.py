"""Prioritisation agent — selects and summarises top clusters via Ollama."""

import logging

from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class PrioritiserAgent(Agent):
    """Selects the highest-priority feedback clusters and summarises them."""

    @property
    def name(self) -> str:
        return "prioritise"

    def run(self, input: AgentInput) -> AgentOutput:
        logger.info("Would select and summarise top clusters via Ollama")
        return AgentOutput(
            data={"tasks": []},
            success=True,
            message="Prioritiser agent placeholder — returned empty task list",
            tokens_used=0,
        )
