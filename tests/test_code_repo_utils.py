"""Tests for SDK-version awareness in ingestion.code_repo_utils.

These are the pure (no-network) building blocks that let code chunks be stamped
with the SDK version they target, plus one injected-fetch collector test.
"""

from ingestion.code_repo_utils import (
    _top_minor_tags,
    collect_repo_code_entries,
    detect_sdk_version,
    find_cargo_toml_paths,
    normalize_version,
    parse_stylus_sdk_version,
    save_code_entries,
)


# --------------------------------------------------------------------------
# normalize_version
# --------------------------------------------------------------------------
def test_normalize_version_strips_prefixes():
    assert normalize_version("^0.6.0") == "0.6.0"
    assert normalize_version("~0.9") == "0.9"
    assert normalize_version("v0.10.8") == "0.10.8"
    assert normalize_version(">=0.5, <0.7") == "0.5"
    assert normalize_version("  0.8.4  ") == "0.8.4"


def test_normalize_version_handles_junk():
    assert normalize_version("") is None
    assert normalize_version(None) is None
    assert normalize_version("workspace") is None


# --------------------------------------------------------------------------
# parse_stylus_sdk_version
# --------------------------------------------------------------------------
def test_parse_simple_string_dependency():
    toml = """
[package]
name = "demo"

[dependencies]
stylus-sdk = "0.6.0"
alloy-primitives = "0.7"
"""
    assert parse_stylus_sdk_version(toml) == "0.6.0"


def test_parse_detailed_table_dependency():
    toml = """
[dependencies]
stylus-sdk = { version = "0.9.0", features = ["export-abi"] }
"""
    assert parse_stylus_sdk_version(toml) == "0.9.0"


def test_parse_underscore_crate_name():
    toml = '[dependencies]\nstylus_sdk = "0.5.1"\n'
    assert parse_stylus_sdk_version(toml) == "0.5.1"


def test_parse_workspace_dependencies_table():
    toml = """
[workspace.dependencies]
stylus-sdk = "0.10.0"
"""
    assert parse_stylus_sdk_version(toml) == "0.10.0"


def test_parse_workspace_true_reference_is_not_a_version():
    # A `workspace = true` member reference carries no concrete version here.
    toml = '[dependencies]\nstylus-sdk = { workspace = true }\n'
    assert parse_stylus_sdk_version(toml) is None


def test_parse_regex_fallback_on_malformed_toml():
    # Deliberately broken TOML (unclosed table) -> tomllib fails, regex saves it.
    toml = 'oops [not valid toml\nstylus-sdk = "0.7.2"\n'
    assert parse_stylus_sdk_version(toml) == "0.7.2"


def test_parse_missing_dependency_returns_none():
    assert parse_stylus_sdk_version('[dependencies]\nserde = "1.0"\n') is None
    assert parse_stylus_sdk_version("") is None


# --------------------------------------------------------------------------
# find_cargo_toml_paths — root wins, then shallowest
# --------------------------------------------------------------------------
def test_find_cargo_toml_paths_prefers_root():
    tree = [
        {"type": "blob", "path": "examples/a/Cargo.toml"},
        {"type": "blob", "path": "Cargo.toml"},
        {"type": "blob", "path": "src/lib.rs"},
        {"type": "tree", "path": "src"},
        {"type": "blob", "path": "crates/x/Cargo.toml"},
    ]
    paths = find_cargo_toml_paths(tree)
    assert paths[0] == "Cargo.toml"
    assert "src/lib.rs" not in paths
    assert set(paths) == {"Cargo.toml", "examples/a/Cargo.toml", "crates/x/Cargo.toml"}


# --------------------------------------------------------------------------
# detect_sdk_version — injected fetcher, root Cargo.toml wins
# --------------------------------------------------------------------------
def test_detect_sdk_version_uses_first_parseable_manifest():
    tree = [
        {"type": "blob", "path": "Cargo.toml"},
        {"type": "blob", "path": "examples/a/Cargo.toml"},
    ]
    served = {
        "https://raw.githubusercontent.com/o/r/main/Cargo.toml": "[workspace]\nmembers=[]\n",
        "https://raw.githubusercontent.com/o/r/main/examples/a/Cargo.toml": '[dependencies]\nstylus-sdk = "0.8.0"\n',
    }
    version = detect_sdk_version(
        "o/r", "main", tree, {}, fetcher=lambda url: served.get(url)
    )
    assert version == "0.8.0"


