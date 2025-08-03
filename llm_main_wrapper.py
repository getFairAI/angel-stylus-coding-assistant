from chroma_query import get_chroma_documents
from llm_decider import call_llm
#from logger import log_info

def join_chunks_limited(chunks, max_chars=10000):
    combined = ""
    for chunk in chunks:
        if len(combined) + len(chunk) > max_chars:
            break
        combined += chunk + "\n\n"
    return combined.strip()

def stylus_request_with_llm(model, user_prompt, conversation_history=""):
    docs = get_chroma_documents(user_prompt)
    
    if not docs:
        fallback_prompt = f"""
        You're acting as a dev assistant using a retrieval system based on the official Stylus documentation (Arbitrum).

        The user asked: "{user_prompt}"

        No relevant content was retrieved for this question — either because:
        – The docs don't cover this topic yet  
        – The question was too vague  
        – Or it's outside the scope of Stylus (e.g. generic Solidity, unrelated tooling, etc.)

        ⚠️ You are keeping track of previous messages using MCP (Model Context Protocol). If the user's question seems to reference something from earlier, check the conversation history provided below.

        {conversation_history}

        Keep your response short and direct.

        If it makes sense, guide the user to include things like:
        – What they're trying to do (compile, deploy, test, debug, etc.)  
        – Which tool they're using (Rust SDK, Rust CLI, etc.)  
        – The actual command or error they're dealing with

        If they already provided enough detail and we just don't have docs for it yet, tell them that clearly. Suggest they rephrase or check back later — the docs are still growing.

        ⚠️ Do **not** make anything up. If it's not in the docs, just say that.
        """

        response = call_llm(fallback_prompt, user_prompt, model)
        return response, []
    
    context = join_chunks_limited(docs)
    
    formatted_prompt = f"""
    You are a developer assistant for Stylus (Arbitrum), helping users by answering technical questions based strictly on the official documentation.

    This is a Retrieval-Augmented Generation (RAG) system. The information provided below was automatically retrieved from the official Stylus documentation, based on the user's question.
    
    Only use the information in the context below. Do **not** rely on any prior knowledge or external sources. If the context includes a URL, you may include it in your response — otherwise, never guess or generate links.

    ⚠️ Important:
    - You are using MCP (Model Context Protocol) to maintain conversation context across interactions
    - Previous conversation history is provided below, use it to provide coherent responses
    - If the user refers to something from a previous message, check the conversation history
    
    --- CONVERSATION HISTORY ---
    {conversation_history}
    --- END OF CONVERSATION HISTORY ---

    If the context doesn't contain the necessary information to answer the question, say:
    "I'm sorry, I couldn't find specific information to help with that right now. The docs are still evolving — feel free to check back later."

    Your tone should be direct, clear, and practical — like a developer helping another developer. No fluff, no guessing.

    --- START OF CONTEXT ---
    {context}
    --- END OF CONTEXT ---
    """

    response = call_llm(formatted_prompt, user_prompt, model)
    return response, docs