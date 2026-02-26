"""Evil Filter agent — classifies feedback as safe or harmful via Ollama."""

import logging

from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class FilterAgent(Agent):
    """Classifies whether a feedback submission is safe or harmful."""

    @property
    def name(self) -> str:
        return "filter"

    def run(self, input: AgentInput) -> AgentOutput:
        logger.info("Would classify feedback as safe/harmful via Ollama")
        return AgentOutput(
            data={"verdict": "safe", "reason": "placeholder"},
            success=True,
            message="Filter agent placeholder — passed all input as safe",
            tokens_used=0,
        )
