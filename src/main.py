from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import time

from retrieve_chroma_docs import retrieve_stylus_context
from basic_logs import write_request_log

app = FastAPI()


class StylusRequest(BaseModel):
    prompt: str


@app.post("/stylus-chat")
def stylus_chat(request: StylusRequest):
    write_request_log(f"User started a request | Prompt: {request.prompt}")
    start_time = time.time()

    result = retrieve_stylus_context(request.prompt)

    duration = round(time.time() - start_time, 2)
    preview = (result.get("context") or result.get("reason") or "")[:80]
    write_request_log(f"✅ Finished retrieval | Time: {duration}s | Preview: {preview}...")

    # Return retrieval payload (MCP/IDE/LLM will decide what to do with it)
    return result


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