# --------------------------------------------------------------------------
# collect_repo_code_entries — stamps sdk_version, skips build artifacts
# --------------------------------------------------------------------------
def test_collect_repo_code_entries_stamps_version(monkeypatch):
    import ingestion.code_repo_utils as cru

    tree = [
        {"type": "blob", "path": "src/lib.rs"},
        {"type": "blob", "path": "target/debug/junk.rs"},  # skipped (build dir)
        {"type": "blob", "path": "README.md"},
        {"type": "blob", "path": "logo.png"},  # skipped (extension)
    ]
    monkeypatch.setattr(cru, "github_tree", lambda repo, ref, headers: tree)
    monkeypatch.setattr(
        cru, "fetch_text", lambda url, headers, max_bytes=200_000: f"// {url}"
    )

    entries = collect_repo_code_entries(
        "o/r",
        source="unit_test_code",
        allowed_extensions=(".rs", ".md"),
        headers={},
        ref="main",
        sdk_version="0.9.0",
    )

    paths = sorted(e["metadata"]["path"] for e in entries)
    assert paths == ["README.md", "src/lib.rs"]
    assert all(e["metadata"]["sdk_version"] == "0.9.0" for e in entries)
    assert all(e["metadata"]["source"] == "unit_test_code" for e in entries)


# --------------------------------------------------------------------------
# _top_minor_tags — newest patch per minor, top N minors
# --------------------------------------------------------------------------
def test_top_minor_tags_picks_newest_patch_per_minor():
    tags = ["v0.10.8", "v0.10.7", "v0.9.0", "v0.8.4", "v0.8.3", "v0.7.0"]
    assert _top_minor_tags(tags, 3) == ["v0.10.8", "v0.9.0", "v0.8.4"]


def test_top_minor_tags_ignores_non_semver_and_dedupes_minor():
    tags = ["latest", "v0.9.1", "0.9.0", "nightly", "v0.8.0"]
    assert _top_minor_tags(tags, 5) == ["v0.9.1", "v0.8.0"]


# --------------------------------------------------------------------------
# save_code_entries — multi-version keys coexist; window prune drops rolled-off
# --------------------------------------------------------------------------
def test_save_code_entries_multi_version_prunes_outside_window(tmp_path, monkeypatch):
    import ingestion.incremental_utils as iu

    monkeypatch.setattr(iu, "INGESTION_STATS_PATH", str(tmp_path / "stats.json"))
    out = str(tmp_path / "framework.json")

    def entry(ref, version, path):
        return {
            "text": f"{ref}:{path}",
            "metadata": {"repo": "o/r", "ref": ref, "sdk_version": version, "path": path},
        }

    # Two versions of the same path must coexist under multi_version keys.
    first = [entry("v0.9.0", "0.9.0", "src/lib.rs"), entry("v0.8.0", "0.8.0", "src/lib.rs")]
    merged = save_code_entries(out, first, "framework_test", multi_version=True,
                               keep_refs={"v0.9.0", "v0.8.0"})
    versions = {e["metadata"]["sdk_version"] for e in merged}
    assert versions == {"0.8.0", "0.9.0"}

    # New run: 0.10 arrives, 0.8 rolls off the window -> pruned, 0.9 carried.
    second = [entry("v0.10.0", "0.10.0", "src/lib.rs"), entry("v0.9.0", "0.9.0", "src/lib.rs")]
    merged = save_code_entries(out, second, "framework_test", multi_version=True,
                               keep_refs={"v0.10.0", "v0.9.0"})
    versions = {e["metadata"]["sdk_version"] for e in merged}
    assert versions == {"0.9.0", "0.10.0"}
    assert "0.8.0" not in versions
