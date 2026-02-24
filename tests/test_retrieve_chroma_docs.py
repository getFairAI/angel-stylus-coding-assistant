import retrieve_chroma_docs as retrieval


def test_code_request_returns_policy_and_reference_header(monkeypatch):
    hits = [
        {
            "text": (
                "Source: GitHub README\n"
                "Repo: OffchainLabs/awesome-stylus/\n"
                "Section: Examples\n\n"
                "- [Keccak Looper](https://gist.github.com/cygaar/ee3cf1d1f98a57369717c9d91e076fd1) "
                "- A Rust contract that loops n times and hashes input"
            ),
            "metadata": {
                "source": "github_readme",
                "repo": "OffchainLabs/awesome-stylus/",
                "section": "Examples",
                "title": "Examples",
                "url": "https://github.com/OffchainLabs/awesome-stylus/",
            },
            "distance": 0.1,
        }
    ]
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: hits)

    result = retrieval.retrieve_stylus_context(
        "Write a Rust contract that loops and hashes an input string"
    )

    assert result["found"] is True
    assert result["query_mode"] == "code_request"
    assert result["context"].startswith("Top references:")
    assert "Policy: this query appears to request code generation" in result["context"]
    assert result["agent_guidance"]["behavior"] == "references_first"
    assert result["agent_guidance"]["code_generation"] == "disallowed"


def test_reference_filter_rejects_local_urls(monkeypatch):
    hits = [
        {
            "text": (
                "- [Local Ref](http://localhost:1234/debug)\n"
                "- [Public Ref](https://github.com/LimeChain/stylus-toolkit)"
            ),
            "metadata": {
                "source": "github_readme",
                "repo": "OffchainLabs/awesome-stylus/",
                "section": "Tools",
                "title": "Tools",
                "url": "https://github.com/OffchainLabs/awesome-stylus/",
            },
            "distance": 0.2,
        }
    ]
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: hits)

    result = retrieval.retrieve_stylus_context("What Stylus tools are available?")
    urls = {ref["url"] for ref in result["references"]}

    assert "http://localhost:1234/debug" not in urls
    assert "https://github.com/LimeChain/stylus-toolkit" in urls


def test_no_hits_returns_structured_not_found(monkeypatch):
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: [])

    result = retrieval.retrieve_stylus_context("query with no matches")

    assert result["found"] is False
    assert result["context"] == ""
    assert "No relevant Stylus documentation was found" in result["reason"]
    assert result["references"] == []
