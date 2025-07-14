import json
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
import ollama  

json_files_path = ["data/introduction.json","data/quickstart.json", "data/stylus_docs.json"]
    
def load_json_data(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)    
    
class OllamaEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        return [ollama.embeddings(model="nomic-embed-text", prompt=text)["embedding"] for text in input]
    
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="stylus_data", embedding_function=OllamaEmbeddingFunction())
#collection = chroma_client.get_or_create_collection(name="pawpass")
        
doc_counter = 0

for file_path in json_files_path:
    data = load_json_data(file_path)
    for i, item in enumerate(data):
        text = item["text"]
        metadata = item["metadata"]

        #embedding = ollama.embeddings(model="nomic-embed-text", prompt=text)["embedding"]

        doc_id = f"doc_{doc_counter}"
        doc_counter += 1

        collection.add(
            documents=[text],
            #embeddings=[embedding], 
            metadatas=[metadata],
            ids=[doc_id]
        )



print(f"[✔] Successfully added {doc_counter} documents to the 'stylus_data' collection.")