import argparse
from langchain.prompts import ChatPromptTemplate
from langchain_community.embeddings.ollama import OllamaEmbeddings
from langchain_community.llms.ollama import Ollama
import re
import time
import litellm
from load import get_db
litellm.api_base = "http://localhost:11434"

PROMPT= """
You are a coding assistant especialized in Stylus, a rust smart contract framework for arbitrum. Use the following context to answer the questions:

{context}

---

Based on the above context, develop code for: {question}
"""

DECISION_PROMPT= """
Consider 2 categories, 'General Knowledge' or 'Code Generation'.
Categorise the following query:

{query}

Answer only with one of the two categories above and nothing else.
"""

def main():
    # Create CLI.
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=str, help="Model to use")
    parser.add_argument("query_text", type=str, help="The query text.")
    args = parser.parse_args()
    query_text = args.query_text
    model = args.model
    query_rag(model, query_text)

def get_embedding_function():
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    return embeddings

def remove_think_tags(response):
    return re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)

def choose_db(query: str, model_name):
    prompt = DECISION_PROMPT.format(query=query)
    model = Ollama(model=model_name)
    
    return model.invoke(prompt)

def query_rag(model_name: str, query: str):
    # Prepare the DB.
    start = time.time()
    
    #decision = choose_db(query)
    # find only last question for the decision making
    decision_query = query.rsplit("user").pop()
    print(decision_query)
    decision = choose_db(decision_query, model_name)
    print(decision)
    if decision == 'General Knowledge':
        db = get_db('docs')
    else:
        db = get_db('docs')

    print('finished loading db')
    # Search the DB.
    results = db.similarity_search_with_score(query, k=5)
    print(results)
    end = time.time() - start
    print(f'finished searching, took: {end}')

    
    context = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT)
    prompt = prompt_template.format(context=context, question=query)
    # print(prompt)

    print("loading model")
    start = time.time()
    #model = Ollama(model="mistral")
    model = Ollama(model=model_name)
    end = time.time() - start
    print(f"loaded model, took: {end}")
    #model = Ollama(model="llama3")
    print("prompting start")
    start = time.time()
    response_text = model.invoke(prompt)
    end = time.time() - start
    print(f"got response, took: {end}")
    response = remove_think_tags(response_text)

    sources = [doc.metadata.get("id", None) for doc, _score in results]
    formatted_response = f"Response: {response_text}\nSources: {sources}"
    print(formatted_response)
    return response


if __name__ == "__main__":
    main()