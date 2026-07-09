"""
Ingest code from community projects referenced in the awesome-stylus list.

Quality-filtered: archived repos are skipped, along with repos below a star
floor or not pushed within a staleness window (all env-overridable, and every
drop is logged rather than silently swallowed). Ingestion is restricted to
Rust-relevant files, and each repo's ``stylus-sdk`` version is stamped onto its
chunks so version-mismatched community code can be told apart at retrieval.

Outputs: data/awesome_stylus_code.json
"""

import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import (
    record_ingestion_stats,
    should_skip_ingestion,
)
from ingestion.code_repo_utils import (
    build_headers,
    collect_repo_code_entries,
    fetch_text,
    repo_metadata,
    save_code_entries,
)

load_dotenv()

HEADERS = build_headers()

AWESOME_REPO = "OffchainLabs/awesome-stylus"
# GitHub API raw endpoint gives canonical markdown, avoiding HTML placeholders
AWESOME_README_API = "https://api.github.com/repos/OffchainLabs/awesome-stylus/contents/README.md"

OUTPUT_JSON_PATH = "data/awesome_stylus_code.json"
JOB_NAME = "awesome_stylus_code"

# Rust-relevant only: community frontend (.js/.ts/.py) added noise without
# helping Stylus *contract* answers. README/markdown kept for project context.
ALLOWED_EXTENSIONS = (".rs", ".toml", ".md")

# Quality gates (env-overridable; lenient defaults so we filter noise, not signal).
MIN_STARS = int(os.getenv("AWESOME_MIN_STARS", "2"))
MAX_AGE_DAYS = int(os.getenv("AWESOME_MAX_AGE_DAYS", "730"))  # ~2 years


def search_repo(owner: str, repo_prefix: str) -> Optional[str]:
    """Find the full repo name via GitHub search when the extracted slug fails."""
    query = f"{repo_prefix} in:name user:{owner}"
    url = f"https://api.github.com/search/repositories?q={requests.utils.quote(query)}&per_page=1"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if items:
            return items[0]["full_name"]
    except Exception as e:  # noqa: BLE001
        write_ingestion_log(f"[info] search repo failed for {owner}/{repo_prefix}: {e}")
    return None


def extract_repo_links_from_markdown(md: str) -> List[str]:
    """
    Extract repo slugs from GitHub links in the README.
    Supports markdown links, plain URLs, github.com and raw.githubusercontent.com.
    """
    repos = set()

    def valid_part(part: str) -> bool:
        return bool(re.match(r"^[A-Za-z0-9_.-]+$", part))

    hrefs = set()
    for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", md):
        hrefs.add(m.group(1))
    for url in re.findall(r"https?://[^\s)]+", md):
        hrefs.add(url)

    for url in hrefs:
        if url.startswith("/"):
            url = f"https://github.com{url}"
        elif re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", url):
            url = f"https://github.com/{url}"

        url = url.rstrip(").,`>\"'")
        try:
            parsed = requests.utils.urlparse(url)
        except Exception:  # noqa: BLE001
            continue
        netloc = parsed.netloc.lower()
        path_parts = parsed.path.strip("/").split("/")
        if netloc.endswith("github.com") or netloc.endswith("raw.githubusercontent.com"):
            if len(path_parts) >= 2 and valid_part(path_parts[0]) and valid_part(path_parts[1]):
                repos.add(f"{path_parts[0]}/{path_parts[1]}")

    cleaned = set()
    for r in repos:
        owner, repo = r.split("/", 1)
        if r.lower() == AWESOME_REPO.lower():
            continue
        if len(owner) < 2 or len(repo) < 3:
            continue
        if not re.search(r"[A-Za-z]", repo):
            continue
        cleaned.add(r)

    return sorted(cleaned)


def _is_stale(pushed_at: Optional[str]) -> bool:
    """True if the repo hasn't been pushed within MAX_AGE_DAYS."""
    if MAX_AGE_DAYS <= 0 or not pushed_at:
        return False
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    age_days = (datetime.now(timezone.utc) - pushed).days
    return age_days > MAX_AGE_DAYS


def _passes_quality_gate(repo: str) -> Optional[Dict]:
    """Return repo metadata if the repo clears the quality gates, else None.

    Every rejection is logged so a shrinking corpus is visible, not silent.
    """
    meta = repo_metadata(repo, HEADERS)
    if meta is None:
        # Try a search fallback for a moved/renamed slug before giving up.
        owner, name = repo.split("/", 1)
        suggestion = search_repo(owner, name)
        if suggestion:
            meta = repo_metadata(suggestion, HEADERS)
        if meta is None:
            write_ingestion_log(f"[skip] {repo}: not found or inaccessible")
            return None

    if meta["archived"]:
        write_ingestion_log(f"[skip] {meta['full_name']}: archived")
        return None
    if meta["stars"] < MIN_STARS:
        write_ingestion_log(
            f"[skip] {meta['full_name']}: {meta['stars']} stars < min {MIN_STARS}"
        )
        return None
    if _is_stale(meta["pushed_at"]):
        write_ingestion_log(
            f"[skip] {meta['full_name']}: stale (last push {meta['pushed_at']})"
        )
        return None
    return meta


def collect_repo_files(repo: str) -> List[Dict]:
    meta = _passes_quality_gate(repo)
    if meta is None:
        return []

    resolved = meta["full_name"]
    return collect_repo_code_entries(
        resolved,
        source="awesome_stylus_code",
        allowed_extensions=ALLOWED_EXTENSIONS,
        headers=HEADERS,
        released_at=meta.get("pushed_at"),
        extra_meta={"stars": meta["stars"], "pushed_at": meta.get("pushed_at")},
    )


def ingest_awesome_stylus_code(force_refresh: bool = False):
    if should_skip_ingestion(JOB_NAME, force_refresh=force_refresh):
        write_ingestion_log(f"[skip] {JOB_NAME}: previous run had no changes; use --force-refresh to override")
        record_ingestion_stats(JOB_NAME, {"added": 0, "updated": 0, "unchanged": 0, "retained": 0}, skipped=True)
        return 0

    entries: List[Dict] = []
    readme = fetch_text(
        AWESOME_README_API,
        {**HEADERS, "Accept": "application/vnd.github.v3.raw"},
    )
    if not readme:
        write_ingestion_log("[warn] Could not fetch awesome-stylus README; skipping")
    else:
        repo_slugs = extract_repo_links_from_markdown(readme)
        if not repo_slugs:
            write_ingestion_log("[warn] No repo links detected in README")
        write_ingestion_log(
            f"[info] {len(repo_slugs)} candidate repos (min_stars={MIN_STARS}, max_age_days={MAX_AGE_DAYS})"
        )
        for repo in repo_slugs:
            entries.extend(collect_repo_files(repo))

    merged = save_code_entries(OUTPUT_JSON_PATH, entries, JOB_NAME)
    return len(merged)


if __name__ == "__main__":
    ingest_awesome_stylus_code()
