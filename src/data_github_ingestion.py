import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests

# List of GitHub repositories to ingest (owner/repo)
REPOS = [
    "OffchainLabs/cargo-stylus",
    "OffchainLabs/awesome-stylus/",
    "OffchainLabs/stylus-sdk-rs"
]

# Output JSON file path
OUTPUT_JSON_PATH = "data/github_readmes_sectioned.json"

HEADERS = {
    "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"
}

# ---------------------------------------------
# IO helpers
# ---------------------------------------------
def save_entries(path: str, entries: List[Dict[str, Any]]) -> None:
    """Save entries to disk, overwriting previous content."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

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
def ingest_github_readmes():
    """Fetch and section-split READMEs from multiple repos."""
    all_entries: List[Dict[str, Any]] = []

    for repo_slug in REPOS:
        print(f"[info] Fetching README for {repo_slug}")
        try:
            markdown = fetch_repo_readme_markdown(repo_slug)
        except Exception as e:
            print(f"[warn] Failed to fetch README for {repo_slug}: {e}")
            continue

        print(f"[info] Parsing README sections for {repo_slug}")
        sections = parse_readme_sections(markdown)
        print(f"[info] Parsed {len(sections)} sections for {repo_slug}")

        repo_entries = build_entries_for_repo(repo_slug, sections)
        all_entries.extend(repo_entries)
        print(f"[ok] Added {len(repo_entries)} entries for {repo_slug}")

    save_entries(OUTPUT_JSON_PATH, all_entries)
    print(f"[ok] Saved {len(all_entries)} total entries to {OUTPUT_JSON_PATH}")


if __name__ == "__main__":
    ingest_github_readmes()
