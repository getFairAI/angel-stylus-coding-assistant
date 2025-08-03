"""
Test script for the MCP (Model Context Protocol) implementation.
This script simulates a conversation with the Stylus assistant using MCP.
"""

import time
import uuid
from mcp_handler import MCPHandler
from rag_wrapper import stylus_chat
from logger import log_info, log_separator

def test_mcp_conversation():
    """
    Test a multi-turn conversation with MCP support.
    """
    # Initialize the MCP handler
    mcp = MCPHandler()
    
    # Generate a session ID for this conversation
    session_id = str(uuid.uuid4())
    print(f"Starting conversation with session ID: {session_id}")
    
    # First message
    prompt1 = "What is Stylus?"
    print(f"\nUser: {prompt1}")
    response1, session_id = stylus_chat("llama3.1:8b", prompt1, session_id)
    print(f"Assistant: {response1}")
    
    time.sleep(1)  # Small delay for readability
    
    # Second message with context
    prompt2 = "What programming languages can I use with it?"
    print(f"\nUser: {prompt2}")
    response2, session_id = stylus_chat("llama3.1:8b", prompt2, session_id)
    print(f"Assistant: {response2}")
    
    time.sleep(1)  # Small delay for readability
    
    # Third message asking for code
    prompt3 = "Give me an example of a simple Rust program for Stylus."
    print(f"\nUser: {prompt3}")
    response3, session_id = stylus_chat("llama3.1:8b", prompt3, session_id)
    print(f"Assistant: {response3}")
    
    # Display the conversation history from MCP
    history = mcp.get_conversation_history(session_id)
    print("\n--- Conversation History from MCP ---")
    print(history)
    
    return session_id

if __name__ == "__main__":
    log_separator()
    log_info("Starting MCP test")
    session_id = test_mcp_conversation()
    log_info(f"MCP test completed with session ID: {session_id}")
    log_separator() 