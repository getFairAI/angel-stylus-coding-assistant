"""
Ingest the OpenZeppelin Stylus contracts *source* (OpenZeppelin/rust-contracts-stylus).

Complements the OZ *docs* crawler with the actual, version-tagged contract
implementations. Pins to the latest release tag so the ingested code matches a
published crate version and stamps ``sdk_version`` for version-aware retrieval.

Outputs: data/openzeppelin_stylus_code.json
"""

from typing import List, Dict

from dotenv import load_dotenv

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import (
    record_ingestion_stats,
    should_skip_ingestion,
)
from ingestion.code_repo_utils import (
    build_headers,
    collect_repo_code_entries,
    latest_release,
    save_code_entries,
)

load_dotenv()

HEADERS = build_headers()

REPO = "OpenZeppelin/rust-contracts-stylus"
OUTPUT_JSON_PATH = "data/openzeppelin_stylus_code.json"
JOB_NAME = "openzeppelin_stylus_code"

ALLOWED_EXTENSIONS = (".rs", ".toml", ".md")


def ingest_openzeppelin_stylus_code(force_refresh: bool = False):
    if should_skip_ingestion(JOB_NAME, force_refresh=force_refresh):
        write_ingestion_log(f"[skip] {JOB_NAME}: previous run had no changes; use --force-refresh to override")
        record_ingestion_stats(JOB_NAME, {"added": 0, "updated": 0, "unchanged": 0, "retained": 0}, skipped=True)
        return 0

    release = latest_release(REPO, HEADERS)
    if release:
        ref = release["tag"]
        released_at = release.get("published_at")
        write_ingestion_log(f"[info] Pinning {REPO} to release {ref}")
    else:
        ref = None  # collector falls back to default branch
        released_at = None
        write_ingestion_log(f"[warn] No release/tag resolved for {REPO}; using default branch HEAD")

    # sdk_version left None -> collector detects it from the repo's Cargo.toml.
    entries: List[Dict] = collect_repo_code_entries(
        REPO,
        source="openzeppelin_stylus_code",
        allowed_extensions=ALLOWED_EXTENSIONS,
        headers=HEADERS,
        ref=ref,
        released_at=released_at,
    )
    merged = save_code_entries(OUTPUT_JSON_PATH, entries, JOB_NAME)
    return len(merged)


if __name__ == "__main__":
    ingest_openzeppelin_stylus_code()
