import json
from langchain_text_splitters import RecursiveJsonSplitter
from load import add_to_db, get_db

def main():
    with open('./rig-data-set.json', 'r') as json_file:
        json_list = json.load(json_file)
    # process data
    new_dataset = []
    for data in json_list:
        instruction = data["instruction"]
        description = data["metadata"]["description"]

        new_instruction = f"{description}, your task consists of {instruction}"
        new_dataset.append({
            "Instruction": new_instruction,
            "Response": data["code"]
        })
    jsonSplitter = RecursiveJsonSplitter()
    documents = jsonSplitter.create_documents(new_dataset)
    db = get_db("code")
    add_to_db(documents, db)
    results = db.similarity_search_with_score("How do i implement a sample agent with RIG", k=5)
    sources = [doc.metadata.get("id", None) for doc, _score in results]
    print(sources)
    
    

if __name__ == "__main__":
    main()