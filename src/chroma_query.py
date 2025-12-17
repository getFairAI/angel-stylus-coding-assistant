import chromadb
import ollama


CHROMA_RESULTS = 10
chroma_client = chromadb.PersistentClient(path="./chroma_db")

collection = chroma_client.get_or_create_collection(name="stylus_chat_data")

def get_prompt_embedding(user_prompt):
    return ollama.embeddings(model="nomic-embed-text", prompt=user_prompt)["embedding"]


def get_chroma_documents(prompt):
    query_embedding = get_prompt_embedding(prompt)
    
    results = collection.query(
    query_embeddings=[query_embedding], 
    n_results=CHROMA_RESULTS,
    )
    num_chunks = len(results["documents"][0])
    return results["documents"][0]
    
    
    