"""
Ingest Stylus codebases for RAG:
 - Core framework: OffchainLabs/stylus-sdk-rs (bast framework)
 - Community projects referenced in awesome-stylus README

Outputs a flat JSON list: data/stylus_code.json
Each entry has: text (full file), metadata (repo, path, url, ref, language, category, ingested_at)
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

HEADERS = {
    "User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)",
}

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

FRAMEWORK_REPO = "OffchainLabs/stylus-sdk-rs"
AWESOME_REPO = "OffchainLabs/awesome-stylus"
AWESOME_README_URL = "https://raw.githubusercontent.com/OffchainLabs/awesome-stylus/main/README.md"

OUTPUT_JSON_PATH = "data/stylus_code.json"

# File selection
ALLOWED_EXTENSIONS = (
    ".rs",
    ".toml",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".py",
)
MAX_FILE_BYTES = 200_000  # skip overly large assets


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def safe_json(url: str) -> Optional[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[warn] JSON fetch failed {url}: {e}")
        return None


def fetch_text(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        if len(resp.content) > MAX_FILE_BYTES:
            print(f"[info] Skip {url} (>{MAX_FILE_BYTES} bytes)")
            return None

        ctype = resp.headers.get("content-type", "").lower()
        if "text" not in ctype and "json" not in ctype and "markdown" not in ctype:
            # Attempt decode anyway; if fails, treat as binary.
            try:
                return resp.content.decode("utf-8")
            except Exception:
                print(f"[info] Skip non-text {url} ({ctype})")
                return None

        return resp.text
    except Exception as e:
        print(f"[warn] Failed to fetch {url}: {e}")
        return None


def github_tree(repo: str, ref: str) -> Optional[List[Dict]]:
    url = f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"
    data = safe_json(url)
    if data and "tree" in data:
        return data["tree"]
    return None


def choose_ref(repo: str) -> Optional[str]:
    for ref in ["main", "master"]:
        tree = github_tree(repo, ref)
        if tree is not None:
            return ref
    print(f"[warn] Could not resolve ref for {repo}")
    return None


def extract_repo_links_from_markdown(md: str) -> List[str]:
    """
    Return unique repo slugs from GitHub links in markdown.
    """
    pattern = re.compile(r"https?://github.com/([\\w.-]+/[\\w.-]+)")
    repos = set()
    for match in pattern.finditer(md):
        slug = match.group(1).rstrip("/")
        repos.add(slug)
    return sorted(repos)


def extension_language(path: str) -> str:
    path_lower = path.lower()
    if path_lower.endswith(".rs"):
        return "rust"
    if path_lower.endswith(".toml"):
        return "toml"
    if path_lower.endswith(".md"):
        return "markdown"
    if path_lower.endswith((".yaml", ".yml")):
        return "yaml"
    if path_lower.endswith(".json"):
        return "json"
    if path_lower.endswith((".js", ".jsx")):
        return "javascript"
    if path_lower.endswith((".ts", ".tsx")):
        return "typescript"
    if path_lower.endswith(".py"):
        return "python"
    return "text"


def build_entry(repo: str, ref: str, path: str, category: str, text: str) -> Dict:
    now_iso = datetime.utcnow().isoformat() + "Z"
    raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
    return {
        "text": text,
        "metadata": {
            "source": "stylus_code",
            "repo": repo,
            "ref": ref,
            "path": path,
            "url": raw_url,
            "language": extension_language(path),
            "category": category,
            "ingested_at": now_iso,
        },
    }


# ------------------------------------------------------------
# Core functions
# ------------------------------------------------------------
def collect_repo_files(repo: str, category: str) -> List[Dict]:
    ref = choose_ref(repo)
    if not ref:
        return []

    tree = github_tree(repo, ref)
    if tree is None:
        return []

    entries: List[Dict] = []
    for node in tree:
        if node.get("type") != "blob":
            continue
        path = node.get("path", "")
        if not path.lower().endswith(ALLOWED_EXTENSIONS):
            continue

        raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
        content = fetch_text(raw_url)
        if not content:
            continue

        entries.append(build_entry(repo, ref, path, category, content))

    print(f"[ok] Collected {len(entries)} files from {repo} ({category})")
    return entries


def ingest_stylus_code():
    entries: List[Dict] = []

    # 1) Core framework
    entries.extend(collect_repo_files(FRAMEWORK_REPO, category="framework"))

    # 2) Community projects from awesome-stylus
    readme = fetch_text(AWESOME_README_URL)
    if not readme:
        print("[warn] Could not fetch awesome-stylus README; skipping community projects")
    else:
        repo_slugs = extract_repo_links_from_markdown(readme)
        # remove the awesome list itself
        repo_slugs = [r for r in repo_slugs if r.lower() != AWESOME_REPO.lower()]
        for repo in repo_slugs:
            entries.extend(collect_repo_files(repo, category="community_project"))

    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[✔] Saved {len(entries)} code entries to {OUTPUT_JSON_PATH}")
    return len(entries)


if __name__ == "__main__":
    ingest_stylus_code()
