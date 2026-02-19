import chromadb
import ollama


chroma_client = chromadb.PersistentClient(path="./chroma_db")

collection = chroma_client.get_collection("stylus_chat_data")

query_embedding = ollama.embeddings(model="mxbai-embed-large", prompt="is there an issue #391 in stylus-rust-sdk")["embedding"]

results = collection.query(
    query_embeddings=[query_embedding], 
    #query_texts=["what information is available for traveling with a dog to France namely about Documents?"],
    #where={"category":"Rust SDK"},
    n_results=10,
    include=["documents"]
    #include=["documents"]
)


print(str(results["documents"]))


