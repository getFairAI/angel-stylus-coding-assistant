import argparse
import os
import shutil

from langchain_community.embeddings.ollama import OllamaEmbeddings
from langchain_community.document_loaders import UnstructuredMarkdownLoader, JSONLoader
from langchain_text_splitters import MarkdownTextSplitter, RecursiveCharacterTextSplitter
from langchain.schema.document import Document
from langchain_community.vectorstores import Chroma

import nltk
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')

def load_q_and_a():
    # Define the metadata extraction function.
    def metadata_func(record: dict, metadata: dict) -> dict:
        metadata["question"] = record.get("question")
        return metadata


    loader = JSONLoader(
        file_path='./q&a_v4.jsonl',
        jq_schema='.answer',
        metadata_func=metadata_func
    )

    data = loader.load()
    return data

def metadata_func(record: dict, metadata: dict) -> dict:

    metadata["instruction"] = record.get("instruction")
    metadata["category"] = record.get("category")
    metadata["metadata"] = record.get("metadata")

    return metadata
    

def get_embedding_function():
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    return embeddings

def load_documents_md(new_file: str = None):
    if new_file is not None:
        loader = UnstructuredMarkdownLoader(file_path=new_file)
    else:
        loader = UnstructuredMarkdownLoader(file_path="./data/artificial-data-set.md")
    documents = loader.load()
    
    return documents

def load_documents_json(new_file: str = None):
    if new_file is not None:
        loader = JSONLoader(file_path=new_file, jq_schema=".[]", content_key="code", metadata_func=metadata_func)
    else:
        loader = JSONLoader(file_path="./data/arbitrum-stylus-data.json", jq_schema=".[]", content_key="code", metadata_func=metadata_func)
    documents = loader.load()
    return documents

def split_documents_md(documents: list[Document]):
    text_splitter = MarkdownTextSplitter(chunk_size=4000, chunk_overlap=200)
    return text_splitter.split_documents(documents)
  
def split_documents_json(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
    return text_splitter.split_documents(documents)

def add_to_db(chunks: list[Document], db: Chroma):
    chunks_with_ids = calculate_chunk_ids(chunks) # Giving each chunk an ID

    # Add or Update the documents.
    existing_items = db.get(include=[])  # IDs are always included by default
    existing_ids = set(existing_items["ids"])
    print(f"Number of existing documents in DB '{db._collection.name}: {len(existing_ids)}")

    # Only add documents that don't exist in the DB.
    new_chunks = []
    for chunk in chunks_with_ids:
        if chunk.metadata["id"] not in existing_ids:
            new_chunks.append(chunk)

    if len(new_chunks):
        print(f"'{db._collection.name}' 👉 Adding new documents: {len(new_chunks)}")
        new_chunk_ids = [chunk.metadata["id"] for chunk in new_chunks]
        db.add_documents(new_chunks, ids=new_chunk_ids)
        db.persist()
    else:
        print(" all documents are added")

def calculate_chunk_ids(chunks):
    # This will create IDs like "data/monopoly.pdf:6:2"
    # Page Source : Page Number : Chunk Index

    last_page_id = None
    current_chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source")
        page = chunk.metadata.get("page")
        current_page_id = f"{source}:{page}"

        # If the page ID is the same as the last one, increment the index.
        if current_page_id == last_page_id:
            current_chunk_index += 1
        else:
            current_chunk_index = 0

        # Calculate the chunk ID.
        chunk_id = f"{current_page_id}:{current_chunk_index}"
        last_page_id = current_page_id

        # Add it to the page meta-data.
        chunk.metadata["id"] = chunk_id

    return chunks

def clear_database(db: Chroma):
    print("✨ Clearing Database '"+db._collection.name+"'")
    db.delete_collection()
    if db._collection.name == 'docs' and os.path.exists("./.vector_data_docs"):
        shutil.rmtree("./.vector_data_docs")
    if db._collection.name == 'code' and os.path.exists("./.vector_data_code"):
        shutil.rmtree("./.vector_data_code")

def init_docs(args = None):
    # Check if the database should be cleared (using the --clear flag).
    # Load the existing database.
    
    db = Chroma(
        collection_name="docs",
        persist_directory='./.vector_data_docs',
        embedding_function=get_embedding_function()
    )
    if args is not None and args.reset:
        clear_database(db)
        return

    # Create (or update) the data store.
    # default files to add
    
    #documents = load_documents_md("./documentation.md")
    #chunks = split_documents_md(documents)
    with open("./data/documentation.md", "r") as file:
        content = file.read()
        file.close()
    markdowns = content.split('\n\n---\n\n')
    text_splitter = MarkdownTextSplitter(chunk_size=2000, chunk_overlap=200)
    chunks = text_splitter.create_documents(markdowns)
    add_to_db(chunks, db)
    
def init_code(args = None):
    # Check if the database should be cleared (using the --clear flag).
    # Load the existing database.
    
    db = Chroma(
        collection_name="code",
        persist_directory='./.vector_data_code', embedding_function=get_embedding_function()
    )
    if args is not None and args.reset:
        clear_database(db)
        return

    # Create (or update) the data store.
    # default files to add
    
    md_documents = load_documents_md("./data/artificial-data-set.md")
    # json_documents = load_documents_md("./artifical-data-set.md")
    chunks = split_documents_md(md_documents)
    add_to_db(chunks, db)

def update_db_code(file: str, isJson=False):
    if isJson:
        documents = load_documents_json(file)
        chunks = split_documents_json(documents)
    else:
        documents = load_documents_md(file)
        chunks = split_documents_md(documents)
    db = Chroma(
        collection_name="code",
        persist_directory='./.vector_data_code', embedding_function=get_embedding_function()
    )
    add_to_db(chunks, db)

def get_db(name: str):
    if name == 'code':
        db = Chroma(
            collection_name="code",
            persist_directory='./.vector_data_code', embedding_function=get_embedding_function()
        )
        return db
    elif name == 'docs':
        db = Chroma(
            collection_name="docs",
            persist_directory='./.vector_data_docs', embedding_function=get_embedding_function()
        )
        return db
    else:
      return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="Which database, 'docs' or 'code'", required=True)
    parser.add_argument("--load", help="File path to load from.")
    parser.add_argument("--reset", action="store_true", help="Reset the database")
    parser.add_argument("--show", action="store_true", help="Show documents.")
    
    args = parser.parse_args()
    if args.load is not None and args.db == 'code':
        update_db_code(args.load, True)
    elif args.load is not None and args.db == 'docs':
        update_db_code(args.load, False)
    elif args.load is not None:
        print("File Extension not supported. Only '.md' or '.json' files")
    elif args.db == "code":
        init_code(args)
    elif args.db == "docs":
        init_docs(args)
    else:
        print("Invalid arguments.")