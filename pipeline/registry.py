"""Agent registry — maps step names to agent instances."""

from .agents.cluster_agent import ClusterAgent
from .agents.deployer_agent import DeployerAgent
from .agents.filter_agent import FilterAgent
from .agents.prioritiser_agent import PrioritiserAgent
from .agents.reviewer_agent import ReviewerAgent
from .agents.specifier_agent import SpecifierAgent
from .agents.writer_agent import WriterAgent

AGENTS = {
    "filter": FilterAgent(),
    "cluster": ClusterAgent(),
    "prioritise": PrioritiserAgent(),
    "specify": SpecifierAgent(),
    "write": WriterAgent(),
    "review": ReviewerAgent(),
    "deploy": DeployerAgent(),
}
