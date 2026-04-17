import logging
import os
import time
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


logger = logging.getLogger(__name__)

CHROMA_RESULTS = 25
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = "stylus_chat_data"
embedding_fn = DefaultEmbeddingFunction()


def _get_collection():
    """Return a fresh collection handle each time to survive ingestion rebuilds."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
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

    hits = []
    for idx, doc in enumerate(documents):
        hits.append(
            {
                "text": doc,
                "metadata": (metadatas[idx] if idx < len(metadatas) else {}) or {},
                "distance": distances[idx] if idx < len(distances) else None,
            }
        )
    return hits
    
