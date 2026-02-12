import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


CHROMA_RESULTS = 25
chroma_client = chromadb.PersistentClient(path="./chroma_db")
embedding_fn = DefaultEmbeddingFunction()
collection = chroma_client.get_or_create_collection(
    name="stylus_chat_data",
    embedding_function=embedding_fn,
)


def get_chroma_documents(prompt):
    results = collection.query(
        query_texts=[prompt],
        n_results=CHROMA_RESULTS,
        include=["documents", "metadatas", "distances"],
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    hits = []
    for idx, doc in enumerate(documents):
        hits.append(
            {
                "text": doc,
                "metadata": (metadatas[idx] if idx < len(metadatas) else {}) or {},
                "distance": distances[idx] if idx < len(distances) else None,
            }
        )
    return hits
    
