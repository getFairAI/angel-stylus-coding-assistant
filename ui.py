import os.path
from rag_query import query_rag
import streamlit as st
from load import init_code, clear_database, update_db_code
st.set_page_config(page_title="FactBot: No Hallucinations, Just Facts")
with st.sidebar:
    st.title('FactBot')

    st.button("Init Default DB", on_click=init_code)
    st.button("Reset DB", on_click=clear_database)
    # Upload more files for RAG
    uploaded_files = st.file_uploader("Choose 1 or many file(s)", accept_multiple_files=True, type=['.md', '.json'], help="Only Markdown or JSON files")
    for uploaded_file in uploaded_files:
        # To read file as bytes:
        print(uploaded_file.name)
        bytes_data = uploaded_file.getvalue()
        with open(uploaded_file.name, 'wb') as f:
            f.write(bytes_data)
        # call load_docs_json
        print(uploaded_file.type)
        update_db_code(uploaded_file.name, uploaded_file.type == 'application/json')

        
    # Reset Vector DAta
    option = st.selectbox(
        "Model to use",
        ("mistral", "llama3", "llama3.3", "deepseek-r1:7b"),
    )

    st.write("You selected:", option)

# Function for generating LLM response
def generate_response(input):
    result = query_rag(option, input)
    return result

# Store LLM generated responses
if "messages" not in st.session_state.keys():
    st.session_state.messages = [{"role": "assistant", "content": "I am a Stylus coding assistant, how can i help?"}]

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
            
            response = generate_response("".join([ "".join([dict["role"], dict["content"]]) for dict in st.session_state.messages])) 
            
            st.write(response) 
    message = {"role": "assistant", "content": response}
    st.session_state.messages.append(message)