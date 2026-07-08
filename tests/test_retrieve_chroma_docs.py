import pytest

import retrieve_chroma_docs as retrieval


@pytest.fixture(autouse=True)
def _no_feedback_or_conversation(monkeypatch):
    """These tests exercise the corpus-retrieval and scoring paths. Feedback and
    conversation enrichment (integration-tested in test_feedback.py) is stubbed
    empty so results depend only on the mocked corpus hits."""
    monkeypatch.setattr(retrieval, "get_feedback_documents", lambda *a, **k: [])
    monkeypatch.setattr(retrieval, "get_conversation_documents", lambda *a, **k: [])


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


def test_code_helper_context_allows_snippets(monkeypatch):
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

    result = retrieval.retrieve_stylus_code_context(
        "Write a Rust contract that loops and hashes an input string"
    )

    assert result["found"] is True
    assert result["query_mode"] == "code_request"
    assert "Policy: this query appears to request code generation" not in result["context"]
    assert result["agent_guidance"]["behavior"] == "references_first"
    assert result["agent_guidance"]["code_generation"] == "allowed"


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


def test_context_includes_chunk_metadata_header(monkeypatch):
    hits = [
        {
            "text": "Body text A",
            "metadata": {
                "title": "Docs Page",
                "section": "Rust SDK",
                "source": "documentation",
                "url": "https://docs.arbitrum.io/stylus/reference/overview",
                "chunk_index": 0,
                "chunk_total": 3,
                "parent_id": "p1",
            },
            "distance": 0.1,
        },
        {
            "text": "Body text B",
            "metadata": {
                "title": "Docs Page",
                "section": "Rust SDK",
                "source": "documentation",
                "url": "https://docs.arbitrum.io/stylus/reference/overview",
                "chunk_index": 1,
                "chunk_total": 3,
                "parent_id": "p1",
            },
            "distance": 0.2,
        },
        {
            "text": "Body text C should be dropped due to per-parent limit",
            "metadata": {
                "title": "Docs Page",
                "section": "Rust SDK",
                "source": "documentation",
                "url": "https://docs.arbitrum.io/stylus/reference/overview",
                "chunk_index": 2,
                "chunk_total": 3,
                "parent_id": "p1",
            },
            "distance": 0.3,
        },
    ]

    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: hits)

    result = retrieval.retrieve_stylus_context("What is the Stylus Rust SDK?")

    # Top references header still prepends context.
    assert result["context"].startswith("Top references:")
    # Metadata header should be injected.
    assert "Docs Page | Rust SDK | source=documentation | chunk 1/3 | https://docs.arbitrum.io/stylus/reference/overview" in result["context"]
    # Only two chunks from same parent should appear.
    assert "Body text C should be dropped" not in result["context"]
    assert result["chunks_used"] == 2


def test_quality_signals_present_and_shaped(monkeypatch):
    hits = [
        {
            "text": "Stylus gas metering overview",
            "metadata": {
                "title": "Gas Metering",
                "section": "Concepts",
                "source": "documentation",
                "url": "https://docs.arbitrum.io/stylus/concepts/gas-metering",
                "ingested_at": "2026-02-01",
            },
            "distance": 0.15,
        }
    ]
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: hits)

    result = retrieval.retrieve_stylus_context("How does Stylus gas metering work?")

    qs = result["quality_signals"]
    assert qs["confidence"] == "high"  # close distance + official source
    assert qs["evidence_profile"]["official_count"] >= 1
    assert set(qs["evidence_profile"]) == {
        "official_count", "community_count", "canonical_count", "unique_domains",
    }
    assert result["answer_contract"]["format"] == "direct_answer_why_links"
    outline = result["recommended_answer_outline"]
    assert outline["direct_answer"] == ""
    assert outline["why"] and outline["links"]
    assert result["as_of_date"] == "2026-02-01"


def test_quality_signals_low_confidence_and_time_sensitive(monkeypatch):
    hits = [
        {
            "text": "Some loosely related community note",
            "metadata": {
                "title": "Note",
                "source": "github_readme",
                "repo": "someone/notes",
                "url": "https://github.com/someone/notes",
            },
            "distance": 0.75,
        }
    ]
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: hits)

    result = retrieval.retrieve_stylus_context("What is the latest Stylus SDK version?")

    qs = result["quality_signals"]
    assert qs["confidence"] == "low"
    assert qs["time_sensitive"] is True
    assert any("time-sensitive" in c.lower() for c in result["recommended_answer_outline"]["caveats"])


def test_is_time_sensitive_helper():
    prefs = {"prefer_news": False, "prefer_projects": False}
    assert retrieval.is_time_sensitive("what is the newest release", prefs) is True
    assert retrieval.is_time_sensitive("how do storage slots work", prefs) is False
    assert retrieval.is_time_sensitive("anything", {"prefer_projects": True}) is True


def test_code_context_entrypoint_allows_snippets(monkeypatch):
    hits = [
        {
            "text": "fn foo() -> U256 { ... }",
            "metadata": {
                "title": "Storage Example",
                "section": "examples",
                "source": "github_readme",
                "repo": "OffchainLabs/stylus-sdk-rs",
                "url": "https://github.com/OffchainLabs/stylus-sdk-rs",
            },
            "distance": 0.2,
        }
    ]
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: hits)

    result = retrieval.retrieve_stylus_code_context("Show me a storage example in Stylus")
    assert result["found"] is True
    assert result["agent_guidance"]["code_generation"] == "allowed"
    assert "quality_signals" in result


def test_tool_query_prepends_tool_summary(monkeypatch):
    hits = [
        {
            "text": "cargo-stylus is the CLI for building and deploying Stylus contracts.",
            "metadata": {
                "title": "cargo-stylus",
                "section": "tools",
                "source": "github_readme",
                "repo": "OffchainLabs/cargo-stylus",
                "url": "https://github.com/OffchainLabs/cargo-stylus",
            },
            "distance": 0.2,
        }
    ]
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: hits)

    result = retrieval.retrieve_stylus_context("What tooling is available for Stylus?")
    assert result["query_mode"] == "tooling"
    assert result["quality_signals"]["time_sensitive"] is False


def test_feedback_hits_are_prepended_and_labeled(monkeypatch):
    corpus = [
        {"text": "docs body", "metadata": {"source": "documentation",
         "url": "https://docs.arbitrum.io/stylus/x"}, "distance": 0.4},
    ]
    fb = [{"text": "user approved answer", "metadata": {}, "distance": 0.1}]
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _p: corpus)
    monkeypatch.setattr(retrieval, "get_feedback_documents", lambda *a, **k: fb)

    result = retrieval.retrieve_stylus_context("How do I test Stylus?")
    assert result["found"] is True
    # user-approved answer is ranked first in the context body.
    assert "user approved answer" in result["context"]


def test_classify_source_type():
    assert retrieval.classify_source_type({"source": "documentation"}) == "official"
    assert retrieval.classify_source_type({"source": "canonical"}) == "canonical"
    assert retrieval.classify_source_type(
        {"source": "x", "url": "https://docs.arbitrum.io/stylus/"}
    ) == "official"
    assert retrieval.classify_source_type(
        {"source": "github_readme", "url": "https://github.com/a/b"}
    ) == "community"
