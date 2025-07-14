import chromadb
import ollama


chroma_client = chromadb.PersistentClient(path="./chroma_db")

collection = chroma_client.get_collection("stylus")

query_embedding = ollama.embeddings(model="nomic-embed-text", prompt="what information is available about Rust SDK?")["embedding"]

results = collection.query(
    query_embeddings=[query_embedding], 
    #query_texts=["what information is available for traveling with a dog to France namely about Documents?"],
    where={"category":"Rust SDK"},
    n_results=10,
    #include=["documents"]
)

#for result in results["documents"]:
#    print(result)

print(str(results["documents"][0]))

#sample_doc = collection.get(ids=["doc_0"], include=["embeddings", "documents", "metadatas"])
#print(sample_doc)

