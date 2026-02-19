from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import time

from retrieve_chroma_docs import retrieve_stylus_context
from basic_logs import write_request_log
from rag_evaluation import eval_context_relevance, eval_response_groundness, eval_response_relevancy
# from langchain_openai import ChatOpenAI


inference_server_url = "http://localhost:11434" # vllm server

app = FastAPI()


class StylusRequest(BaseModel):
    prompt: str


from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="qwen3:30b",
    base_url=inference_server_url,
    temperature=0,
    # other params...
)

#llm = ChatOpenAI(
#    model="qwen3:30b",
#    openai_api_key="EMPTY",
#    openai_api_base=inference_server_url,
#    # max_tokens=500,
#    temperature=0.8,
#)


@app.post("/stylus-chat")
def stylus_chat(request: StylusRequest):
    write_request_log(f"User started a request | Prompt: {request.prompt}")
    start_time = time.time()

    rag_result = retrieve_stylus_context(request.prompt)

    duration = round(time.time() - start_time, 2)
    preview = (rag_result.get("context")
               or rag_result.get("reason") or "")[:80]
    write_request_log(
        f"✅ Finished retrieval | Time: {duration}s | Preview: {preview}...")

    ctx_relevance = eval_context_relevance(request.prompt, rag_result, llm)


    instructions = f"""You are a helpful assistant who is good at analyzing source information and answering questions.
    #       Use the following source documents to answer the user's questions.
    #       If you don't know the answer, just say that you don't know.
    #       Use three sentences maximum and keep the answer concise.

    #Documents:
    #{rag_result}"""
    
    response = llm.invoke([
            {"role": "system", "content": instructions},
            {"role": "user", "content": request.prompt},
        ],
    )
    
    answer_groundness = eval_response_groundness(response, rag_result, llm)
    answer_relevancy = eval_response_relevancy(request.prompt, response, llm)

    # Return retrieval payload (MCP/IDE/LLM will decide what to do with it)
    return {
        'answer': response,
        'context_relevance': ctx_relevance,
        'answer_groundness': answer_groundness,
        'answer_relevancy': answer_relevancy
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002)
