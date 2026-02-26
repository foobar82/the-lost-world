"""Tests for the agent registry and base interface (Phase 3)."""

import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable so `pipeline` resolves as a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.agents.base import Agent, AgentInput, AgentOutput  # noqa: E402
from pipeline.registry import AGENTS  # noqa: E402

EXPECTED_KEYS = {"filter", "cluster", "prioritise", "write", "review", "deploy"}


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------


class TestRegistryCompleteness:
    def test_all_expected_agents_are_registered(self):
        assert set(AGENTS.keys()) == EXPECTED_KEYS

    def test_no_extra_agents_registered(self):
        assert len(AGENTS) == len(EXPECTED_KEYS)


# ---------------------------------------------------------------------------
# Interface compliance
# ---------------------------------------------------------------------------


class TestInterfaceCompliance:
    @pytest.mark.parametrize("step_name", sorted(EXPECTED_KEYS))
    def test_agent_is_instance_of_base_class(self, step_name):
        assert isinstance(AGENTS[step_name], Agent)

    @pytest.mark.parametrize("step_name", sorted(EXPECTED_KEYS))
    def test_agent_has_non_empty_name(self, step_name):
        agent = AGENTS[step_name]
        assert isinstance(agent.name, str)
        assert len(agent.name) > 0

    @pytest.mark.parametrize("step_name", sorted(EXPECTED_KEYS))
    def test_agent_name_matches_registry_key(self, step_name):
        assert AGENTS[step_name].name == step_name

    @pytest.mark.parametrize("step_name", sorted(EXPECTED_KEYS))
    def test_run_is_callable(self, step_name):
        assert callable(AGENTS[step_name].run)


# ---------------------------------------------------------------------------
# Skeleton agent execution
# ---------------------------------------------------------------------------


class TestSkeletonExecution:
    @pytest.mark.parametrize("step_name", sorted(EXPECTED_KEYS))
    def test_run_returns_agent_output(self, step_name):
        agent = AGENTS[step_name]
        result = agent.run(AgentInput(data=None, context={}))
        assert isinstance(result, AgentOutput)

    @pytest.mark.parametrize("step_name", sorted(EXPECTED_KEYS))
    def test_skeleton_returns_success(self, step_name):
        agent = AGENTS[step_name]
        result = agent.run(AgentInput(data=None, context={}))
        assert result.success is True

    @pytest.mark.parametrize("step_name", sorted(EXPECTED_KEYS))
    def test_skeleton_uses_zero_tokens(self, step_name):
        agent = AGENTS[step_name]
        result = agent.run(AgentInput(data=None, context={}))
        assert result.tokens_used == 0

    @pytest.mark.parametrize("step_name", sorted(EXPECTED_KEYS))
    def test_skeleton_has_non_empty_message(self, step_name):
        agent = AGENTS[step_name]
        result = agent.run(AgentInput(data=None, context={}))
        assert isinstance(result.message, str)
        assert len(result.message) > 0


# ---------------------------------------------------------------------------
# Registry swapping
# ---------------------------------------------------------------------------


class TestRegistrySwapping:
    def test_swap_agent_in_registry(self):
        """Replacing a registry entry with a custom agent works."""

        class CustomFilter(Agent):
            @property
            def name(self) -> str:
                return "filter"

            def run(self, input: AgentInput) -> AgentOutput:
                return AgentOutput(
                    data={"verdict": "reject", "reason": "custom"},
                    success=True,
                    message="Custom filter",
                    tokens_used=0,
                )

        original = AGENTS["filter"]
        try:
            AGENTS["filter"] = CustomFilter()
            result = AGENTS["filter"].run(AgentInput(data=None, context={}))
            assert result.data["verdict"] == "reject"
            assert isinstance(AGENTS["filter"], Agent)
        finally:
            AGENTS["filter"] = original
