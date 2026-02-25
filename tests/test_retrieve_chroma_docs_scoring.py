import retrieve_chroma_docs as retrieval


def test_score_hit_prefers_tooling_sections_for_tool_queries():
    hit = {
        "text": (
            "Source: GitHub README\n"
            "Section: Tools\n"
            "- [ToolA](https://github.com/acme/tool-a)\n"
            "- [ToolB](https://github.com/acme/tool-b)\n"
        ),
        "metadata": {
            "source": "github_readme",
            "section": "Tools",
            "repo": "OffchainLabs/awesome-stylus/",
        },
        "distance": 0.2,
    }

    tooling_prefs = retrieval.get_query_preferences("latest stylus tools")
    generic_prefs = retrieval.get_query_preferences("what is stylus")

    tooling_score = retrieval.score_hit(hit, tooling_prefs)
    generic_score = retrieval.score_hit(hit, generic_prefs)

    assert tooling_score < generic_score


def test_score_hit_code_request_prefers_repo_examples_over_docs():
    docs_hit = {
        "text": "Source: documentation - tutorial examples benchmark",
        "metadata": {"source": "documentation", "section": "Examples", "repo": ""},
        "distance": 0.1,
    }
    repo_hit = {
        "text": "Source: GitHub README\nSection: Examples",
        "metadata": {"source": "github_readme", "section": "Examples", "repo": "foo/bar"},
        "distance": 0.1,
    }
    prefs = retrieval.get_query_preferences("write a stylus contract example", code_request=True)

    docs_score = retrieval.score_hit(docs_hit, prefs)
    repo_score = retrieval.score_hit(repo_hit, prefs)

    assert repo_score < docs_score


def test_collect_references_includes_inline_and_plain_urls_and_filters_local():
    ranked_hits = [
        {
            "text": (
                "- [Local](http://localhost:3000/debug)\n"
                "- [Public](https://github.com/LimeChain/stylus-benchmark)\n"
                "See also https://blog.arbitrum.io/uniswap-stylus-hooks/."
            ),
            "metadata": {
                "source": "github_readme",
                "title": "Benchmarks",
                "section": "Examples",
                "repo": "OffchainLabs/awesome-stylus",
                "url": "https://github.com/OffchainLabs/awesome-stylus/",
            },
        }
    ]

    refs = retrieval.collect_references(ranked_hits, max_items=20)
    urls = {ref["url"] for ref in refs}

    assert "http://localhost:3000/debug" not in urls
    assert "https://github.com/OffchainLabs/awesome-stylus/" in urls
    assert "https://github.com/LimeChain/stylus-benchmark" in urls
    assert "https://blog.arbitrum.io/uniswap-stylus-hooks/" in urls


def test_collect_references_adds_docs_root_from_category_fallback():
    ranked_hits = [
        {
            "text": "No direct URLs in this chunk.",
            "metadata": {
                "source": "documentation",
                "category": "How-tos",
                "section": "How-tos",
                "title": "How-tos",
            },
        }
    ]

    refs = retrieval.collect_references(ranked_hits, max_items=20)
    urls = {ref["url"] for ref in refs}
    assert "https://docs.arbitrum.io/stylus/" in urls


def test_retrieve_context_compat_flag_and_reference_helpers(monkeypatch):
    hits = [
        {
            "text": (
                "Source: GitHub README\n"
                "Section: Tools\n\n"
                "- [cargo-stylus](https://github.com/OffchainLabs/cargo-stylus) - toolchain"
            ),
            "metadata": {
                "source": "github_readme",
                "repo": "OffchainLabs/awesome-stylus/",
                "section": "Tools",
                "title": "Tools",
                "url": "https://github.com/OffchainLabs/awesome-stylus/",
            },
            "distance": 0.05,
        }
    ]
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: hits)

    result = retrieval.retrieve_stylus_context(
        "What are the latest stylus tools?",
        include_research_contract=False,
    )

    assert result["found"] is True
    assert result["query_mode"] == "tooling"
    assert result["context"].startswith("Top references:")
    assert "References:" in result["references_markdown"]
    assert result["agent_guidance"]["behavior"] == "references_first"
