"""Tests for pipeline.utils.embeddings — mocked Ollama, real ephemeral ChromaDB."""

import sys
from pathlib import Path
from unittest.mock import patch

import chromadb
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))

from utils.embeddings import (  # noqa: E402
    generate_embedding,
    get_collection,
    set_chromadb_client,
    store_feedback_embedding,
)

FAKE_EMBEDDING = [0.1] * 768  # nomic-embed-text returns 768-dimensional vectors
OLLAMA_REQUEST = httpx.Request("POST", "http://localhost:11434/api/embeddings")


@pytest.fixture(autouse=True)
def _ephemeral_chromadb():
    """Swap in an ephemeral (in-memory) ChromaDB client for every test."""
    client = chromadb.EphemeralClient()
    set_chromadb_client(client)
    yield
    set_chromadb_client(None)


# ---------------------------------------------------------------------------
# generate_embedding
# ---------------------------------------------------------------------------


class TestGenerateEmbedding:
    def test_returns_embedding_on_success(self):
        fake_response = httpx.Response(200, json={"embedding": FAKE_EMBEDDING}, request=OLLAMA_REQUEST)
        with patch("utils.embeddings.httpx.post", return_value=fake_response):
            result = generate_embedding("hello world")
        assert result == FAKE_EMBEDDING

    def test_returns_none_when_ollama_is_unreachable(self):
        with patch("utils.embeddings.httpx.post", side_effect=httpx.ConnectError("refused")):
            result = generate_embedding("hello world")
        assert result is None

    def test_returns_none_on_http_error(self):
        fake_response = httpx.Response(500, json={"error": "model not loaded"}, request=OLLAMA_REQUEST)
        with patch("utils.embeddings.httpx.post", return_value=fake_response):
            result = generate_embedding("hello world")
        assert result is None

    def test_returns_none_when_response_missing_embedding_key(self):
        fake_response = httpx.Response(200, json={"unexpected": "payload"}, request=OLLAMA_REQUEST)
        with patch("utils.embeddings.httpx.post", return_value=fake_response):
            result = generate_embedding("hello world")
        assert result is None


# ---------------------------------------------------------------------------
# store_feedback_embedding
# ---------------------------------------------------------------------------


class TestStoreFeedbackEmbedding:
    def test_stores_embedding_and_returns_true(self):
        fake_response = httpx.Response(200, json={"embedding": FAKE_EMBEDDING}, request=OLLAMA_REQUEST)
        with patch("utils.embeddings.httpx.post", return_value=fake_response):
            ok = store_feedback_embedding("LW-001", "Add fish to the water")
        assert ok is True

        # Verify it's actually in ChromaDB
        collection = get_collection()
        result = collection.get(ids=["LW-001"], include=["documents", "embeddings"])
        assert result["ids"] == ["LW-001"]
        assert result["documents"] == ["Add fish to the water"]
        assert list(result["embeddings"][0]) == pytest.approx(FAKE_EMBEDDING)

    def test_returns_false_when_ollama_is_down(self):
        with patch("utils.embeddings.httpx.post", side_effect=httpx.ConnectError("refused")):
            ok = store_feedback_embedding("LW-002", "Some feedback")
        assert ok is False

        # Nothing stored in ChromaDB
        collection = get_collection()
        result = collection.get(ids=["LW-002"])
        assert result["ids"] == []

    def test_upsert_overwrites_existing_embedding(self):
        """Calling store twice for the same reference updates rather than duplicates."""
        first = httpx.Response(200, json={"embedding": FAKE_EMBEDDING}, request=OLLAMA_REQUEST)
        second_embedding = [0.2] * 768
        second = httpx.Response(200, json={"embedding": second_embedding}, request=OLLAMA_REQUEST)

        with patch("utils.embeddings.httpx.post", return_value=first):
            store_feedback_embedding("LW-003", "Original text")
        with patch("utils.embeddings.httpx.post", return_value=second):
            store_feedback_embedding("LW-003", "Updated text")

        collection = get_collection()
        result = collection.get(ids=["LW-003"], include=["documents", "embeddings"])
        assert result["documents"] == ["Updated text"]
        assert list(result["embeddings"][0]) == pytest.approx(second_embedding)


# ---------------------------------------------------------------------------
# get_collection
# ---------------------------------------------------------------------------


class TestGetCollection:
    def test_collection_name(self):
        collection = get_collection()
        assert collection.name == "feedback_embeddings"

    def test_collection_is_reusable(self):
        """Calling get_collection twice returns the same collection."""
        c1 = get_collection()
        c2 = get_collection()
        assert c1.name == c2.name
