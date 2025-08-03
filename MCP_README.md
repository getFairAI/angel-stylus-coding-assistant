# Model Context Protocol (MCP) Implementation for Angel Stylus Coding Assistant

## Overview

This document describes the Model Context Protocol (MCP) implementation in the Angel Stylus Coding Assistant. MCP enables the assistant to maintain context across multiple interactions, providing more coherent and contextually-aware responses to user queries.

## What is MCP?

Model Context Protocol (MCP) is a framework that allows AI models to understand and process context effectively across interactions. It ensures that models can:

- **Remember past interactions** - Maintaining conversation history to provide consistent responses
- **Connect related information** - Understanding references to previously mentioned topics
- **Provide personalized responses** - Tailoring answers based on the user's conversation history
- **Enhance continuity** - Creating a more natural, flowing conversation experience

## How MCP is Implemented in Angel Stylus

### Core Components

1. **MCPHandler Class** (`mcp_handler.py`)
   - Manages conversation sessions and context storage
   - Provides methods to create, retrieve, and update conversation contexts
   - Handles conversation history formatting for LLM prompts

2. **Session Management**
   - Each conversation is assigned a unique session ID
   - Context is maintained across multiple messages within a session
   - Sessions can be created, retrieved, and updated via the API

3. **Context Storage**
   - Contexts are stored both in memory (for fast access) and on disk (for persistence)
   - JSON-based storage format for easy debugging and portability
   - Automatic context retrieval when continuing a conversation

4. **API Integration**
   - REST API endpoints support session-based conversations
   - Session IDs can be provided by clients or generated automatically
   - Response includes the session ID for future interactions

## Usage

### API Usage

```python
# Example API request with session ID
import requests
import json

# First request (no session ID)
response1 = requests.post(
    "http://localhost:8001/stylus-chat",
    json={
        "model": "llama3.1:8b",
        "prompt": "What is Stylus?"
    }
).json()

# Get the session ID from the response
session_id = response1["session_id"]
print(f"Response: {response1['response']}")

# Second request (with session ID)
response2 = requests.post(
    "http://localhost:8001/stylus-chat",
    json={
        "model": "llama3.1:8b",
        "prompt": "What programming languages can I use with it?",
        "session_id": session_id
    }
).json()

print(f"Response: {response2['response']}")

# Get conversation history
history = requests.get(f"http://localhost:8001/conversation-history/{session_id}").json()
print(f"Conversation history: {history['history']}")
```

### Web Interface

The Streamlit web interface automatically manages MCP sessions:

1. Each browser session gets a unique MCP session ID
2. Conversation history is maintained as you chat
3. The "New Conversation" button in the sidebar clears the history and starts a new session

## Testing

To test the MCP implementation, run:

```bash
python test_mcp.py
```

This script simulates a conversation with multiple turns and displays the conversation history maintained by MCP.

## Limitations

1. **Session Expiration**: Currently, sessions are stored indefinitely. In production, consider adding session expiration.
2. **Memory Usage**: For production use with many users, consider optimizing the in-memory cache.
3. **Token Limits**: Very long conversations may exceed the LLM's context window. The system currently limits to the 5 most recent interactions.

## Future Improvements

1. **Session Expiration**: Add automatic expiration for inactive sessions
2. **Advanced Context Management**: Implement smarter context selection beyond the recent message limit
3. **User Authentication**: Add user authentication to associate sessions with specific users
4. **Context Compression**: Implement techniques to compress context for more efficient storage and retrieval

## Conclusion

The MCP implementation enhances the Angel Stylus Coding Assistant by enabling it to maintain context across interactions, providing a more natural and helpful conversation experience. Users can now refer to previous questions and answers without needing to repeat information, making the assistant more efficient and user-friendly. 