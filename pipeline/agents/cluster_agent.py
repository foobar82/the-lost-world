"""Clustering agent — groups pending feedback by similarity using ChromaDB."""

import logging

from ..constants import CHROMADB_MAX_RESULTS
from ..utils.embeddings import get_collection
from .base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)

# Maximum distance (L2) between embeddings to be considered "similar".
DISTANCE_THRESHOLD = 1.0


class ClusterAgent(Agent):
    """Queries ChromaDB and clusters pending feedback by embedding similarity."""

    @property
    def name(self) -> str:
        return "cluster"

    def run(self, input: AgentInput) -> AgentOutput:
        pending_refs: list[str] | None = input.data
        if not pending_refs:
            logger.info("No pending references supplied — nothing to cluster")
            return AgentOutput(
                data={"clusters": []},
                success=True,
                message="No pending submissions to cluster",
                tokens_used=0,
            )

        try:
            collection = get_collection()
            stored = collection.get(
                ids=pending_refs,
                include=["embeddings", "documents"],
            )
        except Exception:
            logger.exception("Failed to retrieve embeddings from ChromaDB")
            return AgentOutput(
                data={"clusters": []},
                success=False,
                message="ChromaDB query failed",
                tokens_used=0,
            )

        ids = stored["ids"]
        embeddings = stored["embeddings"]
        documents = stored["documents"]

        if not ids:
            logger.info("No embeddings found for pending references")
            return AgentOutput(
                data={"clusters": []},
                success=True,
                message="No embeddings found for pending submissions",
                tokens_used=0,
            )

        clusters = self._cluster_by_similarity(ids, embeddings, documents, collection)

        # Sort by cluster size, largest first.
        clusters.sort(key=lambda c: len(c["references"]), reverse=True)

        logger.info("Formed %d cluster(s) from %d submissions", len(clusters), len(ids))
        return AgentOutput(
            data={"clusters": clusters},
            success=True,
            message=f"Clustered {len(ids)} submissions into {len(clusters)} group(s)",
            tokens_used=0,
        )

    def _cluster_by_similarity(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        collection,
    ) -> list[dict]:
        """Group submissions using ChromaDB similarity search.

        For each unclustered submission, query ChromaDB for similar embeddings
        within DISTANCE_THRESHOLD and group them together.
        """
        clustered: set[str] = set()
        clusters: list[dict] = []

        for i, ref_id in enumerate(ids):
            if ref_id in clustered:
                continue

            # Query for similar embeddings using this item's vector.
            try:
                results = collection.query(
                    query_embeddings=[embeddings[i]],
                    n_results=min(len(ids), CHROMADB_MAX_RESULTS),
                    include=["documents", "distances"],
                )
            except Exception:
                logger.exception("Similarity query failed for %s", ref_id)
                # Fall back to a single-item cluster.
                clusters.append({
                    "references": [ref_id],
                    "documents": [documents[i]],
                })
                clustered.add(ref_id)
                continue

            result_ids = results["ids"][0]
            result_docs = results["documents"][0]
            result_distances = results["distances"][0]

            cluster_refs = []
            cluster_docs = []

            for rid, rdoc, dist in zip(result_ids, result_docs, result_distances):
                if rid in clustered:
                    continue
                if rid not in ids:
                    # Not a pending submission — skip.
                    continue
                if dist <= DISTANCE_THRESHOLD:
                    cluster_refs.append(rid)
                    cluster_docs.append(rdoc)
                    clustered.add(rid)

            if cluster_refs:
                clusters.append({
                    "references": cluster_refs,
                    "documents": cluster_docs,
                })

        return clusters
