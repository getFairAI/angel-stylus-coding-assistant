import json
import os
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
import ollama


DATA_DIR = "data"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "stylus_chat_data"


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


class OllamaEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        return [
            ollama.embeddings(model="nomic-embed-text", prompt=text)["embedding"]
            for text in input
        ]


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

    doc_counter = 0

    for file_path in json_files_path:
        print(f"[info] Indexing {file_path}")
        data = load_json_data(file_path)

        for item in data:
            text = item["text"]
            metadata = item["metadata"]

            doc_id = f"doc_{doc_counter}"
            doc_counter += 1

            collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[doc_id]
            )

    print(f"[✔] Successfully added {doc_counter} documents to the '{COLLECTION_NAME}' collection")
    return doc_counter


# ----------------------------------------------------
# Standalone execution
# ----------------------------------------------------
if __name__ == "__main__":
    fill_chroma()
