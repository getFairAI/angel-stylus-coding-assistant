import streamlit as st
import sys
import os

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now import from the parent directory
from rag_wrapper import stylus_chat
from mcp_handler import MCPHandler

# Initialize the MCP handler
mcp_handler = MCPHandler()

with st.sidebar:
    # Reset Vector DAta
    option = st.selectbox(
        "Model to use",
        ("llama3.1:8b", "mistral")
    )

    st.write("You selected:", option)
    
    # Add option to clear conversation history
    if st.button("New Conversation"):
        st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm your Stylus coding assistant with MCP context retention. Ask me anything about Stylus development!"}]
        st.session_state.session_id = None

# Initialize session ID if not present
if "session_id" not in st.session_state:
    st.session_state.session_id = None

# Function for generating LLM response
def generate_response(input, session_id=None):
    result, session_id = stylus_chat(option, input, session_id)
    # Store the session ID for future use
    st.session_state.session_id = session_id
    return result

# Store LLM generated responses
if "messages" not in st.session_state.keys():
    st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm your Stylus coding assistant with MCP context retention. Ask me anything about Stylus development!"}]

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# User-provided prompt
if input := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": input})
    with st.chat_message("user"):
        st.write(input)

# Generate a new response if last message is not from assistant
if st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant"):
        with st.spinner("Getting your answer using MCP context..."):
            # Pass the session_id to maintain context across interactions
            response = generate_response(input, st.session_state.session_id) 
            st.write(response) 
    message = {"role": "assistant", "content": response}
    st.session_state.messages.append(message)