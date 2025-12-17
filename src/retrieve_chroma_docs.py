from chroma_query import get_chroma_documents


def join_chunks_limited(chunks, max_chars=10000):
    combined = ""
    for chunk in chunks:
        if len(combined) + len(chunk) > max_chars:
            break
        combined += chunk + "\n\n"
    return combined.strip()


def retrieve_stylus_context(user_prompt: str, max_chars: int = 10000):
    """
    Retrieve relevant Stylus documentation context for a given user query.

    This function does NOT call any LLM.
    It only returns retrieved documentation chunks, intended to be consumed
    by an external LLM (IDE / MCP / user-selected model).
    """
    docs = get_chroma_documents(user_prompt)

    if not docs:
        return {
            "found": False,
            "context": "",
            "reason": (
                "No relevant Stylus documentation was found for this query. "
                "The topic may be undocumented, outside Stylus scope, or the question may be too vague."
            ),
        }

    context = join_chunks_limited(docs, max_chars=max_chars)

    return {
        "found": True,
        "context": context,
        "chunks_used": len(docs),
    }
