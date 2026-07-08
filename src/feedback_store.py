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
import logging
import os
import time
import uuid
from typing import Dict, List, Optional

from embeddings import get_chroma_client, get_or_reset_collection


logger = logging.getLogger(__name__)

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
FEEDBACK_COLLECTION = "stylus_feedback"


def _get_feedback_collection():
    try:
        client = get_chroma_client()
        # reset_on_conflict handles the one-time migration off legacy default
        # embeddings; without it the collection would stay unreadable forever.
        return get_or_reset_collection(
            client, FEEDBACK_COLLECTION, reset_on_conflict=True
        )
    except Exception as exc:
        logger.warning(
            "feedback collection unavailable (%s: %s)",
            type(exc).__name__, exc,
        )
        # Returning None keeps API resilient even if Chroma is unavailable.
        return None


def _index_document_if_positive(
    *,
    prompt: str,
    response: str,
    rating: int,
    metadata: Optional[Dict] = None,
    doc_id: Optional[str] = None,
):
    """Shared helper to index positive-rated text into the feedback collection."""
    if rating <= 0:
        return None
    collection = _get_feedback_collection()
    if collection is None:
        return None

    doc = f"Prompt: {prompt}\n\nAssistant response:\n{response}"
    try:
        # Upsert keeps re-rated turns idempotent (same doc_id) instead of
        # duplicating them across submissions.
        collection.upsert(
            documents=[doc],
            metadatas=[metadata or {}],
            ids=[doc_id or str(uuid.uuid4())],
        )
    except Exception as exc:  # best-effort; never break the API flow
        logger.warning(
            "feedback indexing failed (%s: %s)",
            type(exc).__name__, exc,
        )
        return None
    return True


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
    _index_document_if_positive(
        prompt=prompt,
        response=response,
        rating=rating,
        metadata={
            "source": "user_feedback",
            "rating": rating,
            "skill": skill or "",
            **(metadata or {}),
        },
        doc_id=feedback_id,
    )

    return feedback_id


def index_conversation_turn(
    *,
    session_id: str,
    turn_id: str,
    prompt: str,
    response: str,
    rating: int,
    skill: Optional[str] = None,
    metadata: Optional[Dict] = None,
):
    """Index a positively-rated conversation turn into the feedback collection."""

    _index_document_if_positive(
        prompt=prompt,
        response=response,
        rating=rating,
        metadata={
            "source": "conversation",
            "session_id": session_id,
            "turn_id": turn_id,
            "rating": rating,
            "skill": skill or "",
            **(metadata or {}),
        },
        doc_id=turn_id,
    )


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
    except Exception as exc:
        logger.warning(
            "feedback query failed (%s: %s)",
            type(exc).__name__, exc,
        )
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


def get_conversation_documents(prompt: str, n_results: int = 3, session_id: Optional[str] = None) -> List[Dict]:
    """Return positive-rated conversation turns as retriever hits."""
    collection = _get_feedback_collection()
    if collection is None:
        return []

    # Chroma requires a single top-level operator; combine multiple fields with $and.
    if session_id:
        filters = {
            "$and": [
                {"source": "conversation"},
                {"session_id": session_id},
            ]
        }
    else:
        filters = {"source": "conversation"}

    try:
        results = collection.query(
            query_texts=[prompt],
            n_results=n_results,
            where=filters,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.warning(
            "conversation query failed (%s: %s)",
            type(exc).__name__, exc,
        )
        return []

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    hits = []
    for idx, doc in enumerate(documents):
        meta = (metadatas[idx] if idx < len(metadatas) else {}) or {}
        hits.append(
            {
                "text": doc,
                "metadata": meta,
                "distance": distances[idx] if idx < len(distances) else None,
            }
        )
    return hits
