import chroma_query


class FakeCollection:
    def __init__(self, results):
        self._results = results
        self.queries = 0

    def query(self, **kwargs):
        self.queries += 1
        return self._results


def _results(docs, dists):
    return {
        "documents": [docs],
        "metadatas": [[{} for _ in docs]],
        "distances": [dists],
    }


def test_max_distance_env_parsing(monkeypatch):
    monkeypatch.delenv("CHROMA_MAX_DISTANCE", raising=False)
    assert chroma_query._max_distance() is None
    monkeypatch.setenv("CHROMA_MAX_DISTANCE", "0.6")
    assert chroma_query._max_distance() == 0.6
    monkeypatch.setenv("CHROMA_MAX_DISTANCE", "not-a-number")
    assert chroma_query._max_distance() is None


def test_get_chroma_documents_applies_threshold(monkeypatch):
    coll = FakeCollection(_results(["near", "far"], [0.2, 0.9]))
    monkeypatch.setattr(chroma_query, "_get_collection", lambda: coll)
    monkeypatch.setenv("CHROMA_MAX_DISTANCE", "0.5")

    hits = chroma_query.get_chroma_documents("q")
    texts = [h["text"] for h in hits]
    assert texts == ["near"]  # 'far' dropped by threshold


def test_get_chroma_documents_no_threshold_returns_all(monkeypatch):
    coll = FakeCollection(_results(["a", "b"], [0.2, 0.9]))
    monkeypatch.setattr(chroma_query, "_get_collection", lambda: coll)
    monkeypatch.delenv("CHROMA_MAX_DISTANCE", raising=False)

    hits = chroma_query.get_chroma_documents("q")
    assert [h["text"] for h in hits] == ["a", "b"]


def test_get_chroma_documents_retries_then_gives_up(monkeypatch):
    attempts = {"n": 0}

    def failing_query(_prompt):
        attempts["n"] += 1
        raise RuntimeError("NotFoundError")

    monkeypatch.setattr(chroma_query, "_query_collection", failing_query)
    monkeypatch.setattr(chroma_query.time, "sleep", lambda *_: None)

    hits = chroma_query.get_chroma_documents("q")
    assert hits == []
    assert attempts["n"] == 2  # initial + one retry
