from fastapi import FastAPI
from pydantic import BaseModel
from aux_functions import remove_think_tags
from llm_main_wrapper import stylus_request_with_llm
import uvicorn
from typing import Optional
from logger import log_info, log_separator
import time

app = FastAPI()

class StylusRequest(BaseModel):
    model: str
    prompt: str


@app.post("/stylus-chat")
def stylus_chat(request: StylusRequest):
    log_info(f"User started a request | Model: {request.model} | Prompt: {request.prompt}")
    start_time = time.time()
    result = stylus_request_with_llm(request.model, request.prompt)
    clean_result = remove_think_tags(result)
    duration = round(time.time() - start_time, 2)
    log_info(f"✅ Finished inference | Time: {duration}s | Output: {clean_result[:50]}...")
    log_separator()
    return {"response": clean_result}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
