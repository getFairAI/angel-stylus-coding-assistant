import feedback_store


class FakeCollection:
    def __init__(self, query_result=None, raise_on_query=False):
        self._query_result = query_result or {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        self._raise_on_query = raise_on_query
        self.upserts = []
        self.where_seen = []

    def upsert(self, documents, metadatas, ids):
        self.upserts.append((documents, metadatas, ids))

    def query(self, **kwargs):
        self.where_seen.append(kwargs.get("where"))
        if self._raise_on_query:
            raise RuntimeError("boom")
        return self._query_result


def test_index_document_skips_non_positive(monkeypatch):
    monkeypatch.setattr(feedback_store, "_get_feedback_collection", lambda: FakeCollection())
    assert feedback_store._index_document_if_positive(
        prompt="p", response="r", rating=0
    ) is None


def test_index_document_upserts_positive(monkeypatch):
    coll = FakeCollection()
    monkeypatch.setattr(feedback_store, "_get_feedback_collection", lambda: coll)
    ok = feedback_store._index_document_if_positive(
        prompt="p", response="r", rating=1, doc_id="x1"
    )
    assert ok is True
    assert coll.upserts and coll.upserts[0][2] == ["x1"]


def test_index_document_handles_collection_none(monkeypatch):
    monkeypatch.setattr(feedback_store, "_get_feedback_collection", lambda: None)
    assert feedback_store._index_document_if_positive(
        prompt="p", response="r", rating=1
    ) is None


def test_get_feedback_documents_filters_non_positive(monkeypatch):
    result = {
        "documents": [["good", "bad"]],
        "metadatas": [[{"rating": 1}, {"rating": 0}]],
        "distances": [[0.1, 0.2]],
    }
    monkeypatch.setattr(feedback_store, "_get_feedback_collection", lambda: FakeCollection(result))
    hits = feedback_store.get_feedback_documents("q")
    assert [h["text"] for h in hits] == ["good"]


def test_get_feedback_documents_query_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(
        feedback_store, "_get_feedback_collection", lambda: FakeCollection(raise_on_query=True)
    )
    assert feedback_store.get_feedback_documents("q") == []


def test_get_conversation_documents_builds_and_filter(monkeypatch):
    coll = FakeCollection({"documents": [["c"]], "metadatas": [[{}]], "distances": [[0.3]]})
    monkeypatch.setattr(feedback_store, "_get_feedback_collection", lambda: coll)
    feedback_store.get_conversation_documents("q", session_id="s1")
    assert coll.where_seen[0] == {
        "$and": [{"source": "conversation"}, {"session_id": "s1"}]
    }


def test_get_conversation_documents_single_filter_without_session(monkeypatch):
    coll = FakeCollection()
    monkeypatch.setattr(feedback_store, "_get_feedback_collection", lambda: coll)
    feedback_store.get_conversation_documents("q")
    assert coll.where_seen[0] == {"source": "conversation"}


def test_record_feedback_normalizes_and_indexes(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    indexed = {}

    def fake_index(**kwargs):
        indexed.update(kwargs)
        return True

    monkeypatch.setattr(feedback_store, "_index_document_if_positive", fake_index)
    fid = feedback_store.record_feedback(prompt="p", response="r", rating=1, skill="research")
    assert isinstance(fid, str) and fid
    assert indexed["rating"] == 1
    assert indexed["metadata"]["source"] == "user_feedback"
