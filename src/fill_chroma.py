import hashlib
import json
import logging
import os
from typing import Dict, List
import numpy as np
import uuid

from embeddings import get_chroma_client, get_or_reset_collection


logger = logging.getLogger(__name__)

DATA_DIR = os.getenv("DATA_DIR", "data")
COLLECTION_NAME = "stylus_chat_data"
BATCH_SIZE = 64
MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "800"))
OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
SEPARATORS = ["\n\n", "\n", ". ", "; ", " ", ""]

# ----------------------------------------------------
# Helpers
# ----------------------------------------------------


def load_json_data(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def discover_json_files(data_dir: str):
    """Return all .json files inside data_dir (non-recursive)."""
    files = []
    for filename in os.listdir(data_dir):
        if filename.endswith(".json"):
            files.append(os.path.join(data_dir, filename))
    return sorted(files)


def recursive_chunk(
    text: str,
    max_chars: int,
    parent_id=None,
    chunk_index=0
) -> List[Dict]:
    """
    Recursively split text into a list of dicts:
      { "text": ..., "meta": { ... } }

    Uses a hierarchy of natural separators.
    Marks each chunk with neutral meta (parent id, etc.).
    """
    text = text.strip()
    if not text:
        return []

    if parent_id is None:
        parent_id = str(uuid.uuid4())

    # If text already fits, just return one chunk
    if len(text) <= max_chars:
        return [{
            "text": text,
            "meta": {"parent_id": parent_id, "chunk_index": chunk_index}
        }]

    for sep in SEPARATORS:
        if sep == "":
            parts = [text[i: i + max_chars]
                     for i in range(0, len(text), max_chars)]
        else:
            parts = text.split(sep)

        if len(parts) > 1:
            aggregated, buffer = [], ""
            for part in parts:
                candidate = (buffer + sep + part).strip() if buffer else part
                if len(candidate) <= max_chars:
                    buffer = candidate
                else:
                    if buffer:
                        aggregated.extend(recursive_chunk(
                            buffer, max_chars, parent_id, chunk_index))
                        chunk_index += 1
                        buffer = ""
                    if len(part) > max_chars:
                        aggregated.extend(recursive_chunk(
                            part, max_chars, parent_id, chunk_index))
                        chunk_index += 1
                    else:
                        buffer = part

            if buffer:
                aggregated.extend(recursive_chunk(
                    buffer, max_chars, parent_id, chunk_index))

            return aggregated

    return [{
        "text": text[i: i + max_chars],
        "meta": {"parent_id": parent_id, "chunk_index": chunk_index}
    } for i in range(0, len(text), max_chars)]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def semantic_group_chunks(
    units: List[Dict],
    embed_fn,
    similarity_threshold: float = 0.80,
    max_chars: int = MAX_CHARS
) -> List[Dict]:

    if not units:
        return []

    texts = [u["text"] for u in units]
    embeddings = embed_fn(texts)

    final_chunks = []
    current_group = [units[0]]
    current_vec = embeddings[0]
    current_length = len(units[0]["text"])

    for i in range(1, len(units)):
        sim = cosine_similarity(current_vec, embeddings[i])
        next_length = current_length + 1 + len(units[i]["text"])

        if sim >= similarity_threshold and next_length <= max_chars:
            current_group.append(units[i])
            current_vec = embeddings[i]
            current_length = next_length
        else:
            combined_text = " ".join(u["text"] for u in current_group)
            combined_meta = {
                "parent_ids": ", ".join(str(u["meta"]["parent_id"]) for u in current_group),
                "source_indexes": ", ".join(str(u["meta"]["chunk_index"]) for u in current_group)
            }
            final_chunks.append({"text": combined_text, "meta": combined_meta})

            current_group = [units[i]]
            current_vec = embeddings[i]
            current_length = len(units[i]["text"])

    combined_text = " ".join(u["text"] for u in current_group)
    combined_meta = {
        "parent_ids": ", ".join(str(u["meta"]["parent_id"]) for u in current_group),
        "source_indexes": ", ".join(str(u["meta"]["chunk_index"]) for u in current_group)
    }
    final_chunks.append({"text": combined_text, "meta": combined_meta})

    return final_chunks


def apply_overlap(units: List[Dict], overlap: int) -> List[Dict]:
    """Prepend the tail of the previous unit to each unit for recall across
    chunk boundaries. Overlap is taken from the *original* previous text so it
    does not compound as chunks are stitched."""
    if overlap <= 0 or len(units) <= 1:
        return units

    overlapped = []
    prev_text = ""
    for unit in units:
        text = unit["text"]
        if prev_text:
            tail = prev_text[-overlap:]
            text = f"{tail} {text}".strip()
        overlapped.append({"text": text, "meta": unit["meta"]})
        prev_text = unit["text"]
    return overlapped


def _source_key(metadata: Dict) -> str:
    """Stable identity for the source item (independent of run-time uuids), used
    so chunk ids stay constant across rebuilds and unchanged content is not
    re-embedded."""
    for key in ("url", "repo_url", "source_url", "id"):
        value = metadata.get(key)
        if value:
            return str(value)
    parts = [
        str(metadata.get(k, ""))
        for k in ("source", "repo", "title", "section", "subsection")
    ]
    return "|".join(p for p in parts if p)


def stable_chunk_id(source_key: str, index: int, text: str) -> str:
    """Content-derived, deterministic id. Same (source, position, text) => same
    id, enabling idempotent upsert and stale-id garbage collection."""
    digest = hashlib.sha256(
        f"{source_key}|{index}|{text}".encode("utf-8")
    ).hexdigest()
    return f"doc_{digest[:32]}"


def _build_chunk_records(json_files_path: List[str]) -> Dict[str, Dict]:
    """Return {chunk_id: {"document","metadata"}} for the entire corpus."""
    records: Dict[str, Dict] = {}
    for file_path in json_files_path:
        print(f"[info] Indexing {file_path}")
        data = load_json_data(file_path)

        for item in data:
            text = item.get("text", "")
            base_metadata = item.get("metadata", {})
            source_key = _source_key(base_metadata)

            units = recursive_chunk(text, MAX_CHARS)
            units = apply_overlap(units, OVERLAP)

            for idx, unit in enumerate(units):
                chunk_text = unit["text"]
                unit_meta = unit["meta"].copy()

                if len(chunk_text) > MAX_CHARS + OVERLAP:
                    print("⚠ Oversized chunk:", len(chunk_text))

                chunk_metadata = {**base_metadata, **unit_meta}
                chunk_metadata["chunk_index"] = idx
                chunk_metadata["chunk_total"] = len(units)

                doc_id = stable_chunk_id(source_key, idx, chunk_text)
                # Last write wins on a genuine id collision (identical content).
                records[doc_id] = {
                    "document": chunk_text,
                    "metadata": chunk_metadata,
                }
    return records


# ----------------------------------------------------
# MAIN FUNCTION (callable)
# ----------------------------------------------------
def fill_chroma():
    client = get_chroma_client()
    collection = get_or_reset_collection(
        client, COLLECTION_NAME, reset_on_conflict=True
    )

    json_files_path = discover_json_files(DATA_DIR)
    print(f"[info] Found {len(json_files_path)} JSON files in {DATA_DIR}")

    records = _build_chunk_records(json_files_path)
    new_ids = set(records.keys())

    try:
        existing_ids = set(collection.get()["ids"])
    except Exception as e:
        logger.warning("Could not read existing ids from '%s': %s", COLLECTION_NAME, e)
        existing_ids = set()

    # Only embed/write chunks that are new or changed; leave unchanged chunks in
    # place. The collection is never emptied, so live readers keep serving
    # results throughout the rebuild.
    to_upsert = [doc_id for doc_id in new_ids if doc_id not in existing_ids]
    to_delete = [doc_id for doc_id in existing_ids if doc_id not in new_ids]

    for start in range(0, len(to_upsert), BATCH_SIZE):
        batch = to_upsert[start:start + BATCH_SIZE]
        collection.upsert(
            documents=[records[i]["document"] for i in batch],
            metadatas=[records[i]["metadata"] for i in batch],
            ids=batch,
        )
        print(f"[batch] Upserted {len(batch)} docs")

    for start in range(0, len(to_delete), BATCH_SIZE):
        batch = to_delete[start:start + BATCH_SIZE]
        collection.delete(ids=batch)
    if to_delete:
        print(f"[info] Removed {len(to_delete)} stale docs")

    print(
        f"[✔] Corpus '{COLLECTION_NAME}': {len(new_ids)} chunks "
        f"({len(to_upsert)} new/changed, {len(to_delete)} removed, "
        f"{len(new_ids) - len(to_upsert)} unchanged)"
    )
    return len(to_upsert)


# ----------------------------------------------------
# Standalone execution
# ----------------------------------------------------
if __name__ == "__main__":
    fill_chroma()
