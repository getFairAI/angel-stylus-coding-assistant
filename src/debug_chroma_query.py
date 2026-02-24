"""
Manual utility for quickly probing the local Chroma collection.

This is intentionally not a pytest file.
"""

from chroma_query import get_chroma_documents


def main():
    query = "How do I deploy and verify a Stylus contract?"
    hits = get_chroma_documents(query)
    for idx, hit in enumerate(hits[:3], 1):
        title = (hit.get("metadata") or {}).get("title", "unknown")
        print(f"\n[{idx}] {title}\n{(hit.get('text') or '')[:400]}")


if __name__ == "__main__":
    main()
