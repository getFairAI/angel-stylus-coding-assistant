import os
import json
import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import (
    load_entries,
    merge_entries,
    record_ingestion_stats,
    should_skip_ingestion,
)

# load variables from .env
load_dotenv()


# ---------------------------------------------
# Config
# ---------------------------------------------

REPOS = [
    "OffchainLabs/cargo-stylus",
    "OffchainLabs/awesome-stylus",
    "OffchainLabs/stylus-sdk-rs",
]

JOB_NAME = "github_issues"

# Output JSON file path
OUTPUT_JSON_PATH = "data/github_issues_sectioned.json"
OUTPUT_LAST_SYNCED_PATH = "logs/last_ingestion_sync.json"

def build_headers(token: str) -> Dict[str, str]:
    """Return GitHub API headers for the provided token."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)",
    }

BASE_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

GRAPHQL_QUERY= """
query($owner: String!, $repo: String!, $cursor: String, $lastSync: DateTime) {
  repository(owner: $owner, name: $repo) {
    issues(first: 50, after: $cursor, states: [OPEN, CLOSED], orderBy: {field: UPDATED_AT, direction: ASC},  filterBy: { since: $lastSync }) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        body
        state
        createdAt
        url
        comments(first: 100) {
          nodes {
            body
            createdAt
            url
          }
        }
      }
    }
  }
  rateLimit {
    remaining
    cost
  }
}
"""



# ---------------------------------------------
# IO helpers
# ---------------------------------------------
def _entry_key(entry: Dict[str, Any]) -> Optional[str]:
    meta = entry.get("metadata", {})
    return meta.get("comment_url") or meta.get("issue_url")


def save_entries(path: str, new_entries: List[Dict[str, Any]]) -> Dict[str, int]:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    existing_entries = load_entries(path)

    # Use merge_entries for stats + dedupe
    merged, stats = merge_entries(existing_entries, new_entries, key_fn=_entry_key, sort=False)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    write_ingestion_log(
        f"[dedupe] Added {stats['added']} new, updated {stats['updated']} (unchanged {stats['unchanged']}, retained {stats['retained']})"
    )
    return stats

def read_sync_timestamp() -> Optional[str]:
    if not os.path.exists(OUTPUT_LAST_SYNCED_PATH):
        return None

    with open(OUTPUT_LAST_SYNCED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("github_issues_last_sync")

def write_sync_timestamp(timestamp: int) -> None:
    os.makedirs(os.path.dirname(OUTPUT_LAST_SYNCED_PATH), exist_ok=True)

    with open(OUTPUT_LAST_SYNCED_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"github_issues_last_sync": timestamp},
            f,
            indent=2
        )

def unix_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def get_github_token() -> str:
    """
    Return a GitHub token or raise an informative error so the caller can decide
    whether to skip this ingestion step.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is missing; export a token with read-only access to public repos.")
    return token

# ---------------------------------------------
# Fetch Issues via GraphQL
# ---------------------------------------------
def fetch_repo_issues_graphql(repo_slug: str, lastSync: Optional[str], headers: Dict[str, str]) -> List[Dict[str, Any]]:
    owner, repo = repo_slug.split("/", 1)

    all_issues: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        variables = {
            "owner": owner,
            "repo": repo,
            "cursor": cursor,
            "lastSync": lastSync,
        }

        resp = requests.post(
            GRAPHQL_URL,
            headers=headers,
            json={"query": GRAPHQL_QUERY, "variables": variables},
            timeout=30,
        )

        resp.raise_for_status()

        data = resp.json()
        
        if "errors" in data:
            raise RuntimeError(data["errors"])

        repo_data = data["data"].get("repository")
        if repo_data is None:
            raise RuntimeError(f"Repository not found or access denied: {repo_slug}")

        issues_data = repo_data["issues"]
        rate_info = data["data"]["rateLimit"]

        write_ingestion_log(
            f"[rate] remaining={rate_info['remaining']} "
            f"cost={rate_info['cost']}"
        )

        all_issues.extend(issues_data["nodes"])

        if not issues_data["pageInfo"]["hasNextPage"]:
            break

        cursor = issues_data["pageInfo"]["endCursor"]

        if rate_info["remaining"] < 200:
            write_ingestion_log("[info] Low rate limit, sleeping 60s...")
            time.sleep(60)

    return all_issues

