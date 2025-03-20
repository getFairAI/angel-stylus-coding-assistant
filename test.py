import argparse
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_community.embeddings.ollama import OllamaEmbeddings
from langchain_community.llms.ollama import Ollama
from guidance import models, select, gen
from load import get_db
import litellm

litellm.api_base = "http://localhost:11434"

DECISION_PROMPT= """
Consider 2 categories, 'General Knowledge' or 'Code Generation.
Caregorise the following query:

{query}

Answer only with one of the two catetgories above and nothing else.
"""

def llama_cpp_test(query: str):
    #ollama = models.LlamaCpp(
    #    model="/usr/share/ollama/.ollama/models/blobs/sha256-4824460d29f2058aaf6e1118a63a7a197a09bed509f0e7d4e2efb1ee273b447d", # model=f"ollama/llama3.3",
    #    # api_base="http://localhost:11434"
    #    echo=True,
    #    n_gpu_layers=2,
    #    n_threads=8,
    #    n_ctx_=8192,
    #    enable_monitoring=True,
    #    enable_backtrack=True,
    #    enable_ff_tokens=True   
    #)
    
    #lm = ollama + f"write something"+ gen("output", stop="\n")
    #print(lm)
    return

def ollama_test(query: str):
    ollama = Ollama(model="llama3.3")
    prompt = DECISION_PROMPT.format(query=query)
    print(prompt)
    result = ollama.invoke(prompt)
    print(result)
    # prompt_template = ChatPromptTemplate.from_template(DECISION_PROMPT)
    
def decision(query: str):
    # model = 'meta-llama/Meta-Llama-3-8B-Instruct'
    # device = 'cuda'
    # llm_gpt2_large_gpu = models.Transformers(model) 
    #ollama = models.LlamaCpp(
    #    model="/usr/share/ollama/.ollama/models/blobs/sha256-6a0746a1ec1aef3e7ec53868f220ff6e389f6f8ef87a01d77c96807de94ca2aa", # model=f"ollama/llama3",
    #    # api_base="http://localhost:11434"
    #    echo=True,
    #    n_gpu_layers=-1,
    #    n_threads=8,
    #    n_ctx_=8192,
    #    enable_monitoring=True,
    #    enable_backtrack=True,
    #    enable_ff_tokens=True   
    #)
    
    # lm = ollama + f"write something"+ gen("output", stop="\n")
    ollama = models._lite_llm.LiteLLMInstruct(model="ollama/llama3.3", api_base="http://localhost:11434")

    prompt = DECISION_PROMPT.format(query=query)
    print(prompt)
    lm = ollama + f"{prompt} {select(['General Knowledge', 'Task Resolution'], name='decision')}"
    print(lm["decision"])
    return lm["decision"]
  
def get_embedding_function():
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    return embeddings

def similarity():
    db = get_db("docs")
    #documents = db._collection.count()
    #print(documents)
    results = db.similarity_search_with_score(" What is stylus?", k=5)
    result = [(doc.page_content, doc.metadata.get("id", None)) for doc, _score in results]
    for (doc, source) in result:
        print(doc)
        print(source)

def main():
    decision("Show me an example on how to create an agent with RIG")
    decision("How do you declare a variable in stylus?")


if __name__ == "__main__":
    ollama_test("What is arbitrum")
    print("--------------")
    ollama_test("Help me write a stylus contract for a voting platform")
    print("--------------")
    ollama_test("what can i do with stylus?")
    print("--------------")
    ollama_test("write me a stylus contract that implements the ERC20 standard")