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


def test_collect_references_porting_mode_keeps_primary_urls_under_inline_flood():
    ranked_hits = [
        {
            "text": (
                "- [A](https://github.com/example/a)\n"
                "- [B](https://github.com/example/b)\n"
                "- [C](https://github.com/example/c)\n"
                "- [D](https://github.com/example/d)\n"
                "- [E](https://github.com/example/e)\n"
            ),
            "metadata": {
                "source": "github_readme",
                "title": "Examples",
                "section": "Examples",
                "repo": "OffchainLabs/awesome-stylus",
                "url": "https://github.com/OffchainLabs/awesome-stylus/",
            },
        },
        {
            "text": "Uniswap hooks writeup.",
            "metadata": {
                "source": "stylus_blog",
                "title": "Unlocking DeFi Potential: How Stylus Fuels Uniswap Hook Innovation",
                "section": "Case Studies",
                "url": "https://blog.arbitrum.io/uniswap-stylus-hooks/",
            },
        },
    ]

    refs = retrieval.collect_references(
        ranked_hits,
        max_items=6,
        include_research_contract=False,
    )
    urls = {ref["url"] for ref in refs}

    assert "https://blog.arbitrum.io/uniswap-stylus-hooks/" in urls


def test_collect_references_porting_mode_skips_legacy_examples_inline_links():
    ranked_hits = [
        {
            "text": (
                "- [Zk-sunade](https://github.com/supernovahs/zk-sunade)\n"
                "- [Stylus Proxy](https://github.com/byteZorvin/stylus-proxy)\n"
            ),
            "metadata": {
                "source": "github_readme",
                "title": "Examples / Examples built with cargo-stylus v0.2.x",
                "section": "Examples",
                "subsection": "Examples built with cargo-stylus v0.2.x",
                "repo": "OffchainLabs/awesome-stylus",
                "url": "https://github.com/OffchainLabs/awesome-stylus/",
            },
        }
    ]

    porting_refs = retrieval.collect_references(
        ranked_hits,
        max_items=20,
        include_research_contract=False,
    )
    research_refs = retrieval.collect_references(
        ranked_hits,
        max_items=20,
        include_research_contract=True,
    )

    porting_urls = {ref["url"] for ref in porting_refs}
    research_urls = {ref["url"] for ref in research_refs}

    assert "https://github.com/OffchainLabs/awesome-stylus/" in porting_urls
    assert "https://github.com/supernovahs/zk-sunade" not in porting_urls
    assert "https://github.com/supernovahs/zk-sunade" in research_urls


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


def test_retrieve_context_porting_mode_adds_benchmark_and_relevant_blog(monkeypatch):
    hits = [
        {
            "text": (
                "Source: GitHub README\n"
                "Section: Examples\n"
                "- [Alpha](https://github.com/example/alpha)\n"
                "- [Beta](https://github.com/example/beta)\n"
                "- [Gamma](https://github.com/example/gamma)\n"
                "- [Delta](https://github.com/example/delta)\n"
            ),
            "metadata": {
                "source": "github_readme",
                "repo": "OffchainLabs/awesome-stylus/",
                "section": "Examples",
                "title": "Examples",
                "url": "https://github.com/OffchainLabs/awesome-stylus/",
            },
            "distance": 0.05,
        },
        {
            "text": "Source: Stylus Blog\nUniswap hooks analysis.",
            "metadata": {
                "source": "stylus_blog",
                "section": "Case Studies",
                "title": "Unlocking DeFi Potential: How Stylus Fuels Uniswap Hook Innovation",
                "url": "https://blog.arbitrum.io/uniswap-stylus-hooks/",
            },
            "distance": 0.06,
        },
    ]
    monkeypatch.setattr(retrieval, "get_chroma_documents", lambda _prompt: hits)

    result = retrieval.retrieve_stylus_context(
        "Analyze https://github.com/Uniswap/v3-core/blob/main/contracts/UniswapV3Pool.sol and return a porting verdict.",
        include_research_contract=False,
    )

    urls = [ref["url"] for ref in result["references"]]
    top_urls = urls[:10]

    assert "https://blog.arbitrum.io/uniswap-stylus-hooks/" in top_urls
    assert "https://github.com/LimeChain/stylus-benchmark" in urls
