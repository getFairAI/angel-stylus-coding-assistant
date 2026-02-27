import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import re
from urllib.parse import urlparse
import requests

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import (
    load_entries,
    merge_entries,
    record_ingestion_stats,
    should_skip_ingestion,
)

# List of GitHub repositories to ingest (owner/repo)
REPOS = [
    "OffchainLabs/cargo-stylus",
    "OffchainLabs/awesome-stylus",
    "OffchainLabs/stylus-sdk-rs",
]

JOB_NAME = "github_readmes"

# Output JSON file path
OUTPUT_JSON_PATH = "data/github_readmes_sectioned.json"

HEADERS = {
    "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"
}

VIDEO_HOST_KEYWORDS = (
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "loom.com",
)
VIDEO_EXTENSIONS = (
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".gif",
)

# ---------------------------------------------
# IO helpers
# ---------------------------------------------
def entry_key(entry: Dict[str, Any]):
    meta = entry.get("metadata", {})
    source = meta.get("source")
    if source == "github_readme":
        return (
            source,
            meta.get("repo"),
            meta.get("section"),
            meta.get("subsection"),
            meta.get("title"),
        )
    if source == "github_readme_linked":
        return (
            source,
            meta.get("repo"),
            meta.get("linked_url"),
        )
    return (
        source,
        meta.get("repo"),
        meta.get("title"),
        meta.get("section"),
        meta.get("subsection"),
    )


