import chromadb
import ollama


chroma_client = chromadb.PersistentClient(path="./chroma_db")

collection = chroma_client.get_collection("stylus_chat_data")

query_embedding = ollama.embeddings(model="nomic-embed-text", prompt="I would like to learn about a gente introduction if its in the documentation")["embedding"]

results = collection.query(
    query_embeddings=[query_embedding], 
    #query_texts=["what information is available for traveling with a dog to France namely about Documents?"],
    #where={"category":"Rust SDK"},
    n_results=3,
    #include=["documents"]
)


print(str(results["documents"][0]))


