"""Tests for the cluster agent with mocked ChromaDB."""

import sys
from pathlib import Path

import chromadb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.agents.base import AgentInput, AgentOutput  # noqa: E402
from pipeline.agents.cluster_agent import ClusterAgent, DISTANCE_THRESHOLD  # noqa: E402
from pipeline.utils.embeddings import set_chromadb_client  # noqa: E402


@pytest.fixture(autouse=True)
def _ephemeral_chromadb():
    """Swap in an ephemeral ChromaDB client for every test."""
    client = chromadb.EphemeralClient()
    set_chromadb_client(client)
    yield
    set_chromadb_client(None)


@pytest.fixture()
def agent():
    return ClusterAgent()


def _make_input(refs: list[str] | None) -> AgentInput:
    return AgentInput(data=refs, context={})


def _seed_collection(ids: list[str], embeddings: list[list[float]], documents: list[str]):
    """Insert test data into the ephemeral ChromaDB collection."""
    from pipeline.utils.embeddings import get_collection
    collection = get_collection()
    collection.upsert(ids=ids, embeddings=embeddings, documents=documents)
    return collection


# ---------------------------------------------------------------------------
# No-op cases
# ---------------------------------------------------------------------------


class TestClusterAgentEmpty:
    def test_none_input_returns_empty(self, agent):
        result = agent.run(_make_input(None))
        assert isinstance(result, AgentOutput)
        assert result.success is True
        assert result.data["clusters"] == []

    def test_empty_list_returns_empty(self, agent):
        result = agent.run(_make_input([]))
        assert result.success is True
        assert result.data["clusters"] == []

    def test_refs_not_in_chromadb_returns_empty(self, agent):
        result = agent.run(_make_input(["LW-999"]))
        assert result.success is True
        assert result.data["clusters"] == []


# ---------------------------------------------------------------------------
# Clustering behaviour
# ---------------------------------------------------------------------------


class TestClusterAgentClustering:
    def test_single_item_forms_one_cluster(self, agent):
        _seed_collection(
            ids=["LW-001"],
            embeddings=[[1.0] * 768],
            documents=["Add fish to the lake"],
        )
        result = agent.run(_make_input(["LW-001"]))
        assert result.success is True
        clusters = result.data["clusters"]
        assert len(clusters) == 1
        assert clusters[0]["references"] == ["LW-001"]
        assert clusters[0]["documents"] == ["Add fish to the lake"]

    def test_similar_items_cluster_together(self, agent):
        # Two very similar embeddings should end up in the same cluster.
        base = [1.0] * 768
        nearby = [1.01] * 768
        _seed_collection(
            ids=["LW-001", "LW-002"],
            embeddings=[base, nearby],
            documents=["Add fish", "Add more fish"],
        )
        result = agent.run(_make_input(["LW-001", "LW-002"]))
        clusters = result.data["clusters"]
        assert len(clusters) == 1
        assert set(clusters[0]["references"]) == {"LW-001", "LW-002"}

    def test_dissimilar_items_form_separate_clusters(self, agent):
        # Two very different embeddings should form separate clusters.
        vec_a = [1.0] + [0.0] * 767
        vec_b = [0.0] * 767 + [1.0]
        _seed_collection(
            ids=["LW-001", "LW-002"],
            embeddings=[vec_a, vec_b],
            documents=["Add fish", "Change the colour scheme"],
        )
        result = agent.run(_make_input(["LW-001", "LW-002"]))
        clusters = result.data["clusters"]
        assert len(clusters) == 2

    def test_clusters_sorted_largest_first(self, agent):
        # Three similar items + one outlier = one cluster of 3 + one of 1.
        base = [1.0] * 768
        similar_1 = [1.001] * 768
        similar_2 = [1.002] * 768
        outlier = [0.0] * 767 + [1.0]
        _seed_collection(
            ids=["LW-001", "LW-002", "LW-003", "LW-004"],
            embeddings=[base, similar_1, similar_2, outlier],
            documents=["Fish A", "Fish B", "Fish C", "Colour change"],
        )
        result = agent.run(_make_input(["LW-001", "LW-002", "LW-003", "LW-004"]))
        clusters = result.data["clusters"]
        assert len(clusters) == 2
        assert len(clusters[0]["references"]) >= len(clusters[1]["references"])

    def test_only_clusters_pending_refs(self, agent):
        """Items in ChromaDB but not in the pending refs list are excluded."""
        base = [1.0] * 768
        _seed_collection(
            ids=["LW-001", "LW-002"],
            embeddings=[base, [1.001] * 768],
            documents=["Fish", "More fish"],
        )
        # Only pass LW-001 as pending.
        result = agent.run(_make_input(["LW-001"]))
        clusters = result.data["clusters"]
        assert len(clusters) == 1
        assert clusters[0]["references"] == ["LW-001"]


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


class TestClusterAgentOutput:
    def test_uses_zero_tokens(self, agent):
        result = agent.run(_make_input(None))
        assert result.tokens_used == 0

    def test_message_is_descriptive(self, agent):
        _seed_collection(
            ids=["LW-001"],
            embeddings=[[1.0] * 768],
            documents=["Test"],
        )
        result = agent.run(_make_input(["LW-001"]))
        assert "1" in result.message
