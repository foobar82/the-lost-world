"""Base interface for all pipeline agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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


@dataclass
class FileChange:
    """A single file change produced by the writer agent."""

    path: str  # Relative to repo root
    action: str  # "create", "modify", "delete"
    content: str  # New file content (for create/modify); empty for delete


@dataclass
class WriterOutput:
    """Structured output from the writer agent."""

    changes: list[FileChange] = field(default_factory=list)
    summary: str = ""
    reasoning: str = ""


class Agent(ABC):
    """Base class for all pipeline agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def run(self, input: AgentInput) -> AgentOutput:
        pass
