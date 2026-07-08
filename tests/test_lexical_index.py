"""Tests for the dependency-free BM25 lexical index."""

import lexical_index
from lexical_index import BM25, lexical_search, tokenize


def test_tokenize_splits_identifiers_and_versions():
    assert tokenize("StorageMap") == ["storage", "map"]
    assert tokenize("msg_sender") == ["msg", "sender"]
    assert tokenize("cargo stylus check!") == ["cargo", "stylus", "check"]
    assert tokenize("stylus-sdk-rs v0.10.8") == ["stylus", "sdk", "rs", "v0", "10", "8"]
    assert tokenize("") == []
    assert tokenize(None) == []


def test_bm25_ranks_relevant_document_first():
    docs = [
        "How to deploy a Stylus contract with cargo stylus deploy",
        "Defining storage with sol_storage and StorageMap",
        "Completely unrelated text about bananas and fruit",
    ]
    bm25 = BM25(docs)
    top = bm25.top_k("cargo stylus deploy", k=3)
    assert top, "expected at least one positive-scoring hit"
    assert top[0][0] == 0  # the deploy doc ranks first
    assert all(score > 0 for _, score in top)


def test_bm25_empty_corpus_is_safe():
    bm25 = BM25([])
    assert bm25.scores("anything") == []
    assert bm25.top_k("anything", 5) == []


class FakeLexCollection:
    def __init__(self, docs, metas=None):
        self._docs = docs
        self._metas = metas or [{} for _ in docs]
        self.get_calls = 0

    def count(self):
        return len(self._docs)

    def get(self, include=None):
        self.get_calls += 1
        return {
            "ids": [str(i) for i in range(len(self._docs))],
            "documents": self._docs,
            "metadatas": self._metas,
        }


def test_lexical_search_returns_hit_shape_and_caches(monkeypatch):
    lexical_index.reset_cache()
    coll = FakeLexCollection(
        ["cargo stylus check dry run", "erc20 token example", "banana bread"],
        metas=[{"url": "u0"}, {"url": "u1"}, {"url": "u2"}],
    )
    hits = lexical_search(coll, "cargo stylus check", k=2)
    assert hits and hits[0]["text"] == "cargo stylus check dry run"
    assert hits[0]["metadata"] == {"url": "u0"}
    assert hits[0]["distance"] is None
    assert "lexical_score" in hits[0]

    # second call at the same count reuses the cached index (no rebuild)
    lexical_search(coll, "erc20", k=1)
    assert coll.get_calls == 1


def test_cache_rebuilds_on_count_change(monkeypatch):
    lexical_index.reset_cache()
    c1 = FakeLexCollection(["one doc"])
    lexical_search(c1, "doc", k=1)
    c2 = FakeLexCollection(["one doc", "two doc", "three doc"])
    lexical_search(c2, "three", k=1)
    assert c2.get_calls == 1  # different count -> rebuilt from c2
