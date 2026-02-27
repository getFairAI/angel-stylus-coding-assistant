"""
Ingest code from community projects referenced in the awesome-stylus list.
Outputs: data/awesome_stylus_code.json
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

HEADERS = {"User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"}
token = os.environ.get("GITHUB_TOKEN")
if token:
    HEADERS["Authorization"] = f"Bearer {token}"

AWESOME_REPO = "OffchainLabs/awesome-stylus"
# GitHub API raw endpoint gives canonical markdown, avoiding HTML placeholders
AWESOME_README_API = "https://api.github.com/repos/OffchainLabs/awesome-stylus/contents/README.md"

OUTPUT_JSON_PATH = "data/awesome_stylus_code.json"

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
MAX_FILE_BYTES = 200_000


def safe_json(url: str) -> Optional[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[warn] JSON fetch failed {url}: {e}")
        return None


def fetch_text(url: str, extra_headers: Optional[Dict] = None) -> Optional[str]:
    try:
        headers = HEADERS.copy()
        if extra_headers:
            headers.update(extra_headers)
        resp = requests.get(url, headers=headers, timeout=30)
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


def repo_exists(repo: str) -> bool:
    url = f"https://api.github.com/repos/{repo}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    # For other errors, assume not usable to avoid repeated failures
    return False


def search_repo(owner: str, repo_prefix: str) -> Optional[str]:
    """
    Try to find the full repo name via GitHub search when the extracted slug fails.
    Returns full_name (owner/name) or None.
    """
    query = f"{repo_prefix} in:name user:{owner}"
    url = f"https://api.github.com/search/repositories?q={requests.utils.quote(query)}&per_page=1"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if items:
            return items[0]["full_name"]
    except Exception as e:
        print(f"[info] search repo failed for {owner}/{repo_prefix}: {e}")
    return None


def extract_repo_links_from_markdown(md: str) -> List[str]:
    """
    Extract repo slugs from GitHub links in the README.
    Sources parsed:
      - Markdown links: [text](href)
      - Plain URLs in text
    Supports:
      - https://github.com/owner/repo/...
      - https://raw.githubusercontent.com/owner/repo/branch/path
      - /owner/repo or owner/repo inside markdown href
    """
    repos = set()

    def valid_part(part: str) -> bool:
        return bool(re.match(r"^[A-Za-z0-9_.-]+$", part))

    hrefs = set()
    # 1) Markdown links
    for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", md):
        hrefs.add(m.group(1))
    # 2) Plain URLs
    for url in re.findall(r"https?://[^\s)]+", md):
        hrefs.add(url)

    for url in hrefs:
        # normalize relative or owner/repo hrefs
        if url.startswith("/"):
            url = f"https://github.com{url}"
        elif re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", url):
            url = f"https://github.com/{url}"

        # strip trailing punctuation
        url = url.rstrip(").,`>\"'")
        try:
            parsed = requests.utils.urlparse(url)
        except Exception:
            continue
        netloc = parsed.netloc.lower()
        path_parts = parsed.path.strip("/").split("/")
        if netloc.endswith("github.com"):
            if len(path_parts) >= 2 and valid_part(path_parts[0]) and valid_part(path_parts[1]):
                slug = f"{path_parts[0]}/{path_parts[1]}"
                repos.add(slug)
        elif netloc.endswith("raw.githubusercontent.com"):
            if len(path_parts) >= 2 and valid_part(path_parts[0]) and valid_part(path_parts[1]):
                slug = f"{path_parts[0]}/{path_parts[1]}"
                repos.add(slug)

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

    repos = cleaned
    return sorted(repos)


def build_entry(repo: str, ref: str, path: str, text: str) -> Dict:
    now_iso = datetime.utcnow().isoformat() + "Z"
    raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
    return {
        "text": text,
        "metadata": {
            "source": "awesome_stylus_code",
            "repo": repo,
            "ref": ref,
            "path": path,
            "url": raw_url,
            "ingested_at": now_iso,
        },
    }


def collect_repo_files(repo: str) -> List[Dict]:
    if not repo_exists(repo):
        owner, name = repo.split("/", 1)
        suggestion = search_repo(owner, name)
        if suggestion and repo_exists(suggestion):
            print(f"[info] Resolved {repo} -> {suggestion} via search")
            repo = suggestion
        else:
            print(f"[warn] Repo not found or inaccessible: {repo}")
            return []

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
        if "/node_modules/" in f"/{path}/":
            continue
        if not path.lower().endswith(ALLOWED_EXTENSIONS):
            continue

        raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
        content = fetch_text(raw_url)
        if not content:
            continue

        entries.append(build_entry(repo, ref, path, content))

    print(f"[ok] Collected {len(entries)} files from {repo}")
    return entries


def ingest_awesome_stylus_code():
    entries: List[Dict] = []
    readme = fetch_text(
        AWESOME_README_API,
        extra_headers={"Accept": "application/vnd.github.v3.raw"},
    )
    if not readme:
        print("[warn] Could not fetch awesome-stylus README; skipping")
    else:
        repo_slugs = extract_repo_links_from_markdown(readme)
        if not repo_slugs:
            print("[warn] No repo links detected in README")
        for repo in repo_slugs:
            entries.extend(collect_repo_files(repo))

    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[✔] Saved {len(entries)} community code entries to {OUTPUT_JSON_PATH}")
    return len(entries)


if __name__ == "__main__":
    ingest_awesome_stylus_code()
