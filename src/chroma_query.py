import os
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


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


def get_chroma_documents(prompt):
    try:
        collection = _get_collection()
        results = collection.query(
            query_texts=[prompt],
            n_results=CHROMA_RESULTS,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        # If the collection was dropped mid-run, rehydrate once and retry.
        try:
            collection = _get_collection()
            results = collection.query(
                query_texts=[prompt],
                n_results=CHROMA_RESULTS,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
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
    
