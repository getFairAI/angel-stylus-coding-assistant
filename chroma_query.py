import chromadb
import ollama
from analyze_prompt import get_filters_wrapper
from logger import log_info

class OllamaEmbeddingFunction:
    """Custom embedding function for ChromaDB using Ollama."""
    
    def __call__(self, input):
        """Generate embeddings for input texts."""
        import ollama
        
        if isinstance(input, str):
            input = [input]
        
        embeddings = []
        for text in input:
            result = ollama.embeddings(model="nomic-embed-text", prompt=text)
            embeddings.append(result["embedding"])
        return embeddings

chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Use the same embedding function as setup_database.py
embedding_function = OllamaEmbeddingFunction()
collection = chroma_client.get_or_create_collection(
    name="stylus_data",
    embedding_function=embedding_function
)

def get_prompt_embedding(user_prompt):
    return ollama.embeddings(model="nomic-embed-text", prompt=user_prompt)["embedding"]


def get_chroma_documents(prompt):
    filters = get_filters_wrapper(prompt)
    
    if not filters:
        return []
    
    filter_list = [{k: v} for k, v in filters.items()]
    if len(filter_list) == 1:
        where_filter = filter_list[0]
    else:
        where_filter = {"$and": filter_list}

    log_info(f"🔎 Applied filters: {filters}")
    
    query_embedding = get_prompt_embedding(prompt)
    
    results = collection.query(
    query_embeddings=[query_embedding], 
    where=where_filter,
    n_results=20,
    )
    num_chunks = len(results["documents"][0])
    log_info(f"🔎 Number of returned chunks: {num_chunks}")
    return results["documents"][0]
    
    
    