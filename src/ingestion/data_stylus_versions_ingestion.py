"""
Stylus SDK version awareness ingestion.

Sources:
- CHANGELOG.md from OffchainLabs/stylus-sdk-rs (versions and notes)
- Recent merged PRs from OffchainLabs/stylus-sdk-rs (for migration hints)

Outputs: data/stylus_versions.json
Each entry contains text plus metadata: source, repo, type (changelog|pr), version (when known),
url, number (for PRs), merged_at, labels, ingested_at, ref info.
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import (
    load_entries,
    merge_entries,
    record_ingestion_stats,
    should_skip_ingestion,
)

load_dotenv()

REPO = "OffchainLabs/stylus-sdk-rs"
OWNER, NAME = REPO.split("/", 1)
CHANGELOG_URL = f"https://raw.githubusercontent.com/{REPO}/main/CHANGELOG.md"
OUTPUT_JSON_PATH = "data/stylus_versions.json"
JOB_NAME = "stylus_versions"

HEADERS = {
    "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)",
}

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def fetch_text(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        write_ingestion_log(f"[warn] Failed to fetch {url}: {e}")
        return None


def parse_changelog(changelog_text: str) -> List[Dict]:
    """
    Split CHANGELOG sections by version headings and emit entries.
    Accepts headings like:
      ## [v1.2.3] - 2025-01-01
      ## v1.2.3
      ## Version 1.2.3
    """
    entries: List[Dict] = []
    now_iso = datetime.utcnow().isoformat() + "Z"
    pattern = re.compile(r"^##\\s*(?:\\[?version\\s*)?v?(\\d+\\.\\d+\\.\\d+[^\\s\\]]*)", re.IGNORECASE)

    lines = changelog_text.splitlines()
    current_version = None
    buffer: List[str] = []

    def flush():
        nonlocal buffer, current_version
        if current_version and buffer:
            body = "\n".join(buffer).strip()
            header = [
                "Source: Stylus SDK CHANGELOG",
                f"Repo: {REPO}",
                f"Version: {current_version}",
                f"URL: {CHANGELOG_URL}",
            ]
            entries.append(
                {
                    "text": "\n\n".join(["\n".join(header), body]),
                    "metadata": {
                        "source": "stylus_changelog",
                        "repo": REPO,
                        "version": current_version,
                        "url": CHANGELOG_URL,
                        "type": "changelog",
                        "ingested_at": now_iso,
                    },
                }
            )
        buffer = []

    for line in lines:
        match = pattern.match(line.strip())
        if match:
            flush()
            current_version = match.group(1)
        else:
            buffer.append(line)

    flush()
    write_ingestion_log(f"[ok] Parsed {len(entries)} changelog versions")
    return entries


PR_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 50, after: $cursor, states: MERGED, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        mergedAt
        url
        baseRefName
        headRefName
      }
    }
  }
  rateLimit { remaining cost }
}
"""


def fetch_merged_prs(limit: int = 150) -> List[Dict]:
    cursor = None
    collected: List[Dict] = []

    if "Authorization" not in HEADERS:
        write_ingestion_log("[warn] GITHUB_TOKEN is missing; PR ingestion will likely hit rate limits")

    while len(collected) < limit:
        resp = requests.post(
            "https://api.github.com/graphql",
            headers=HEADERS,
            json={"query": PR_QUERY, "variables": {"owner": OWNER, "name": NAME, "cursor": cursor}},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        repo = data.get("data", {}).get("repository")
        if not repo:
            write_ingestion_log("[warn] Repository not found or access denied for PR fetch")
            break

        pr_data = repo["pullRequests"]
        nodes = pr_data["nodes"]
        collected.extend(nodes)

        if not pr_data["pageInfo"]["hasNextPage"]:
            break
        cursor = pr_data["pageInfo"]["endCursor"]

    write_ingestion_log(f"[ok] Fetched {len(collected)} merged PRs (capped at {limit})")
    return collected[:limit]


def build_entries_for_prs(prs: List[Dict]) -> List[Dict]:
    now_iso = datetime.utcnow().isoformat() + "Z"
    entries: List[Dict] = []

    for pr in prs:
        header_lines = [
            "Source: Stylus SDK PR",
            f"Repo: {REPO}",
            f"PR: #{pr['number']} {pr['title']}",
            f"URL: {pr['url']}",
            f"Merged At: {pr.get('mergedAt')}",
            f"Base: {pr.get('baseRefName')} | Head: {pr.get('headRefName')}",
        ]
        body = pr.get("body") or ""
        text = "\n\n".join(["\n".join(header_lines), body.strip()])

        entries.append(
            {
                "text": text,
                "metadata": {
                    "source": "stylus_pr",
                    "repo": REPO,
                    "type": "pr",
                    "number": pr["number"],
                    "url": pr["url"],
                    "merged_at": pr.get("mergedAt"),
                    "base_ref": pr.get("baseRefName"),
                    "head_ref": pr.get("headRefName"),
                    "ingested_at": now_iso,
                },
            }
        )

    return entries


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def ingest_stylus_versions(force_refresh: bool = False):
    if should_skip_ingestion(JOB_NAME, force_refresh=force_refresh):
        write_ingestion_log(f"[skip] {JOB_NAME}: previous run had no changes; use --force-refresh to override")
        record_ingestion_stats(JOB_NAME, {"added": 0, "updated": 0, "unchanged": 0, "retained": 0}, skipped=True)
        return 0

    entries: List[Dict] = []

    changelog = fetch_text(CHANGELOG_URL)
    if changelog:
        entries.extend(parse_changelog(changelog))
    else:
        write_ingestion_log("[warn] Skipping changelog ingestion (not fetched)")

    try:
        prs = fetch_merged_prs(limit=150)
        entries.extend(build_entries_for_prs(prs))
    except Exception as e:
        write_ingestion_log(f"[warn] Skipping PR ingestion due to error: {e}")

    existing = load_entries(OUTPUT_JSON_PATH)
    merged, stats = merge_entries(
        existing,
        entries,
        key_fn=lambda e: (
            e.get("metadata", {}).get("type"),
            e.get("metadata", {}).get("version") or e.get("metadata", {}).get("number"),
        ),
    )

    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    write_ingestion_log(
        f"[ok] Saved {len(merged)} version-awareness entries (added {stats['added']}, updated {stats['updated']}, unchanged {stats['unchanged']}, retained {stats['retained']}) to {OUTPUT_JSON_PATH}"
    )
    record_ingestion_stats(JOB_NAME, stats)
    return len(merged)


if __name__ == "__main__":
    ingest_stylus_versions()
