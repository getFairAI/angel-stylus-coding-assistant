from fastapi import FastAPI
from pydantic import BaseModel
from aux_functions import remove_think_tags
from llm_main_wrapper import stylus_request_with_llm
import uvicorn
from typing import Optional
from logger import log_info, log_separator
import time
import uuid
from mcp_handler import MCPHandler

app = FastAPI()
mcp_handler = MCPHandler()

class StylusRequest(BaseModel):
    model: str
    prompt: str
    session_id: Optional[str] = None

@app.post("/stylus-chat")
def stylus_chat(request: StylusRequest):
    log_info(f"User started a request | Model: {request.model} | Prompt: {request.prompt}")
    
    # Generate a session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    # Get conversation history for MCP context
    conversation_history = mcp_handler.get_conversation_history(session_id)
    
    start_time = time.time()
    
    # Pass the conversation history to the LLM wrapper
    result, retrieved_docs = stylus_request_with_llm(
        request.model, 
        request.prompt, 
        conversation_history
    )
    
    clean_result = remove_think_tags(result)
    
    # Store the interaction in MCP
    mcp_handler.add_interaction(
        session_id, 
        request.prompt, 
        clean_result, 
        retrieved_docs
    )
    
    duration = round(time.time() - start_time, 2)
    log_info(f"✅ Finished inference | Time: {duration}s | Output: {clean_result[:50]}...")
    log_separator()
    
    # Return the session ID along with the response
    return {
        "response": clean_result,
        "session_id": session_id
    }

# Add an endpoint to get conversation history
@app.get("/conversation-history/{session_id}")
def get_conversation_history(session_id: str):
    history = mcp_handler.get_conversation_history(session_id, max_interactions=10)
    return {"history": history, "session_id": session_id}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
