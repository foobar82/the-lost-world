"""Base interface for all pipeline agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentInput:
    """Standard input to any agent."""

    data: Any
    context: dict  # Shared context (e.g. repo path, config, budget remaining)


@dataclass
class AgentOutput:
    """Standard output from any agent."""

    data: Any
    success: bool
    message: str  # Human-readable summary of what happened
    tokens_used: int  # For cost tracking


class Agent(ABC):
    """Base class for all pipeline agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def run(self, input: AgentInput) -> AgentOutput:
        pass
