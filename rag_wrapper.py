from llm_main_wrapper import stylus_request_with_llm
from logger import log_info, log_separator
import time
from aux_functions import remove_think_tags
import uuid
from mcp_handler import MCPHandler

# Initialize the MCP handler
mcp_handler = MCPHandler()

def stylus_chat(model_name: str, prompt: str, session_id=None):
    # Generate a session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
        log_info(f"Created new MCP session: {session_id}")
    else:
        log_info(f"Using existing MCP session: {session_id}")
    
    # Get conversation history
    conversation_history = mcp_handler.get_conversation_history(session_id)
    
    log_info(f"User started a request | Model: {model_name} | Prompt: {prompt} | Session: {session_id}")
    start_time = time.time()
    
    # Pass the conversation history to the LLM wrapper
    result, retrieved_docs = stylus_request_with_llm(model_name, prompt, conversation_history)
    
    clean_result = remove_think_tags(result)
    
    # Store the interaction in MCP
    mcp_handler.add_interaction(
        session_id, 
        prompt, 
        clean_result, 
        retrieved_docs
    )
    
    duration = round(time.time() - start_time, 2)
    log_info(f"✅ Finished inference | Time: {duration}s | Output: {clean_result[:50]}... | Session: {session_id}")
    log_separator()
    
    # Return both the response and the session ID
    return clean_result, session_id


