import tempfile
import types

import chromadb
import pytest

import embeddings


def test_env_getters_defaults_and_overrides(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert embeddings.get_embedding_model() == embeddings.DEFAULT_EMBEDDING_MODEL
    assert embeddings.get_ollama_host() == embeddings.DEFAULT_OLLAMA_HOST

    monkeypatch.setenv("EMBEDDING_MODEL", "nomic-embed-text")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama:11434")
    assert embeddings.get_embedding_model() == "nomic-embed-text"
    assert embeddings.get_ollama_host() == "http://ollama:11434"
    assert embeddings.embedding_space_fingerprint() == "nomic-embed-text|cosine"


def test_embedding_function_config_protocol(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "mxbai-embed-large")
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    fn = embeddings.get_embedding_function()
    assert embeddings.OllamaEmbeddingFunction.name() == "ollama"
    cfg = fn.get_config()
    assert cfg == {"model": "mxbai-embed-large", "host": "http://localhost:11434"}
    rebuilt = embeddings.OllamaEmbeddingFunction.build_from_config(cfg)
    assert rebuilt.model == "mxbai-embed-large"
    assert rebuilt.host == "http://localhost:11434"


def test_embedding_function_call_uses_ollama_client(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, host):
            self.host = host

        def embeddings(self, model, prompt):
            calls.append((model, prompt))
            return {"embedding": [0.1, 0.2, 0.3]}

    monkeypatch.setattr(embeddings.ollama, "Client", FakeClient)
    fn = embeddings.OllamaEmbeddingFunction(model="m", host="http://h")
    out = fn(["a", "b"])
    # Chroma normalizes EF output to numpy arrays, so compare numerically.
    assert len(out) == 2
    assert all(list(map(float, row)) == pytest.approx([0.1, 0.2, 0.3], abs=1e-6) for row in out)
    assert {c[1] for c in calls} == {"a", "b"}
    assert all(c[0] == "m" for c in calls)


def test_check_ollama_ready_paths(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "mxbai-embed-large")

    class GoodClient:
        def __init__(self, host):
            pass

        def list(self):
            return {"models": [{"model": "mxbai-embed-large:latest"}]}

    monkeypatch.setattr(embeddings.ollama, "Client", GoodClient)
    ok, msg = embeddings.check_ollama_ready()
    assert ok and "ready" in msg.lower()

    class MissingModelClient(GoodClient):
        def list(self):
            return {"models": [{"model": "llama3"}]}

    monkeypatch.setattr(embeddings.ollama, "Client", MissingModelClient)
    ok, msg = embeddings.check_ollama_ready()
    assert not ok and "pull" in msg.lower()

    class BrokenClient:
        def __init__(self, host):
            raise ConnectionError("refused")

    monkeypatch.setattr(embeddings.ollama, "Client", BrokenClient)
    ok, msg = embeddings.check_ollama_ready()
    assert not ok and "not reachable" in msg.lower()


def test_get_chroma_client_http_mode(monkeypatch):
    captured = {}

    def fake_http(host, port):
        captured["host"] = host
        captured["port"] = port
        return "http-client"

    monkeypatch.setenv("CHROMA_SERVER_HOST", "chroma")
    monkeypatch.setenv("CHROMA_SERVER_PORT", "8000")
    monkeypatch.setattr(embeddings.chromadb, "HttpClient", fake_http)
    client = embeddings.get_chroma_client()
    assert client == "http-client"
    assert captured == {"host": "chroma", "port": 8000}


def test_get_chroma_client_persistent_mode(monkeypatch):
    captured = {}

    def fake_persistent(path):
        captured["path"] = path
        return "persistent-client"

    monkeypatch.delenv("CHROMA_SERVER_HOST", raising=False)
    monkeypatch.setenv("CHROMA_PATH", "/tmp/x")
    monkeypatch.setattr(embeddings.chromadb, "PersistentClient", fake_persistent)
    client = embeddings.get_chroma_client()
    assert client == "persistent-client"
    assert captured == {"path": "/tmp/x"}


def test_is_embedding_conflict():
    conflict = ValueError(
        "An embedding function already exists in the collection configuration, "
        "and a new one is provided. Embedding function conflict: new vs persisted"
    )
    assert embeddings._is_embedding_conflict(conflict)
    assert not embeddings._is_embedding_conflict(ValueError("something else"))


def test_get_or_reset_collection_rebuilds_on_fingerprint_change(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "mxbai-embed-large")
    client = chromadb.PersistentClient(path=tempfile.mkdtemp())

    # Pre-create a collection tagged with a stale fingerprint.
    client.create_collection(
        name="stylus_chat_data",
        embedding_function=embeddings.get_embedding_function(),
        metadata={"hnsw:space": "cosine", embeddings.FINGERPRINT_KEY: "old-model|cosine"},
    )

    col = embeddings.get_or_reset_collection(client, "stylus_chat_data")
    assert col.metadata[embeddings.FINGERPRINT_KEY] == "mxbai-embed-large|cosine"
    assert col.count() == 0


def test_get_or_reset_collection_resets_on_conflict(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "mxbai-embed-large")

    deleted = {"called": False}
    made = {"count": 0}

    fake_collection = types.SimpleNamespace(metadata={embeddings.FINGERPRINT_KEY: "mxbai-embed-large|cosine"})

    class FakeClient:
        def get_collection(self, name):
            return fake_collection

        def delete_collection(self, name):
            deleted["called"] = True

        def get_or_create_collection(self, name, embedding_function, metadata):
            made["count"] += 1
            if made["count"] == 1:
                raise ValueError("Embedding function conflict: new vs persisted")
            return "rebuilt"

    result = embeddings.get_or_reset_collection(
        FakeClient(), "stylus_feedback", reset_on_conflict=True
    )
    assert result == "rebuilt"
    assert deleted["called"] is True
    assert made["count"] == 2


def test_get_or_reset_collection_reraises_without_reset_flag():
    class FakeClient:
        def get_collection(self, name):
            raise KeyError("missing")

        def get_or_create_collection(self, name, embedding_function, metadata):
            raise ValueError("Embedding function conflict: new vs persisted")

    with pytest.raises(ValueError):
        embeddings.get_or_reset_collection(FakeClient(), "c", reset_on_conflict=False)