# ---------------------------------------------
# Build structured entries (same format as before)
# ---------------------------------------------
def build_entries_for_issue(
    repo_slug: str,
    issue: Dict[str, Any],
) -> List[Dict[str, Any]]:

    entries: List[Dict[str, Any]] = []
    now_iso = datetime.utcnow().isoformat() + "Z"
    repo_url = f"https://github.com/{repo_slug}"

    issue_number = issue["number"]
    issue_title = issue["title"]
    issue_body = issue.get("body") or ""
    issue_url = issue["url"]

    # ---------------------------------
    # Issue body entry
    # ---------------------------------
    header_lines = [
        "Source: GitHub Issue",
        f"Repo: {repo_slug}",
        f"URL: {issue_url}",
        f"Issue: #{issue_number}",
        f"Title: {issue_title}",
    ]
    header_text = "\n".join(header_lines)

    text_with_identity = f"{header_text}\n\n{issue_body.strip()}"

    entries.append(
        {
            "text": text_with_identity,
            "metadata": {
                "source": "github_issue",
                "repo": repo_slug,
                "repo_url": repo_url,
                "issue_number": issue_number,
                "issue_url": issue_url,
                "title": issue_title,
                "type": "issue_body",
                "ingested_at": now_iso,
            },
        }
    )

    # ---------------------------------
    # Comment entries
    # ---------------------------------
    for comment in issue["comments"]["nodes"]:
        comment_body = comment.get("body") or ""
        comment_url = comment.get("url")

        header_lines = [
            "Source: GitHub Issue Comment",
            f"Repo: {repo_slug}",
            f"URL: {comment_url}",
            f"Issue: #{issue_number}",
            f"Issue Title: {issue_title}",
        ]
        header_text = "\n".join(header_lines)

        text_with_identity = f"{header_text}\n\n{comment_body.strip()}"

        entries.append(
            {
                "text": text_with_identity,
                "metadata": {
                    "source": "github_issue_comment",
                    "repo": repo_slug,
                    "repo_url": repo_url,
                    "issue_number": issue_number,
                    "issue_url": issue_url,
                    "comment_url": comment_url,
                    "title": issue_title,
                    "type": "comment",
                    "ingested_at": now_iso,
                },
            }
        )

    return entries

# ---------------------------------------------
# Main ingestion
# ---------------------------------------------
def ingest_github_issues(force_refresh: bool = False):
    all_entries: List[Dict[str, Any]] = []

    if should_skip_ingestion(JOB_NAME, force_refresh=force_refresh):
        write_ingestion_log(f"[skip] {JOB_NAME}: previous run had no changes; use --force-refresh to override")
        record_ingestion_stats(JOB_NAME, {"added": 0, "updated": 0, "unchanged": 0, "retained": 0}, skipped=True)
        return

    try:
        token = get_github_token()
    except RuntimeError as e:
        write_ingestion_log(f"[error] Skipping GitHub issues ingestion: {e}")
        record_ingestion_stats(JOB_NAME, {"added": 0, "updated": 0, "unchanged": 0, "retained": 0}, skipped=True)
        raise

    headers = build_headers(token)

    write_ingestion_log("[sync] Reading last sync timestamp...")
    last_sync = read_sync_timestamp()

    if last_sync:
        write_ingestion_log(f"[sync] Incremental sync since {last_sync}")
    else:
        write_ingestion_log("[sync] No sync file found — full ingestion")
        
    # last_sync can be stored as int or string; normalise to int for unix->iso conversion
    datetime_last_sync = None
    if last_sync is not None:
        try:
            last_sync_int = int(last_sync)
            datetime_last_sync = unix_to_iso(last_sync_int)
        except (TypeError, ValueError):
            write_ingestion_log(f"[warn] Corrupt last sync value '{last_sync}', performing full sync")
            datetime_last_sync = None

    new_sync_timestamp = int(datetime.now(tz=timezone.utc).timestamp())
    fetch_success = False
    
    for repo_slug in REPOS:
        write_ingestion_log(f"[info] Fetching issues via GraphQL for {repo_slug}")

        try:
            issues = fetch_repo_issues_graphql(repo_slug, datetime_last_sync, headers)
        except Exception as e:
            write_ingestion_log(str(e))
            write_ingestion_log(f"[warn] Failed to fetch issues for {repo_slug}: {e}")
            continue
        fetch_success = True

        write_ingestion_log(f"[info] Found {len(issues)} issues")

        for issue in issues:
            entries = build_entries_for_issue(repo_slug, issue)
            all_entries.extend(entries)

        write_ingestion_log(f"[ok] Added entries for {repo_slug}")

    # Deduplicate + persist and capture stats
    stats = save_entries(OUTPUT_JSON_PATH, all_entries)

    if fetch_success:
        write_sync_timestamp(new_sync_timestamp)

    record_ingestion_stats(JOB_NAME, stats, skipped=not fetch_success)
    write_ingestion_log(f"[ok] Saved {len(all_entries)} total entries")


if __name__ == "__main__":
    ingest_github_issues()
