import logging
import os
import time

from embeddings import CHROMA_SPACE, get_chroma_client, get_embedding_function


logger = logging.getLogger(__name__)

CHROMA_RESULTS = 25
COLLECTION_NAME = "stylus_chat_data"

# Cosine distance cutoff (0 = identical, 2 = opposite). Hits farther than this
# are treated as irrelevant so the API can honestly report `found: false`
# instead of returning 25 loosely-related chunks. None disables the filter.
def _max_distance():
    raw = os.getenv("CHROMA_MAX_DISTANCE", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid CHROMA_MAX_DISTANCE=%r; ignoring", raw)
        return None


def _get_collection():
    """Return a fresh collection handle each time to survive ingestion rebuilds."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": CHROMA_SPACE},
    )


def _query_collection(prompt):
    collection = _get_collection()
    return collection.query(
        query_texts=[prompt],
        n_results=CHROMA_RESULTS,
        include=["documents", "metadatas", "distances"],
    )


def get_chroma_documents(prompt):
    try:
        results = _query_collection(prompt)
    except Exception as exc:
        # Chroma 1.x shares a process-wide server singleton; if a collection UUID
        # rotates (migration, external delete), cached handles throw NotFoundError.
        # Sleep briefly to let the server refresh, then retry with a fresh handle.
        logger.warning(
            "chroma_query first attempt failed (%s: %s); retrying",
            type(exc).__name__, exc,
        )
        time.sleep(0.25)
        try:
            results = _query_collection(prompt)
        except Exception as exc2:
            logger.error(
                "chroma_query retry failed (%s: %s); returning empty hits",
                type(exc2).__name__, exc2,
            )
            return []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    max_distance = _max_distance()
    hits = []
    dropped = 0
    for idx, doc in enumerate(documents):
        distance = distances[idx] if idx < len(distances) else None
        if (
            max_distance is not None
            and distance is not None
            and distance > max_distance
        ):
            dropped += 1
            continue
        hits.append(
            {
                "text": doc,
                "metadata": (metadatas[idx] if idx < len(metadatas) else {}) or {},
                "distance": distance,
            }
        )
    if dropped:
        logger.info(
            "chroma_query dropped %d/%d hits above max_distance=%.3f",
            dropped, len(documents), max_distance,
        )
    return hits
    
