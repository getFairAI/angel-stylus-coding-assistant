"""
Ingest the source of the Stylus-by-Example repo (contract examples + prose).

The rendered pages are already partially covered by the docs ingestion via a
hardcoded URL list; ingesting the repo captures the raw example source, auto-
tracks newly added examples, and stamps the SDK version the examples target.

Outputs: data/stylus_by_example_code.json
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
    save_code_entries,
)

load_dotenv()

HEADERS = build_headers()

REPO = "OffchainLabs/stylus-by-example"
OUTPUT_JSON_PATH = "data/stylus_by_example_code.json"
JOB_NAME = "stylus_by_example"

# .mdx captures the example walkthroughs; .rs/.toml the runnable contract source.
ALLOWED_EXTENSIONS = (".rs", ".toml", ".md", ".mdx")


def ingest_stylus_by_example(force_refresh: bool = False):
    if should_skip_ingestion(JOB_NAME, force_refresh=force_refresh):
        write_ingestion_log(f"[skip] {JOB_NAME}: previous run had no changes; use --force-refresh to override")
        record_ingestion_stats(JOB_NAME, {"added": 0, "updated": 0, "unchanged": 0, "retained": 0}, skipped=True)
        return 0

    entries: List[Dict] = collect_repo_code_entries(
        REPO,
        source="stylus_by_example_code",
        allowed_extensions=ALLOWED_EXTENSIONS,
        headers=HEADERS,
    )
    merged = save_code_entries(OUTPUT_JSON_PATH, entries, JOB_NAME)
    return len(merged)


if __name__ == "__main__":
    ingest_stylus_by_example()
