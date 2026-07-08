"""Tests for changelog parsing in data_stylus_versions_ingestion.

Regression guard for the double-escaped regex that silently matched zero version
headings, leaving the index with no SDK-version content to retrieve.
"""

from ingestion import data_stylus_versions_ingestion as mod
from ingestion.data_stylus_versions_ingestion import (
    VERSION_HEADING_PATTERN,
    _version_sort_key,
    build_entries_for_prs,
    parse_changelog,
)

SAMPLE = """\
# Changelog

## [Unreleased]

## [0.10.8](https://github.com/OffchainLabs/stylus-sdk-rs/releases/tag/v0.10.8) - 2026-07-06
### Fixed
- Fixed a thing

## [0.10.7](https://github.com/OffchainLabs/stylus-sdk-rs/releases/tag/v0.10.7) - 2026-05-19
### Fixed
- Fixed another thing

## [0.9.0](https://github.com/OffchainLabs/stylus-sdk-rs/releases/tag/v0.9.0) - 2025-12-01
### New
- Added a feature
"""


def test_heading_pattern_matches_keep_a_changelog_form():
    m = VERSION_HEADING_PATTERN.match("## [0.10.8](https://x/v0.10.8) - 2026-07-06")
    assert m and m.group(1) == "0.10.8"
    assert VERSION_HEADING_PATTERN.match("## v0.9.0").group(1) == "0.9.0"
    assert VERSION_HEADING_PATTERN.match("## Version 0.8.4").group(1) == "0.8.4"
    assert VERSION_HEADING_PATTERN.match("## [Unreleased]") is None


def test_version_sort_key_orders_numerically():
    assert _version_sort_key("0.10.8") > _version_sort_key("0.9.0")


def test_parse_changelog_emits_versions_and_latest_summary(monkeypatch):
    monkeypatch.setattr(mod, "write_ingestion_log", lambda *a, **k: None)
    entries = parse_changelog(SAMPLE)

    versions = {e["metadata"].get("version") for e in entries if e["metadata"]["type"] == "changelog"}
    assert {"0.10.8", "0.10.7", "0.9.0"} <= versions

    latest = [e for e in entries if e["metadata"]["type"] == "changelog_latest"]
    assert len(latest) == 1, "exactly one synthesized latest-release summary"
    summary = latest[0]
    assert entries[0] is summary, "latest summary should lead the entries"
    assert summary["metadata"]["latest_version"] == "0.10.8"
    assert summary["metadata"]["released_at"] == "2026-07-06"
    assert "v0.10.8" in summary["text"]
    # stable merge key: no version/number so it updates in place across releases
    assert "version" not in summary["metadata"]
    assert "number" not in summary["metadata"]


def test_latest_is_by_version_not_file_order(monkeypatch):
    monkeypatch.setattr(mod, "write_ingestion_log", lambda *a, **k: None)
    oldest_first = """\
## [0.9.0](https://x/v0.9.0) - 2025-12-01
- old

## [0.10.8](https://x/v0.10.8) - 2026-07-06
- new
"""
    entries = parse_changelog(oldest_first)
    latest = next(e for e in entries if e["metadata"]["type"] == "changelog_latest")
    assert latest["metadata"]["latest_version"] == "0.10.8"


def test_build_entries_for_prs_shape():
    prs = [
        {
            "number": 321,
            "title": "Add storage cache",
            "body": "Improves storage access.",
            "url": "https://github.com/OffchainLabs/stylus-sdk-rs/pull/321",
            "mergedAt": "2026-06-01T00:00:00Z",
            "baseRefName": "main",
            "headRefName": "feat/cache",
        }
    ]
    entries = build_entries_for_prs(prs)
    assert len(entries) == 1
    e = entries[0]
    assert e["metadata"]["type"] == "pr"
    assert e["metadata"]["number"] == 321
    assert e["metadata"]["source"] == "stylus_pr"
    assert "#321" in e["text"] and "Add storage cache" in e["text"]


def test_ingest_stylus_versions_writes_output(tmp_path, monkeypatch):
    """Exercise the main flow with mocked network so no HTTP is performed."""
    import json

    out = tmp_path / "stylus_versions.json"
    monkeypatch.setattr(mod, "write_ingestion_log", lambda *a, **k: None)
    monkeypatch.setattr(mod, "record_ingestion_stats", lambda *a, **k: None)
    monkeypatch.setattr(mod, "should_skip_ingestion", lambda *a, **k: False)
    monkeypatch.setattr(mod, "fetch_text", lambda url: SAMPLE)
    monkeypatch.setattr(mod, "fetch_merged_prs", lambda limit=150: [])
    monkeypatch.setattr(mod, "OUTPUT_JSON_PATH", str(out))

    count = mod.ingest_stylus_versions(force_refresh=True)
    assert count >= 3
    saved = json.loads(out.read_text())
    assert any(e["metadata"]["type"] == "changelog_latest" for e in saved)
