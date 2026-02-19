import os
import json
import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import sys
from dotenv import load_dotenv

# load variables from .env
load_dotenv()


# ---------------------------------------------
# Config
# ---------------------------------------------

REPOS = [
    "OffchainLabs/cargo-stylus",
    "OffchainLabs/awesome-stylus/",
    "OffchainLabs/stylus-sdk-rs"
]

# Output JSON file path
OUTPUT_JSON_PATH = "data/github_issues_sectioned.json"
OUTPUT_LAST_SYNCED_PATH= "logs/last_ingestion_sync.json"

# When generating github token if needed, make sure it only has READ access to PUBLIC repositories, no other permissions are needed
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

if GITHUB_TOKEN is None:
    print("Missing github token. Exiting...")
    sys.exit(0)


HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"
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
def save_entries(path: str, new_entries: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    existing_entries: List[Dict[str, Any]] = []

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                existing_entries = json.load(f)
            except Exception:
                existing_entries = []

    # ---------------------------------------------
    # Build lookup of existing unique IDs
    # ---------------------------------------------
    existing_ids = set()

    for entry in existing_entries:
        meta = entry.get("metadata", {})
        unique_id = (
            meta.get("comment_url")
            or meta.get("issue_url")
        )
        if unique_id:
            existing_ids.add(unique_id)

    # ---------------------------------------------
    # Filter new entries
    # ---------------------------------------------
    filtered_new_entries = []

    for entry in new_entries:
        meta = entry.get("metadata", {})
        unique_id = (
            meta.get("comment_url")
            or meta.get("issue_url")
        )

        if not unique_id:
            continue

        if unique_id not in existing_ids:
            filtered_new_entries.append(entry)
            existing_ids.add(unique_id)

    # ---------------------------------------------
    # Merge & write
    # ---------------------------------------------
    existing_entries.extend(filtered_new_entries)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing_entries, f, ensure_ascii=False, indent=2)

    print(f"[dedupe] Added {len(filtered_new_entries)} new entries (skipped {len(new_entries) - len(filtered_new_entries)})")

def read_sync_timestamp() -> Optional[str]:
    if not os.path.exists(OUTPUT_LAST_SYNCED_PATH):
        return None

    with open(OUTPUT_LAST_SYNCED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("github_issues_last_sync")

def write_sync_timestamp(timestamp: str) -> None:
    os.makedirs(os.path.dirname(OUTPUT_LAST_SYNCED_PATH), exist_ok=True)

    with open(OUTPUT_LAST_SYNCED_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"github_issues_last_sync": timestamp},
            f,
            indent=2
        )

def unix_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")

# ---------------------------------------------
# Fetch Issues via GraphQL
# ---------------------------------------------
def fetch_repo_issues_graphql(repo_slug: str, lastSync: Optional[str]) -> List[Dict[str, Any]]:
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
            headers=HEADERS,
            json={"query": GRAPHQL_QUERY, "variables": variables},
            timeout=30,
        )

        data = resp.json()
        
        if "errors" in data:
            raise RuntimeError(data["errors"])

        issues_data = data["data"]["repository"]["issues"]
        rate_info = data["data"]["rateLimit"]

        print(
            f"[rate] remaining={rate_info['remaining']} "
            f"cost={rate_info['cost']}"
        )

        all_issues.extend(issues_data["nodes"])

        if not issues_data["pageInfo"]["hasNextPage"]:
            break

        cursor = issues_data["pageInfo"]["endCursor"]

        if rate_info["remaining"] < 200:
            print("[info] Low rate limit, sleeping 60s...")
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
def ingest_github_issues():
    all_entries: List[Dict[str, Any]] = []

    print("[sync] Reading last sync timestamp...")
    last_sync = read_sync_timestamp()

    if last_sync:
        print(f"[sync] Incremental sync since {last_sync}")
    else:
        print("[sync] No sync file found — full ingestion")
        
    datetime_last_sync = unix_to_iso(last_sync) if last_sync else None

    new_sync_timestamp = int(datetime.now(tz=timezone.utc).timestamp())
    
    for repo_slug in REPOS:
        print(f"[info] Fetching issues via GraphQL for {repo_slug}")

        try:
            issues = fetch_repo_issues_graphql(repo_slug, datetime_last_sync)
        except Exception as e:
            print(e)
            print(f"[warn] Failed to fetch issues for {repo_slug}: {e}")
            continue

        print(f"[info] Found {len(issues)} issues")

        for issue in issues:
            entries = build_entries_for_issue(repo_slug, issue)
            all_entries.extend(entries)

        print(f"[ok] Added entries for {repo_slug}")

    save_entries(OUTPUT_JSON_PATH, all_entries)

    write_sync_timestamp(new_sync_timestamp)
    
    print(f"[ok] Saved {len(all_entries)} total entries")


if __name__ == "__main__":
    ingest_github_issues()
