import json
import os
from typing import Dict, List
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
import ollama
from concurrent.futures import ThreadPoolExecutor
import re
import numpy as np
import uuid


DATA_DIR = "data"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "stylus_chat_data"
BATCH_SIZE = 64
MAX_CHARS = 800
OVERLAP = 100
SEPARATORS = ["\n\n", "\n", ". ", "; ", " ", ""]


class OllamaEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:

        def embed(text):
            return ollama.embeddings(
                model="mxbai-embed-large",
                prompt=text
            )["embedding"]

        with ThreadPoolExecutor(max_workers=8) as executor:
            embeddings = list(executor.map(embed, input))

        return embeddings

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


# ----------------------------------------------------
# MAIN FUNCTION (callable)
# ----------------------------------------------------
def fill_chroma():
    # Init client
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Reset collection (safe to ignore if it doesn't exist)
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
        print(f"[info] Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        print(f"[info] No existing collection '{COLLECTION_NAME}' to delete")

    # Recreate collection
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=OllamaEmbeddingFunction()
    )

    json_files_path = discover_json_files(DATA_DIR)
    print(f"[info] Found {len(json_files_path)} JSON files in {DATA_DIR}")

    # json_files_path = [ "data/github_issues_sectioned.json"]
    documents_batch = []
    metadatas_batch = []
    ids_batch = []

    doc_counter = 0

    for file_path in json_files_path:
        print(f"[info] Indexing {file_path}")
        data = load_json_data(file_path)

        for item in data:
            text = item.get("text", "")
            base_metadata = item.get("metadata", {})

            # 1) Recursively split into small units
            units = recursive_chunk(text, MAX_CHARS)

            # Step 2: semantic grouping
            #semantic_chunks = semantic_group_chunks(
            #      units,
            #    embed_fn=lambda texts: OllamaEmbeddingFunction()(texts),
            #    similarity_threshold=0.85
            #)

            #print(f"[info] Formed {len(semantic_chunks)} semantic chunks")

            # chunks = chunk_text(text, max_chars=2000)

            for idx, unit in enumerate(units):
                chunk_text = unit["text"]
                unit_meta = unit["meta"].copy()

                if len(chunk_text) > MAX_CHARS:
                    print("⚠ Oversized chunk:", len(chunk_text))

                # Build final metadata by merging
                chunk_metadata = {**base_metadata, **unit_meta}
                chunk_metadata["chunk_index"] = idx
                chunk_metadata["chunk_total"] = len(units)

                doc_id = f"doc_{doc_counter}"
                doc_counter += 1

                documents_batch.append(chunk_text)
                metadatas_batch.append(chunk_metadata)
                ids_batch.append(doc_id)

                if len(documents_batch) >= BATCH_SIZE:
                    collection.add(
                        documents=documents_batch,
                        metadatas=metadatas_batch,
                        ids=ids_batch
                    )

                    print(f"[batch] Added {len(documents_batch)} docs")

                    documents_batch = []
                    metadatas_batch = []
                    ids_batch = []

    # Flush remaining docs
    if documents_batch:
        collection.add(
            documents=documents_batch,
            metadatas=metadatas_batch,
            ids=ids_batch
        )
        print(f"[batch] Added final {len(documents_batch)} docs")

    print(
        f"[✔] Successfully added {doc_counter} documents to the '{COLLECTION_NAME}' collection")
    return doc_counter


# ----------------------------------------------------
# Standalone execution
# ----------------------------------------------------
if __name__ == "__main__":
    fill_chroma()
