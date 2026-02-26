"""Clustering agent — groups pending feedback by similarity using ChromaDB."""

import logging

from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class ClusterAgent(Agent):
    """Queries ChromaDB and clusters pending feedback by embedding similarity."""

    @property
    def name(self) -> str:
        return "cluster"

    def run(self, input: AgentInput) -> AgentOutput:
        logger.info(
            "Would query ChromaDB and cluster pending feedback by similarity"
        )
        return AgentOutput(
            data={"clusters": []},
            success=True,
            message="Cluster agent placeholder — returned empty clusters",
            tokens_used=0,
        )
