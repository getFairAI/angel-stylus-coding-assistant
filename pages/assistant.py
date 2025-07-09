from rag_query import query_rag
from rag_wrapper import stylus_chat
import streamlit as st

with st.sidebar:
    # Reset Vector DAta
    option = st.selectbox(
        "Model to use",
        ("deepseek-r1:7b", "llama3.1:8b", "deepseek-r1:14b", "qwen2.5:32b")
        #("mistral", "llama3", "llama3.3", "deepseek-r1:7b"),
    )

    st.write("You selected:", option)

# Function for generating LLM response
def generate_response(input):
    result = stylus_chat(option, input)
    return result

# Store LLM generated responses
if "messages" not in st.session_state.keys():
    st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm your Stylus coding assistant. Please note that I will not remember previous messages, so include all the details you need help with in each question. How can I help today?"}]

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
        with st.spinner("Getting your answer from superior intelligence.."):
            
            #response = generate_response("".join([ "".join([dict["role"], dict["content"]]) for dict in st.session_state.messages])) 
            response = generate_response(input) 
            st.write(response) 
    message = {"role": "assistant", "content": response}
    st.session_state.messages.append(message)