"""Lightweight user feedback capture and retrieval utilities.

The backend allows clients to submit a simple thumbs-up / thumbs-down signal
for a given prompt/response pair. Feedback events are:

- Logged to `logs/feedback_events.jsonl` for auditability.
- Optionally indexed into a dedicated Chroma collection so future queries can
  retrieve high-quality, user-validated snippets alongside the canonical docs.

The Chroma step is best-effort; any failures fall back to file logging only so
feedback submissions never break the API flow.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Dict, List, Optional

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

# -----------------------------
# File logging
# -----------------------------
# Allow overriding log location for tests and deployments. Read at call time so
# monkeypatch/setenv in tests takes effect.
def _log_dir() -> str:
    path = os.getenv("LOG_DIR", "logs")
    os.makedirs(path, exist_ok=True)
    return path


def _feedback_log_path() -> str:
    return os.path.join(_log_dir(), "feedback_events.jsonl")


def _write_feedback_event(event: Dict) -> None:
    with open(_feedback_log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# -----------------------------
# Chroma storage (best-effort)
# -----------------------------
CHROMA_PATH = "./chroma_db"
FEEDBACK_COLLECTION = "stylus_feedback"


def _get_feedback_collection():
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        return client.get_or_create_collection(
            name=FEEDBACK_COLLECTION,
            embedding_function=DefaultEmbeddingFunction(),
        )
    except Exception:
        # Returning None keeps API resilient even if Chroma is unavailable.
        return None


def _normalize_rating(value: int) -> int:
    if value not in (-1, 0, 1):
        raise ValueError("rating must be one of {-1, 0, 1}")
    return int(value)


def record_feedback(
    *,
    prompt: str,
    response: str,
    rating: int,
    skill: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> str:
    """Persist a feedback event and index it for retrieval when possible.

    Returns the generated feedback_id.
    """

    rating = _normalize_rating(rating)
    feedback_id = str(uuid.uuid4())
    timestamp = int(time.time())

    event = {
        "id": feedback_id,
        "timestamp": timestamp,
        "prompt": prompt,
        "response": response,
        "rating": rating,
        "skill": skill,
    }
    if metadata:
        event["metadata"] = metadata

    _write_feedback_event(event)

    # Only index positive feedback into Chroma to avoid polluting retrieval.
    if rating > 0:
        collection = _get_feedback_collection()
        if collection is not None:
            try:
                doc = f"Prompt: {prompt}\n\nAssistant response:\n{response}"
                collection.add(
                    documents=[doc],
                    metadatas=[{
                        "source": "user_feedback",
                        "rating": rating,
                        "skill": skill or "",
                        **(metadata or {}),
                    }],
                    ids=[feedback_id],
                )
            except Exception:
                # Ignore indexing errors; logging already captured the event.
                pass

    return feedback_id


def get_feedback_documents(prompt: str, n_results: int = 5) -> List[Dict]:
    """Return Chroma hits from user-approved feedback documents.

    If Chroma is unavailable or empty, an empty list is returned.
    """

    collection = _get_feedback_collection()
    if collection is None:
        return []

    try:
        results = collection.query(
            query_texts=[prompt],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    hits = []
    for idx, doc in enumerate(documents):
        meta = (metadatas[idx] if idx < len(metadatas) else {}) or {}
        # Skip anything that is not explicitly positive feedback.
        if meta.get("rating", 0) <= 0:
            continue
        hits.append(
            {
                "text": doc,
                "metadata": meta,
                "distance": distances[idx] if idx < len(distances) else None,
            }
        )
    return hits
