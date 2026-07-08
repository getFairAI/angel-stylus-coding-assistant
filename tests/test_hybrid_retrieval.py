"""Tests for hybrid (dense + BM25) retrieval fusion in chroma_query."""

import chroma_query
import lexical_index


class FakeLexCollection:
    def __init__(self, docs):
        self._docs = docs

    def count(self):
        return len(self._docs)

    def get(self, include=None):
        return {
            "ids": [str(i) for i in range(len(self._docs))],
            "documents": self._docs,
            "metadatas": [{} for _ in self._docs],
        }


def _dense(text, distance):
    return {"text": text, "metadata": {}, "distance": distance}


def test_rrf_fuse_dedups_and_orders():
    dense = [_dense("A", 0.2), _dense("B", 0.3)]
    lexical = [
        {"text": "B", "metadata": {}, "distance": None},  # appears in both -> boosted
        {"text": "C", "metadata": {}, "distance": None},  # lexical only
    ]
    fused = chroma_query._rrf_fuse(dense, lexical, rrf_k=60, limit=10)
    texts = [h["text"] for h in fused]
    assert texts[0] == "B"  # in both lists -> highest fused score
    assert set(texts) == {"A", "B", "C"}
    # the retained "B" is the dense object (keeps its distance)
    b = next(h for h in fused if h["text"] == "B")
    assert b["distance"] == 0.3


def test_hybrid_empty_dense_returns_empty_without_lexical(monkeypatch):
    monkeypatch.setattr(chroma_query, "_dense_documents", lambda p: [])
    called = {"lex": False}

    def _boom():
        called["lex"] = True
        raise AssertionError("lexical should not run when dense is empty")

    monkeypatch.setattr(chroma_query, "_get_collection", _boom)
    assert chroma_query.get_hybrid_documents("off-topic") == []
    assert called["lex"] is False


def test_hybrid_fuses_dense_and_lexical(monkeypatch):
    lexical_index.reset_cache()
    monkeypatch.setattr(
        chroma_query, "_dense_documents",
        lambda p: [_dense("A dense doc about storage", 0.2)],
    )
    corpus = [
        "A dense doc about storage",
        "lexical only cargo stylus deploy guide",
        "unrelated banana content",
    ]
    monkeypatch.setattr(chroma_query, "_get_collection", lambda: FakeLexCollection(corpus))

    fused = chroma_query.get_hybrid_documents("cargo stylus deploy", limit=10)
    texts = [h["text"] for h in fused]
    assert "A dense doc about storage" in texts          # dense preserved
    assert "lexical only cargo stylus deploy guide" in texts  # lexical recall added


def test_hybrid_falls_back_to_dense_on_lexical_error(monkeypatch):
    dense_hits = [_dense("d", 0.1)]
    monkeypatch.setattr(chroma_query, "_dense_documents", lambda p: dense_hits)

    def _raise():
        raise RuntimeError("collection unavailable")

    monkeypatch.setattr(chroma_query, "_get_collection", _raise)
    assert chroma_query.get_hybrid_documents("q") == dense_hits


def test_flag_routes_to_hybrid(monkeypatch):
    monkeypatch.setenv("STYLUS_HYBRID_RETRIEVAL", "1")
    monkeypatch.setattr(chroma_query, "get_hybrid_documents", lambda p: ["HYBRID"])
    monkeypatch.setattr(chroma_query, "_dense_documents", lambda p: ["DENSE"])
    assert chroma_query.get_chroma_documents("q") == ["HYBRID"]

    monkeypatch.setenv("STYLUS_HYBRID_RETRIEVAL", "0")
    assert chroma_query.get_chroma_documents("q") == ["DENSE"]
