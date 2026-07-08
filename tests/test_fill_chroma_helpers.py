import fill_chroma


def test_stable_chunk_id_is_deterministic_and_content_addressed():
    a = fill_chroma.stable_chunk_id("src-1", 0, "hello world")
    b = fill_chroma.stable_chunk_id("src-1", 0, "hello world")
    c = fill_chroma.stable_chunk_id("src-1", 0, "hello WORLD")
    assert a == b            # same inputs -> same id (idempotent upsert)
    assert a != c            # changed text -> new id (stale id gets GC'd)
    assert a.startswith("doc_") and len(a) == len("doc_") + 32


def test_source_key_prefers_url():
    assert fill_chroma._source_key({"url": "https://x/y", "title": "T"}) == "https://x/y"
    # falls back to composite identity when no url
    key = fill_chroma._source_key({"source": "s", "repo": "r", "title": "t"})
    assert key == "s|r|t"


def test_apply_overlap_prepends_previous_tail():
    units = [
        {"text": "aaaaaa", "meta": {}},
        {"text": "bbbbbb", "meta": {}},
    ]
    out = fill_chroma.apply_overlap(units, overlap=3)
    assert out[0]["text"] == "aaaaaa"          # first unchanged
    assert out[1]["text"] == "aaa bbbbbb"      # tail of prev prepended


def test_apply_overlap_noop_when_disabled_or_single():
    units = [{"text": "a", "meta": {}}, {"text": "b", "meta": {}}]
    assert fill_chroma.apply_overlap(units, overlap=0) == units
    assert fill_chroma.apply_overlap(units[:1], overlap=5) == units[:1]


def test_recursive_chunk_respects_max_chars():
    text = "sentence one. sentence two. " * 100
    chunks = fill_chroma.recursive_chunk(text, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c["text"]) <= 200 for c in chunks)
