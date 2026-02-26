"""Code Reviewer agent — reviews proposed changes via Anthropic API."""

import logging

from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class ReviewerAgent(Agent):
    """Reviews code changes for correctness, security, and contract adherence."""

    @property
    def name(self) -> str:
        return "review"

    def run(self, input: AgentInput) -> AgentOutput:
        logger.info("Would review code changes via Anthropic API")
        return AgentOutput(
            data={"verdict": "approve", "comments": ""},
            success=True,
            message="Reviewer agent placeholder — auto-approved all changes",
            tokens_used=0,
        )
