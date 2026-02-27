"""
Ingest the Stylus Rust SDK (bast framework) codebase for RAG.
Outputs: data/stylus_framework_code.json
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

HEADERS = {"User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"}
token = os.environ.get("GITHUB_TOKEN")
if token:
    HEADERS["Authorization"] = f"Bearer {token}"

FRAMEWORK_REPO = "OffchainLabs/stylus-sdk-rs"
OUTPUT_JSON_PATH = "data/stylus_framework_code.json"

ALLOWED_EXTENSIONS = (
    ".rs",
    ".toml",
    ".md",
    ".yaml",
    ".yml",
    ".json",
)
MAX_FILE_BYTES = 200_000


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
        if github_tree(repo, ref):
            return ref
    print(f"[warn] Could not resolve ref for {repo}")
    return None


def build_entry(repo: str, ref: str, path: str, text: str) -> Dict:
    now_iso = datetime.utcnow().isoformat() + "Z"
    raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
    return {
        "text": text,
        "metadata": {
            "source": "stylus_framework_code",
            "repo": repo,
            "ref": ref,
            "path": path,
            "url": raw_url,
            "ingested_at": now_iso,
        },
    }


def collect_framework_files() -> List[Dict]:
    ref = choose_ref(FRAMEWORK_REPO)
    if not ref:
        return []

    tree = github_tree(FRAMEWORK_REPO, ref)
    if tree is None:
        return []

    entries: List[Dict] = []
    for node in tree:
        if node.get("type") != "blob":
            continue
        path = node.get("path", "")
        if not path.lower().endswith(ALLOWED_EXTENSIONS):
            continue

        raw_url = f"https://raw.githubusercontent.com/{FRAMEWORK_REPO}/{ref}/{path}"
        content = fetch_text(raw_url)
        if not content:
            continue

        entries.append(build_entry(FRAMEWORK_REPO, ref, path, content))

    print(f"[ok] Collected {len(entries)} framework files")
    return entries


def ingest_stylus_framework():
    entries = collect_framework_files()
    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"[✔] Saved {len(entries)} framework code entries to {OUTPUT_JSON_PATH}")
    return len(entries)


if __name__ == "__main__":
    ingest_stylus_framework()
