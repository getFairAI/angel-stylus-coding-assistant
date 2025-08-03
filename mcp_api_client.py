"""
Example client script for using the MCP-enabled Angel Stylus Coding Assistant API.
"""

import requests
import json
import time

# API endpoint
API_BASE_URL = "http://localhost:8001"

def query_assistant(prompt, model="llama3.1:8b", session_id=None):
    """
    Query the assistant with optional session ID for context preservation.
    
    Args:
        prompt: User's question
        model: LLM model to use
        session_id: Optional session ID to continue a conversation
        
    Returns:
        Response text and session ID
    """
    request_data = {
        "prompt": prompt,
        "model": model
    }
    
    # Include session ID if provided
    if session_id:
        request_data["session_id"] = session_id
        
    response = requests.post(
        f"{API_BASE_URL}/stylus-chat",
        json=request_data
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return None, None
        
    response_data = response.json()
    return response_data["response"], response_data["session_id"]

def get_conversation_history(session_id):
    """
    Retrieve conversation history for a session.
    
    Args:
        session_id: Session ID
        
    Returns:
        Conversation history as a string
    """
    response = requests.get(f"{API_BASE_URL}/conversation-history/{session_id}")
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return None
        
    return response.json()["history"]

def run_example_conversation():
    """
    Run an example conversation to demonstrate MCP capabilities.
    """
    print("Angel Stylus Coding Assistant with MCP\n")
    
    # First query (no session ID)
    print("User: What is Stylus?")
    response1, session_id = query_assistant("What is Stylus?")
    print(f"Assistant: {response1}\n")
    print(f"Session ID: {session_id}\n")
    
    time.sleep(1)  # Small delay for readability
    
    # Second query (with session ID)
    print("User: How can I use it with Rust?")
    response2, session_id = query_assistant("How can I use it with Rust?", session_id=session_id)
    print(f"Assistant: {response2}\n")
    
    time.sleep(1)  # Small delay for readability
    
    # Third query (follow-up with context)
    print("User: Show me an example contract")
    response3, session_id = query_assistant("Show me an example contract", session_id=session_id)
    print(f"Assistant: {response3}\n")
    
    # Display the full conversation history
    print("\n=== Conversation History ===")
    history = get_conversation_history(session_id)
    print(history)
    
if __name__ == "__main__":
    print("Starting MCP API client example...\n")
    try:
        run_example_conversation()
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Make sure the API server is running at http://localhost:8001")
    print("\nDone.") 