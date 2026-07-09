"""
Ingest the Stylus Rust SDK (base framework) codebase for RAG.

Pins to the newest patch of each of the last ``STYLUS_SDK_KEEP_MINORS`` (default
3) minor releases of ``stylus-sdk-rs`` — kept side-by-side, each chunk stamped
with its own ``sdk_version`` — so version-specific questions ("how did storage
work in 0.8?") have version-appropriate material instead of only current HEAD.
Versions that roll off the window are pruned. Falls back to the default branch
(marked ``unreleased``) when no release/tag can be resolved.

Outputs: data/stylus_framework_code.json
"""

import os
from typing import List, Dict, Set, Tuple

from dotenv import load_dotenv

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import (
    record_ingestion_stats,
    should_skip_ingestion,
)
from ingestion.code_repo_utils import (
    build_headers,
    collect_repo_code_entries,
    latest_minor_releases,
    save_code_entries,
)

load_dotenv()

HEADERS = build_headers()

FRAMEWORK_REPO = "OffchainLabs/stylus-sdk-rs"
OUTPUT_JSON_PATH = "data/stylus_framework_code.json"
JOB_NAME = "stylus_framework"

ALLOWED_EXTENSIONS = (".rs", ".toml", ".md", ".yaml", ".yml", ".json")
# How many recent minor release lines to keep indexed side-by-side.
KEEP_MINORS = int(os.getenv("STYLUS_SDK_KEEP_MINORS", "3"))


def collect_framework_files() -> Tuple[List[Dict], Set[str]]:
    """Collect SDK source across the last KEEP_MINORS minor releases.

    For the SDK repo itself the release tag *is* the SDK version, so
    ``sdk_version`` comes from the tag. Returns (entries, pinned_refs) so the
    caller can prune versions that have rolled off the window.
    """
    releases = latest_minor_releases(FRAMEWORK_REPO, HEADERS, count=KEEP_MINORS)
    if not releases:
        write_ingestion_log(
            f"[warn] No releases resolved for {FRAMEWORK_REPO}; using default branch HEAD"
        )
        entries = collect_repo_code_entries(
            FRAMEWORK_REPO,
            source="stylus_framework_code",
            allowed_extensions=ALLOWED_EXTENSIONS,
            headers=HEADERS,
            sdk_version="unreleased",
        )
        return entries, set()

    pinned = ", ".join(r["tag"] for r in releases)
    write_ingestion_log(f"[info] Pinning {FRAMEWORK_REPO} to releases: {pinned}")

    entries: List[Dict] = []
    keep_refs: Set[str] = set()
    for release in releases:
        ref = release["tag"]
        keep_refs.add(ref)
        entries.extend(
            collect_repo_code_entries(
                FRAMEWORK_REPO,
                source="stylus_framework_code",
                allowed_extensions=ALLOWED_EXTENSIONS,
                headers=HEADERS,
                ref=ref,
                sdk_version=release["sdk_version"],
                released_at=release.get("published_at"),
            )
        )
    return entries, keep_refs


def ingest_stylus_framework(force_refresh: bool = False):
    if should_skip_ingestion(JOB_NAME, force_refresh=force_refresh):
        write_ingestion_log(f"[skip] {JOB_NAME}: previous run had no changes; use --force-refresh to override")
        record_ingestion_stats(JOB_NAME, {"added": 0, "updated": 0, "unchanged": 0, "retained": 0}, skipped=True)
        return 0

    entries, keep_refs = collect_framework_files()
    merged = save_code_entries(
        OUTPUT_JSON_PATH,
        entries,
        JOB_NAME,
        multi_version=bool(keep_refs),
        keep_refs=keep_refs or None,
    )
    return len(merged)


if __name__ == "__main__":
    ingest_stylus_framework()
