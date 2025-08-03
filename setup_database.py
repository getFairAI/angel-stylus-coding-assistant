#!/usr/bin/env python3
"""
Setup script to initialize the ChromaDB with Stylus documentation data.
"""

import json
import os
import sys
from pathlib import Path

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

def setup_database():
    """Initialize the ChromaDB with available data."""
    print("🗄️  Setting up ChromaDB with Stylus documentation...")
    
    # Create chroma_db directory if it doesn't exist
    Path("chroma_db").mkdir(exist_ok=True)
    
    # Check if we have the necessary import modules
    try:
        import chromadb
        import ollama
        print("✅ Required modules found")
    except ImportError as e:
        print(f"❌ Missing required module: {e}")
        print("Please install dependencies first: pip install -r requirements_mcp.txt")
        return False
    
    try:
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(path="./chroma_db")
        
        # Create or get collection with custom embedding function
        embedding_function = OllamaEmbeddingFunction()
        collection = client.get_or_create_collection(
            name="stylus_data",
            embedding_function=embedding_function
        )
        
        # Check if collection already has data
        count = collection.count()
        if count > 0:
            print(f"✅ Database already initialized with {count} documents")
            return True
        
        # Load data from JSON files
        data_files = [
            "data/stylus_docs.json",
            "data/arbitrum-stylus-data.json",
            "data/stylus-dataset.json"
        ]
        
        documents = []
        metadatas = []
        ids = []
        
        doc_id = 0
        
        for file_path in data_files:
            if os.path.exists(file_path):
                print(f"📖 Loading data from {file_path}...")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Handle different JSON structures
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict) and 'documents' in data:
                        items = data['documents']
                    else:
                        items = [data]
                    
                    for item in items:
                        if isinstance(item, dict):
                            # Extract text content
                            text_content = ""
                            if 'content' in item:
                                text_content = str(item['content'])
                            elif 'text' in item:
                                text_content = str(item['text'])
                            elif 'page_content' in item:
                                text_content = str(item['page_content'])
                            else:
                                text_content = str(item)
                            
                            if text_content and len(text_content.strip()) > 10:
                                documents.append(text_content)
                                
                                # Create metadata (ensure all values are strings)
                                metadata = {
                                    "source": file_path,
                                    "doc_type": "stylus_documentation"
                                }
                                
                                # Add any additional metadata from the item (convert to strings)
                                if 'metadata' in item and isinstance(item['metadata'], dict):
                                    for key, value in item['metadata'].items():
                                        if isinstance(value, (str, int, float, bool)):
                                            metadata[key] = str(value)
                                        elif isinstance(value, list):
                                            metadata[key] = ", ".join(str(v) for v in value)
                                        else:
                                            metadata[key] = str(value)
                                
                                metadatas.append(metadata)
                                ids.append(f"doc_{doc_id}")
                                doc_id += 1
                
                except Exception as e:
                    print(f"⚠️  Error loading {file_path}: {e}")
                    continue
            else:
                print(f"⚠️  File not found: {file_path}")
        
        if documents:
            print(f"📚 Adding {len(documents)} documents to ChromaDB...")
            
            # Add documents in batches to avoid memory issues
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch_end = min(i + batch_size, len(documents))
                batch_docs = documents[i:batch_end]
                batch_metadata = metadatas[i:batch_end]
                batch_ids = ids[i:batch_end]
                
                collection.add(
                    documents=batch_docs,
                    metadatas=batch_metadata,
                    ids=batch_ids
                )
                print(f"  Added batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")
            
            print(f"✅ Successfully added {len(documents)} documents to ChromaDB")
            return True
        else:
            print("❌ No valid documents found in data files")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

def main():
    """Main function."""
    print("🤖 Angel Stylus Coding Assistant - Database Setup")
    print("=" * 50)
    
    success = setup_database()
    
    if success:
        print("\n✅ Database setup completed successfully!")
        print("You can now run the assistant with: python run_mcp_assistant.py")
    else:
        print("\n❌ Database setup failed!")
        print("Please check the error messages above and try again.")

if __name__ == "__main__":
    main() 