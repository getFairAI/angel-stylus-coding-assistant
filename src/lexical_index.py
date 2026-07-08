"""Dependency-free BM25 lexical index over the Chroma collection.

Dense (vector) retrieval alone is weak on exact-token queries — API names, CLI
flags, version strings, snake_case/CamelCase identifiers — which matter a lot for
Stylus code. This module provides a keyword signal to fuse with the dense results
(see `chroma_query.get_hybrid_documents`).

No third-party deps: a compact postings-based BM25 in plain Python. The index is
built from the collection's documents and cached, rebuilt when the collection's
document count changes.
"""

from __future__ import annotations

import logging
import math
import re
import threading
from collections import Counter, defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def tokenize(text: Optional[str]) -> list[str]:
    """Lowercase alphanumeric tokens, with CamelCase split into subwords.

    `StorageMap` -> ['storage', 'map']; `msg_sender` -> ['msg', 'sender'];
    `cargo stylus check` -> ['cargo', 'stylus', 'check'].
    """
    spaced = _CAMEL_BOUNDARY.sub(" ", text or "")
    return _TOKEN_RE.findall(spaced.lower())


class BM25:
    """Okapi BM25 over a fixed document corpus, using an inverted index."""

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        tokenized = [tokenize(doc) for doc in documents]
        self.doc_len = [len(toks) for toks in tokenized]
        self.n = len(tokenized)
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 0.0

        # term -> list of (doc_index, term_frequency)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        df: Counter = Counter()
        for i, toks in enumerate(tokenized):
            counts = Counter(toks)
            for term, freq in counts.items():
                self.postings[term].append((i, freq))
                df[term] += 1

        # BM25 idf with +1 smoothing so scores stay non-negative
        self.idf = {
            term: math.log(1 + (self.n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def scores(self, query: str) -> list[float]:
        scores = [0.0] * self.n
        if not self.n or self.avgdl == 0.0:
            return scores
        for term in tokenize(query):
            idf = self.idf.get(term)
            if not idf:
                continue
            for doc_i, freq in self.postings.get(term, ()):  # only docs with the term
                denom = freq + self.k1 * (1 - self.b + self.b * self.doc_len[doc_i] / self.avgdl)
                scores[doc_i] += idf * (freq * (self.k1 + 1)) / denom
        return scores

    def top_k(self, query: str, k: int) -> list[tuple[int, float]]:
        scores = self.scores(query)
        ranked = sorted(range(self.n), key=lambda i: scores[i], reverse=True)
        return [(i, scores[i]) for i in ranked[:k] if scores[i] > 0]


# --- collection-backed cache -------------------------------------------------
_lock = threading.Lock()
_cache: dict = {"sig": None, "bm25": None, "documents": [], "metadatas": []}


def _collection_signature(collection) -> Optional[int]:
    try:
        return collection.count()
    except Exception:  # pragma: no cover - depends on chroma backend
        return None


def get_index(collection) -> dict:
    """Return a cached BM25 index for the collection, rebuilding on count change."""
    sig = _collection_signature(collection)
    with _lock:
        if _cache["bm25"] is not None and _cache["sig"] == sig:
            return _cache
        data = collection.get(include=["documents", "metadatas"])
        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        _cache.update(
            sig=sig,
            bm25=BM25(documents),
            documents=documents,
            metadatas=metadatas,
        )
        logger.info("lexical_index built BM25 over %d documents", len(documents))
        return _cache


def reset_cache() -> None:
    with _lock:
        _cache.update(sig=None, bm25=None, documents=[], metadatas=[])


def lexical_search(collection, query: str, k: int) -> list[dict]:
    """Top-k lexical hits shaped like dense hits (text/metadata/distance=None)."""
    cache = get_index(collection)
    bm25: BM25 = cache["bm25"]
    documents = cache["documents"]
    metadatas = cache["metadatas"]
    hits = []
    for i, score in bm25.top_k(query, k):
        hits.append(
            {
                "text": documents[i],
                "metadata": (metadatas[i] if i < len(metadatas) else {}) or {},
                "distance": None,
                "lexical_score": score,
            }
        )
    return hits
