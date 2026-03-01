"""Embedding utilities: generate embeddings via Ollama and store them in ChromaDB."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

try:
    from ..constants import EMBEDDING_MODEL, HTTP_TIMEOUT_SECONDS, OLLAMA_URL
except ImportError:
    # Fallback for tests that add pipeline/ directly to sys.path.
    from constants import EMBEDDING_MODEL, HTTP_TIMEOUT_SECONDS, OLLAMA_URL

logger = logging.getLogger(__name__)
CHROMADB_PATH = str(Path(__file__).resolve().parents[2] / "backend" / "data" / "chromadb")
COLLECTION_NAME = "feedback_embeddings"

# Lazy-import chromadb: Pydantic V1 (used internally by chromadb) is
# incompatible with Python 3.14+, so the import may fail at module-load time.
# Wrapping it here allows the rest of the pipeline to function normally.
try:
    import chromadb
except Exception:  # chromadb raises pydantic.v1.errors.ConfigError, not ImportError
    chromadb = None  # type: ignore[assignment]
    logger.warning(
        "chromadb could not be imported (Pydantic V1 is incompatible with "
        "Python 3.14+). Embedding storage and retrieval will be unavailable."
    )

_client: chromadb.ClientAPI | None = None
_chromadb_store_warned: bool = False


def get_chromadb_client(path: str | None = None) -> chromadb.ClientAPI:
    """Return a persistent ChromaDB client, creating it on first call."""
    global _client
    if chromadb is None:
        raise ImportError(
            "chromadb is not available — Pydantic V1 is incompatible with "
            "Python 3.14+. Downgrade to Python <=3.13 or wait for a chromadb "
            "release that migrates to Pydantic V2 settings."
        )
    if _client is None:
        _client = chromadb.PersistentClient(path=path or CHROMADB_PATH)
    return _client


def set_chromadb_client(client: chromadb.ClientAPI | None) -> None:
    """Override the module-level ChromaDB client (used by tests)."""
    global _client
    _client = client


def get_collection() -> chromadb.Collection:
    """Return the feedback_embeddings collection, creating it if needed."""
    return get_chromadb_client().get_or_create_collection(COLLECTION_NAME)


def generate_embedding(text: str, ollama_url: str | None = None) -> list[float] | None:
    """Call Ollama to generate an embedding vector for *text*.

    Returns None if Ollama is unreachable or returns an error.
    """
    url = f"{ollama_url or OLLAMA_URL}/api/embeddings"
    try:
        response = httpx.post(
            url,
            json={"model": EMBEDDING_MODEL, "prompt": text},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except (httpx.HTTPError, KeyError):
        logger.exception("Failed to generate embedding via Ollama")
        return None


def store_feedback_embedding(reference: str, text: str, ollama_url: str | None = None) -> bool:
    """Generate an embedding for *text* and store it in ChromaDB under *reference*.

    Returns True on success, False if the embedding could not be generated or stored.
    """
    embedding = generate_embedding(text, ollama_url=ollama_url)
    if embedding is None:
        return False

    try:
        collection = get_collection()
        collection.upsert(
            ids=[reference],
            embeddings=[embedding],
            documents=[text],
        )
        return True
    except Exception:
        global _chromadb_store_warned
        if not _chromadb_store_warned:
            logger.exception("Failed to store embedding in ChromaDB for %s", reference)
            _chromadb_store_warned = True
        else:
            logger.debug("Failed to store embedding in ChromaDB for %s", reference)
        return False
