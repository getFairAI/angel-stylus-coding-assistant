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


# Matches "Keep a Changelog" version headings, e.g.:
#   ## [0.10.8](https://.../v0.10.8) - 2026-07-06
#   ## [v1.2.3] - 2025-01-01
#   ## v1.2.3
#   ## Version 1.2.3
# NOTE: this is a raw string, so single backslashes are correct regex escapes.
# (A previous double-escaped version matched nothing, so no version chunks were
# ever indexed — "what is the latest SDK version?" had nothing to retrieve.)
VERSION_HEADING_PATTERN = re.compile(
    r"^##\s*\[?(?:version\s*)?v?(\d+\.\d+\.\d+[^\s\]]*)", re.IGNORECASE
)
RELEASE_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _version_sort_key(version: str):
    """Numeric key so 0.10.8 > 0.9.0 regardless of changelog ordering."""
    return tuple(int(n) for n in re.findall(r"\d+", version.split("-")[0]))


def parse_changelog(changelog_text: str) -> List[Dict]:
    """
    Split CHANGELOG sections by version headings and emit entries, plus a single
    synthesized "latest release" summary chunk that directly answers version
    questions ("what is the current/latest Stylus SDK version?").
    """
    entries: List[Dict] = []
    now_iso = datetime.utcnow().isoformat() + "Z"

    lines = changelog_text.splitlines()
    current_version = None
    current_date = None
    buffer: List[str] = []
    seen: List[tuple] = []  # (version, date) in file order

    def flush():
        nonlocal buffer, current_version, current_date
        if current_version and buffer:
            body = "\n".join(buffer).strip()
            version_line = f"Version: {current_version}"
            if current_date:
                version_line += f" (released {current_date})"
            header = [
                "Source: Stylus SDK CHANGELOG",
                f"Repo: {REPO}",
                version_line,
                f"URL: {CHANGELOG_URL}",
            ]
            entries.append(
                {
                    "text": "\n\n".join(["\n".join(header), body]),
                    "metadata": {
                        "source": "stylus_changelog",
                        "repo": REPO,
                        "version": current_version,
                        "released_at": current_date,
                        "url": CHANGELOG_URL,
                        "type": "changelog",
                        "ingested_at": now_iso,
                    },
                }
            )
        buffer = []

    for line in lines:
        stripped = line.strip()
        match = VERSION_HEADING_PATTERN.match(stripped)
        if match:
            flush()
            current_version = match.group(1)
            date_match = RELEASE_DATE_PATTERN.search(stripped)
            current_date = date_match.group(1) if date_match else None
            seen.append((current_version, current_date))
        else:
            buffer.append(line)

    flush()

    if seen:
        # Newest by semantic version, not by file position, so "latest" is correct
        # even if the changelog is ordered oldest-first.
        ordered = sorted(seen, key=lambda vd: _version_sort_key(vd[0]), reverse=True)
        latest_version, latest_date = ordered[0]
        recent = ", ".join(f"v{v}" for v, _ in ordered[:8])
        summary = (
            f"The latest Arbitrum Stylus Rust SDK (stylus-sdk-rs) release is "
            f"v{latest_version}"
            + (f", released {latest_date}." if latest_date else ".")
            + f" Recent versions, newest first: {recent}."
        )
        header = [
            "Source: Stylus SDK CHANGELOG",
            f"Repo: {REPO}",
            "Topic: latest stylus-sdk-rs version / current SDK release",
            f"URL: {CHANGELOG_URL}",
        ]
        entries.insert(
            0,
            {
                "text": "\n\n".join(["\n".join(header), summary]),
                "metadata": {
                    # No `version`/`number` key on purpose: the incremental merge key
                    # is (type, version or number), so leaving them unset keeps a
                    # single stable "latest" entry that is updated in place rather
                    # than accumulating a stale summary per release.
                    "source": "stylus_changelog",
                    "repo": REPO,
                    "latest_version": latest_version,
                    "released_at": latest_date,
                    "url": CHANGELOG_URL,
                    "type": "changelog_latest",
                    "ingested_at": now_iso,
                },
            },
        )

    write_ingestion_log(f"[ok] Parsed {len(entries)} changelog entries (incl. latest summary)")
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