def save_entries(path: str, new_entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """Merge new entries into existing file and persist."""
    existing = load_entries(path)
    merged, stats = merge_entries(existing, new_entries, key_fn=entry_key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    write_ingestion_log(
        f"[ok] Saved {len(merged)} total README entries (added {stats['added']}, updated {stats['updated']}, unchanged {stats['unchanged']}, retained {stats['retained']}) to {path}"
    )
    record_ingestion_stats(JOB_NAME, stats)
    return stats

# ---------------------------------------------
# Fetch README (main -> master)
# ---------------------------------------------
def fetch_repo_readme_markdown(repo_slug: str) -> str:
    """
    Fetch the raw README.md content for a given repo (owner/repo).
    Tries main first, then master.
    """
    owner, repo = repo_slug.split("/", 1)
    candidates = [
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md",
    ]

    last_error = None
    for url in candidates:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Failed to fetch README.md for {repo_slug}: {last_error}")


# ---------------------------------------------
# Linked resources (for awesome-stylus)
# ---------------------------------------------
def extract_markdown_links(markdown: str) -> List[Tuple[str, str]]:
    """
    Extract (text, url) tuples from markdown link syntax [text](url).
    Skips anchors and mailto links.
    """
    links: List[Tuple[str, str]] = []
    pattern = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
    for match in pattern.finditer(markdown):
        text, url = match.group(1), match.group(2)
        if url.startswith("#") or url.startswith("mailto:"):
            continue
        links.append((text, url))
    return links


def is_video_url(url: str) -> bool:
    parsed = urlparse(url.lower())
    if parsed.netloc and any(host in parsed.netloc for host in VIDEO_HOST_KEYWORDS):
        return True
    return parsed.path.endswith(VIDEO_EXTENSIONS)


def resolve_repo_relative_url(repo_slug: str, url: str) -> str:
    """
    Convert relative GitHub README links into raw file URLs on main branch.
    If an absolute GitHub blob URL is provided, convert it to the raw form.
    If an absolute GitHub link points to a repo or file without blob/raw,
    generate best-effort raw URLs (main then master).
    Otherwise return the original absolute URL.
    """
    if url.startswith("http://") or url.startswith("https://"):
        parsed = urlparse(url)
        path_parts = parsed.path.split("/")
        if parsed.netloc == "github.com" and len(path_parts) >= 3:
            owner, repo = path_parts[1], path_parts[2]

            # Case: explicit blob URL
            if "/blob/" in parsed.path and len(path_parts) >= 6:
                branch = path_parts[4]
                remaining_path = "/".join(path_parts[5:])
                return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{remaining_path}"

            # Case: repo root or path without branch -> assume main/master
            path_after_repo = path_parts[3:]  # may be empty
            relative_path = "/".join(path_after_repo)
            branch_candidates = ["main", "master"]

            for branch in branch_candidates:
                if relative_path:
                    candidate = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{relative_path}"
                else:
                    candidate = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
                # We return the first candidate; caller will attempt fetch and fall back if needed.
                return candidate

        return url

    owner, repo = repo_slug.split("/", 1)
    return f"https://raw.githubusercontent.com/{owner}/{repo}/main/{url.lstrip('./')}"


def fetch_link_content(url: str) -> Optional[str]:
    """
    Fetch a linked resource. If the URL is a GitHub raw candidate, try main then master.
    Returns text content or None if unsuitable.
    """
    candidate_urls = [url]
    last_error: Optional[Exception] = None

    # If the URL was best-effort guessed for GitHub main/master, include the alternate branch as fallback
    if "raw.githubusercontent.com" in url and "/main/" in url:
        candidate_urls.append(url.replace("/main/", "/master/", 1))
    elif "raw.githubusercontent.com" in url and "/master/" in url:
        candidate_urls.append(url.replace("/master/", "/main/", 1))

    for candidate in candidate_urls:
        try:
            resp = requests.get(candidate, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").lower()
            if not content_type.startswith("text/") and "json" not in content_type and "markdown" not in content_type:
                write_ingestion_log(f"[info] Skipping non-text resource {candidate} (content-type={content_type})")
                return None
            return resp.text
        except Exception as e:
            last_error = e
            continue

    write_ingestion_log(f"[warn] Failed to fetch linked resource {url}: {last_error}")
    return None


def build_entries_for_links(repo_slug: str, readme_url: str, markdown: str) -> List[Dict[str, Any]]:
    """
    For the awesome-stylus repo, follow README links and ingest linked text resources.
    Videos are skipped. Each linked document becomes a separate entry.
    """
    entries: List[Dict[str, Any]] = []
    now_iso = datetime.utcnow().isoformat() + "Z"

    for link_text, link_url in extract_markdown_links(markdown):
        resolved_url = resolve_repo_relative_url(repo_slug, link_url)
        if is_video_url(resolved_url):
            continue

        content = fetch_link_content(resolved_url)
        if not content:
            continue

        header_lines = [
            "Source: GitHub README Linked Resource",
            f"Repo: {repo_slug}",
            f"README URL: {readme_url}",
            f"Link Text: {link_text}",
            f"Linked URL: {resolved_url}",
        ]
        header_text = "\n".join(header_lines)

        entries.append(
            {
                "text": f"{header_text}\n\n{content}",
                "metadata": {
                    "source": "github_readme_linked",
                    "repo": repo_slug,
                    "repo_url": f"https://github.com/{repo_slug}",
                    "linked_url": resolved_url,
                    "linked_text": link_text,
                    "ingested_at": now_iso,
                },
            }
        )

    if entries:
        write_ingestion_log(f"[ok] Added {len(entries)} linked resources for {repo_slug}")
    else:
        write_ingestion_log("[info] No linked resources ingested (after filtering videos/broken links)")

    return entries

# ---------------------------------------------
# Parse README into sections (## / ###)
# ---------------------------------------------
def parse_readme_sections(markdown: str) -> List[Dict[str, Any]]:
    """
    Split README.md into sections based on headings.

    Rules:
      - top-level "# ..." is treated as the repo title and ignored as its own section
      - "## ..." creates a new main section
      - "### ..." creates a subsection under the current "##"
    """
    lines = markdown.splitlines()

    sections: List[Dict[str, Any]] = []
    current_h2: Optional[str] = None
    current_h3: Optional[str] = None
    buffer: List[str] = []

    def flush_section():
        """Flush the current buffer into a section if it has content."""
        if not buffer:
            return

        if current_h3:
            title = f"{current_h2} / {current_h3}" if current_h2 else current_h3
        elif current_h2:
            title = current_h2
        else:
            title = "Overview & Links"

        body = "\n".join(buffer).strip()
        text = f"{title}\n\n{body}" if body else title

        sections.append(
            {
                "title": title,
                "section": current_h2 or "Overview & Links",
                "subsection": current_h3,
                "body": text,  # Note: body already includes a local title line
            }
        )

    for line in lines:
        stripped = line.strip()

        # Ignore top-level repo title "# ..."
        if stripped.startswith("# "):
            flush_section()
            current_h2 = None
            current_h3 = None
            buffer = []
            continue

        if stripped.startswith("## "):
            flush_section()
            current_h2 = stripped[3:].strip()
            current_h3 = None
            buffer = []
            continue

        if stripped.startswith("### "):
            flush_section()
            current_h3 = stripped[4:].strip()
            buffer = []
            continue

        buffer.append(line)

    flush_section()
    return sections

# ---------------------------------------------
# Build entries (one per section) with repo identity in text
# ---------------------------------------------
def build_entries_for_repo(repo_slug: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert parsed sections into final JSON entries.

    Each chunk text is prefixed with:
      - Repo: owner/repo
      - URL: https://github.com/owner/repo
      - Section/Subsection
    """
    entries: List[Dict[str, Any]] = []
    now_iso = datetime.utcnow().isoformat() + "Z"
    repo_url = f"https://github.com/{repo_slug}"

    for sec in sections:
        section_name = sec["section"]
        subsection_name = sec["subsection"]

        header_lines = [
            "Source: GitHub README",
            f"Repo: {repo_slug}",
            f"URL: {repo_url}",
            f"Section: {section_name}",
        ]
        if subsection_name:
            header_lines.append(f"Subsection: {subsection_name}")

        header_text = "\n".join(header_lines)

        # Put identity header at the very top of the chunk text
        text_with_identity = f"{header_text}\n\n{sec['body']}"

        metadata: Dict[str, Any] = {
            "source": "github_readme",
            "repo": repo_slug,
            "repo_url": repo_url,
            "title": sec["title"],
            "section": section_name,
            "ingested_at": now_iso,
        }
        if subsection_name:
            metadata["subsection"] = subsection_name

        entries.append(
            {
                "text": text_with_identity,
                "metadata": metadata,
            }
        )

    return entries

# ---------------------------------------------
# Main ingestion
# ---------------------------------------------
def ingest_github_readmes(force_refresh: bool = False):
    """Fetch and section-split READMEs from multiple repos."""
    if should_skip_ingestion(JOB_NAME, force_refresh=force_refresh):
        write_ingestion_log(f"[skip] {JOB_NAME}: previous run had no changes; use --force-refresh to override")
        record_ingestion_stats(JOB_NAME, {"added": 0, "updated": 0, "unchanged": 0, "retained": 0}, skipped=True)
        return

    all_entries: List[Dict[str, Any]] = []

    for repo_slug in REPOS:
        write_ingestion_log(f"[info] Fetching README for {repo_slug}")
        try:
            markdown = fetch_repo_readme_markdown(repo_slug)
        except Exception as e:
            write_ingestion_log(f"[warn] Failed to fetch README for {repo_slug}: {e}")
            continue

        write_ingestion_log(f"[info] Parsing README sections for {repo_slug}")
        sections = parse_readme_sections(markdown)
        write_ingestion_log(f"[info] Parsed {len(sections)} sections for {repo_slug}")

        repo_entries = build_entries_for_repo(repo_slug, sections)
        all_entries.extend(repo_entries)
        write_ingestion_log(f"[ok] Added {len(repo_entries)} entries for {repo_slug}")

        # Special handling: follow linked resources in awesome-stylus
        if repo_slug.lower().endswith("awesome-stylus"):
            readme_url = f"https://raw.githubusercontent.com/{repo_slug}/main/README.md"
            link_entries = build_entries_for_links(repo_slug, readme_url, markdown)
            all_entries.extend(link_entries)

    save_entries(OUTPUT_JSON_PATH, all_entries)


if __name__ == "__main__":
    ingest_github_readmes()
