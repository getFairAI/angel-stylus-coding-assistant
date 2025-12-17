import json
import os
from datetime import datetime
from typing import List, Dict, Any
import requests

# Raw README URL for awesome-stylus
README_URL = "https://raw.githubusercontent.com/OffchainLabs/awesome-stylus/main/README.md"

# Where we store all Awesome Stylus entries
OUTPUT_JSON_PATH = "data/awesome_stylus.json"

HEADERS = {
    "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"
}


# ----------------------------------------------------
# Helpers for IO
# ----------------------------------------------------
def save_entries(path: str, entries: List[Dict[str, Any]]) -> None:
    """Save entries to disk, creating the folder if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------
# Fetch README content
# ----------------------------------------------------
def fetch_readme_markdown(url: str) -> str:
    """Fetch the raw README.md content from GitHub."""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


# ----------------------------------------------------
# Parse README into semantic sections
# ----------------------------------------------------
def parse_readme_sections(markdown: str) -> List[Dict[str, Any]]:
    """
    Split README.md into sections based on headings.

    We treat:
      - top-level "# ..." as repo title (ignored as its own section)
      - "## ..." as main sections (Guides, Videos, Tools, Libraries, Projects, Examples, etc.)
      - "### ..." as subsections under a main section (e.g. Stylus Pro Series)

    Each section becomes:
      {
        "title": "Guides",
        "section": "Guides",
        "subsection": None,
        "body": "...markdown body..."
      }
    """
    lines = markdown.splitlines()

    sections: List[Dict[str, Any]] = []
    current_h2: str | None = None
    current_h3: str | None = None
    buffer: List[str] = []

    def flush_section():
        """Flush the current buffer into a section if it has content."""
        if not buffer:
            return

        # Decide the title of this section
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
                "body": text,
            }
        )

    for line in lines:
        stripped = line.strip()

        # Skip empty lines only if there's no active section yet
        # (we still keep empty lines inside sections for formatting)
        if stripped.startswith("# "):
            # Repo main title (e.g. "# Awesome Stylus") – ignore as a section
            # and flush any buffer accumulated before this (shouldn't happen often).
            flush_section()
            current_h2 = None
            current_h3 = None
            buffer = []
            continue

        if stripped.startswith("## "):
            # New main section
            flush_section()
            current_h2 = stripped[3:].strip()
            current_h3 = None
            buffer = []
            continue

        if stripped.startswith("### "):
            # New subsection under the current h2
            flush_section()
            current_h3 = stripped[4:].strip()
            buffer = []
            continue

        # Normal content line
        buffer.append(line)

    # Flush last section at the end
    flush_section()

    return sections


# ----------------------------------------------------
# Build RAG entries from sections
# ----------------------------------------------------
def build_entries_from_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert parsed sections into final JSON entries for Chroma ingestion."""
    entries: List[Dict[str, Any]] = []
    now_iso = datetime.utcnow().isoformat() + "Z"

    for sec in sections:
        metadata: Dict[str, Any] = {
            "source": "awesome_stylus",
            "title": sec["title"],
            "section": sec["section"],
            "ingested_at": now_iso,
        }
        if sec["subsection"]:
            metadata["subsection"] = sec["subsection"]

        entry = {
            "text": sec["body"],
            "metadata": metadata,
        }
        entries.append(entry)

    return entries


# ----------------------------------------------------
# Main ingestion
# ----------------------------------------------------
def ingest_awesome_stylus():
    """Main runner to fetch README and write awesome_stylus.json."""
    print(f"[info] Fetching README from {README_URL}")
    markdown = fetch_readme_markdown(README_URL)

    print("[info] Parsing README into sections...")
    sections = parse_readme_sections(markdown)
    print(f"[info] Parsed {len(sections)} sections")

    entries = build_entries_from_sections(sections)
    save_entries(OUTPUT_JSON_PATH, entries)

    print(f"[ok] Saved {len(entries)} entries to {OUTPUT_JSON_PATH}")


if __name__ == "__main__":
    ingest_awesome_stylus()
