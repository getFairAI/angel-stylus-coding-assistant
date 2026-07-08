"""Shared embedding + Chroma configuration for the Stylus retrieval backend.

Historically the ingest path, the query path, and the feedback store each
instantiated their own embedding function (and two of them hardcoded the Chroma
path), which made it easy for the index space and the query space to drift
apart. This module is the single source of truth:

- One embedding function (`get_embedding_function`) used everywhere.
- One `CHROMA_PATH` resolver honoring the `CHROMA_PATH` env var.
- One collection-space fingerprint so a model change can be detected and the
  affected collection rebuilt instead of failing on a dimension mismatch.

Embeddings are served by a local Ollama instance (default `mxbai-embed-large`,
1024-dim, cosine). Configure via env:

- `EMBEDDING_MODEL`  (default ``mxbai-embed-large``)
- `OLLAMA_HOST`      (default ``http://localhost:11434``)
- `CHROMA_PATH`      (default ``./chroma_db``)
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import chromadb
import ollama
from chromadb import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "mxbai-embed-large"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_CHROMA_PATH = "./chroma_db"

# Cosine is what mxbai-embed-large is trained for; it also bounds distances to
# [0, 2] which makes the retrieval relevance threshold (CHROMA_MAX_DISTANCE)
# meaningful and model-agnostic.
CHROMA_SPACE = "cosine"

# Collection-metadata key holding the embedding-space fingerprint, used to
# detect a model/space change and rebuild instead of failing on a dimension
# mismatch at add() time.
FINGERPRINT_KEY = "embedding_space"

_EMBED_WORKERS = 8


def get_embedding_model() -> str:
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def get_ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)


def get_chroma_path() -> str:
    return os.getenv("CHROMA_PATH", DEFAULT_CHROMA_PATH)


def get_chroma_client():
    """Return the shared Chroma client.

    When ``CHROMA_SERVER_HOST`` is set (Docker deployment), connect to a
    standalone Chroma server via HTTP so the API and the ingestion job share one
    process — ingestion's writes become immediately visible to the live API with
    no restart. Otherwise fall back to an embedded ``PersistentClient`` on
    ``CHROMA_PATH`` (local dev / single-process). Embeddings are always computed
    client-side by the ollama embedding function, so both modes still require
    ollama reachable from this process.
    """
    host = os.getenv("CHROMA_SERVER_HOST")
    if host:
        port = int(os.getenv("CHROMA_SERVER_PORT", "8000"))
        return chromadb.HttpClient(host=host, port=port)
    return chromadb.PersistentClient(path=get_chroma_path())


class OllamaEmbeddingFunction(EmbeddingFunction):
    """Chroma embedding function backed by a local Ollama server.

    Embeds a batch concurrently. The Ollama client is created lazily per call so
    the function stays cheap to construct and picks up ``OLLAMA_HOST`` at runtime
    (tests and deployments may set it after import).
    """

    def __init__(self, model: Optional[str] = None, host: Optional[str] = None):
        self._model = model
        self._host = host

    @property
    def model(self) -> str:
        return self._model or get_embedding_model()

    @property
    def host(self) -> str:
        return self._host or get_ollama_host()

    def __call__(self, input: Documents) -> Embeddings:
        client = ollama.Client(host=self.host)
        model = self.model

        def embed(text: str):
            return client.embeddings(model=model, prompt=text)["embedding"]

        with ThreadPoolExecutor(max_workers=_EMBED_WORKERS) as executor:
            return list(executor.map(embed, list(input)))

    # Registry name for Chroma's config protocol. Chroma calls this on the class
    # (unbound), so it must be a staticmethod. The concrete model/host live in
    # get_config(); model changes are handled by the fingerprint rebuild, not by
    # this name.
    @staticmethod
    def name() -> str:  # pragma: no cover - trivial
        return "ollama"

    # Chroma 1.5.x embedding-function config protocol (avoids a deprecation
    # warning and lets the function be persisted/rehydrated with the collection).
    def get_config(self) -> dict:
        return {"model": self.model, "host": self.host}

    @staticmethod
    def build_from_config(config: dict) -> "OllamaEmbeddingFunction":
        return OllamaEmbeddingFunction(
            model=config.get("model"), host=config.get("host")
        )


def get_embedding_function() -> OllamaEmbeddingFunction:
    """Return the shared embedding function used for index AND query."""
    return OllamaEmbeddingFunction()


def _is_embedding_conflict(exc: Exception) -> bool:
    text = str(exc).lower()
    return "embedding function" in text and "conflict" in text


def get_or_reset_collection(client, name: str, *, reset_on_conflict: bool = False):
    """Return a Chroma collection bound to the shared embedding function.

    Rebuilds the collection when the embedding-space fingerprint changed (a new
    model/space has a different vector dimension and cannot be added into an
    existing collection). When ``reset_on_conflict`` is set, also rebuilds when
    the persisted embedding function conflicts with the current one — this is the
    one-time migration path off the legacy default embeddings. Callers that must
    not lose data (e.g. read-only query path) leave ``reset_on_conflict`` False
    and let a full re-ingestion perform the rebuild.
    """
    fingerprint = embedding_space_fingerprint()
    embedding_function = get_embedding_function()
    metadata = {"hnsw:space": CHROMA_SPACE, FINGERPRINT_KEY: fingerprint}

    try:
        existing = client.get_collection(name=name)
        stored = (existing.metadata or {}).get(FINGERPRINT_KEY)
        if stored != fingerprint:
            logger.warning(
                "Embedding space changed (%r -> %r); rebuilding '%s'",
                stored, fingerprint, name,
            )
            client.delete_collection(name=name)
    except Exception:
        # Collection does not exist yet — created below.
        pass

    try:
        return client.get_or_create_collection(
            name=name,
            embedding_function=embedding_function,
            metadata=metadata,
        )
    except Exception as exc:  # noqa: BLE001
        if reset_on_conflict and _is_embedding_conflict(exc):
            logger.warning(
                "Embedding function conflict on '%s'; rebuilding collection", name
            )
            client.delete_collection(name=name)
            return client.get_or_create_collection(
                name=name,
                embedding_function=embedding_function,
                metadata=metadata,
            )
        raise


def embedding_space_fingerprint() -> str:
    """Identifier for the current embedding space.

    Stored on the collection metadata so ingestion can detect a model/space
    change and rebuild the collection instead of erroring on a dimension
    mismatch at ``add`` time.
    """
    return f"{get_embedding_model()}|{CHROMA_SPACE}"


def check_ollama_ready() -> tuple[bool, str]:
    """Best-effort readiness probe: server reachable and model pulled.

    Returns ``(ok, message)``. Never raises — callers log the message.
    """
    model = get_embedding_model()
    host = get_ollama_host()
    try:
        client = ollama.Client(host=host)
        tags = client.list()
    except Exception as exc:  # noqa: BLE001 - surface any connection failure
        return (
            False,
            f"Ollama not reachable at {host} ({type(exc).__name__}: {exc}). "
            f"Start it with `ollama serve`.",
        )

    available = set()
    for entry in tags.get("models", []) or []:
        name = entry.get("model") or entry.get("name") or ""
        available.add(name)
        available.add(name.split(":", 1)[0])

    if model not in available and model.split(":", 1)[0] not in available:
        return (
            False,
            f"Embedding model '{model}' not found on Ollama host {host}. "
            f"Pull it with `ollama pull {model}`.",
        )
    return True, f"Ollama ready at {host} with model '{model}'."
