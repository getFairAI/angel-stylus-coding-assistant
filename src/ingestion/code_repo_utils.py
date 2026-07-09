"""
Shared helpers for GitHub *code* ingestion jobs (SDK framework, community
"awesome" repos, stylus-by-example, OpenZeppelin contracts).

Two responsibilities live here so every code source behaves identically:

1. Fetching a repo tree and its raw files (with a size cap and text guard).
2. SDK-version awareness — resolving the latest release tag and parsing the
   `stylus-sdk` dependency version out of a project's ``Cargo.toml`` so each
   ingested code chunk can be stamped with the SDK version it targets. Without
   this, code captured at a moving ``main``/``master`` HEAD carries no version
   identity and the assistant cannot tell 0.5-era APIs from current ones.

The version *parsing* functions are pure (no network) so they are unit-testable
without hitting GitHub; only the ``*_remote`` / release / tree helpers do IO.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Callable, Dict, List, Optional

import requests

from basic_logs import write_ingestion_log
from ingestion.incremental_utils import (
    load_entries,
    merge_entries,
    record_ingestion_stats,
)

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - project targets 3.12
    tomllib = None  # type: ignore[assignment]


DEFAULT_MAX_FILE_BYTES = 200_000
# Dependency crate names that identify a Stylus contract project. The SDK crate
# is the one whose version tells us which API surface the code targets.
STYLUS_DEP_NAMES = ("stylus-sdk", "stylus_sdk")
# Build artifacts / vendored deps that never carry useful signal.
DEFAULT_SKIP_DIRS = ("/target/", "/node_modules/", "/.git/")


def build_headers() -> Dict[str, str]:
    """Standard headers, adding the GitHub token when present for rate limits."""
    headers = {"User-Agent": "StylusRAGBot/1.0 (+https://arbitrum.io)"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


# ---------------------------------------------------------------------------
# Raw fetch helpers
# ---------------------------------------------------------------------------
def safe_json(url: str, headers: Dict[str, str]) -> Optional[dict]:
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:  # noqa: BLE001
        write_ingestion_log(f"[warn] JSON fetch failed {url}: {e}")
        return None


def fetch_text(
    url: str, headers: Dict[str, str], max_bytes: int = DEFAULT_MAX_FILE_BYTES
) -> Optional[str]:
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        if len(resp.content) > max_bytes:
            return None
        return resp.text
    except Exception as e:  # noqa: BLE001
        write_ingestion_log(f"[warn] Failed to fetch {url}: {e}")
        return None


def github_tree(repo: str, ref: str, headers: Dict[str, str]) -> Optional[List[Dict]]:
    url = f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"
    data = safe_json(url, headers)
    if data and "tree" in data:
        return data["tree"]
    return None


def choose_ref(repo: str, headers: Dict[str, str]) -> Optional[str]:
    """Resolve a usable default branch (``main`` then ``master``)."""
    for ref in ("main", "master"):
        if github_tree(repo, ref, headers):
            return ref
    write_ingestion_log(f"[warn] Could not resolve ref for {repo}")
    return None


def repo_metadata(repo: str, headers: Dict[str, str]) -> Optional[Dict]:
    """Return ``{stars, pushed_at, archived, full_name}`` or None if missing.

    Used to quality-filter community repos (skip archived / stale / low-signal).
    """
    data = safe_json(f"https://api.github.com/repos/{repo}", headers)
    if not data or "full_name" not in data:
        return None
    return {
        "full_name": data.get("full_name", repo),
        "stars": int(data.get("stargazers_count") or 0),
        "pushed_at": data.get("pushed_at"),
        "archived": bool(data.get("archived")),
    }


# ---------------------------------------------------------------------------
# SDK version awareness
# ---------------------------------------------------------------------------
_VERSION_CORE = re.compile(r"\d+(?:\.\d+){0,2}(?:[-+.][0-9A-Za-z.]+)?")


def normalize_version(raw: Optional[str]) -> Optional[str]:
    """Strip caret/tilde/comparator/`v` prefixes and return the semver core.

    ``"^0.6.0"`` -> ``"0.6.0"``, ``"v0.9"`` -> ``"0.9"``, ``">=0.5, <0.7"`` ->
    ``"0.5"`` (first constraint). Returns None when no version-like token found.
    """
    if not raw:
        return None
    stripped = raw.strip().lstrip("^~=><vV ").strip()
    match = _VERSION_CORE.match(stripped)
    if match:
        return match.group(0)
    # Fall back to the first version-like token anywhere in the string.
    match = _VERSION_CORE.search(raw)
    return match.group(0) if match else None


def _version_from_dep_value(value) -> Optional[str]:
    """Extract a version from a Cargo dependency value.

    Handles ``dep = "0.6"``, ``dep = { version = "0.6", ... }`` and
    ``dep = { workspace = true }`` (returns the sentinel ``"workspace"``).
    """
    if isinstance(value, str):
        return normalize_version(value)
    if isinstance(value, dict):
        if value.get("workspace") is True:
            return "workspace"
        version = value.get("version")
        if isinstance(version, str):
            return normalize_version(version)
    return None


_REGEX_DEP_LINE = re.compile(
    r'^\s*stylus[-_]sdk\s*=\s*'
    r'(?:"(?P<simple>[^"]+)"'  # stylus-sdk = "0.6"
    r'|\{[^}]*\bversion\s*=\s*"(?P<detailed>[^"]+)")',  # { version = "0.6", ... }
    re.MULTILINE,
)


def _regex_sdk_version(text: str) -> Optional[str]:
    match = _REGEX_DEP_LINE.search(text)
    if not match:
        return None
    return normalize_version(match.group("simple") or match.group("detailed"))


def parse_stylus_sdk_version(cargo_toml_text: Optional[str]) -> Optional[str]:
    """Parse the ``stylus-sdk`` dependency version from Cargo.toml text.

    Checks ``[dependencies]``, ``[dev-dependencies]``, ``[build-dependencies]``
    and ``[workspace.dependencies]``. Falls back to a line regex if the TOML is
    malformed (or ``tomllib`` is unavailable). ``workspace = true`` references
    are skipped since the concrete version lives in the workspace root, which is
    tried separately via the tree scan. Returns None when nothing usable found.
    """
    if not cargo_toml_text:
        return None

    if tomllib is not None:
        try:
            data = tomllib.loads(cargo_toml_text)
        except Exception:  # noqa: BLE001 - malformed toml -> regex fallback
            data = None
        if isinstance(data, dict):
            tables = ("dependencies", "dev-dependencies", "build-dependencies")
            for table in tables:
                deps = data.get(table) or {}
                for name in STYLUS_DEP_NAMES:
                    if name in deps:
                        version = _version_from_dep_value(deps[name])
                        if version and version != "workspace":
                            return version
            workspace_deps = (data.get("workspace") or {}).get("dependencies") or {}
            for name in STYLUS_DEP_NAMES:
                if name in workspace_deps:
                    version = _version_from_dep_value(workspace_deps[name])
                    if version and version != "workspace":
                        return version

    return _regex_sdk_version(cargo_toml_text)


def find_cargo_toml_paths(tree: List[Dict]) -> List[str]:
    """Return Cargo.toml paths in the tree, shallowest first (root wins)."""
    paths = [
        node.get("path", "")
        for node in tree
        if node.get("type") == "blob"
        and node.get("path", "").rsplit("/", 1)[-1] == "Cargo.toml"
    ]
    paths.sort(key=lambda p: (p.count("/"), len(p)))
    return paths


def detect_sdk_version(
    repo: str,
    ref: str,
    tree: List[Dict],
    headers: Dict[str, str],
    *,
    max_manifests: int = 5,
    fetcher: Optional[Callable[[str], Optional[str]]] = None,
) -> Optional[str]:
    """Best-effort ``stylus-sdk`` version for a repo at ``ref``.

    Scans up to ``max_manifests`` Cargo.toml files (root first) and returns the
    first parseable ``stylus-sdk`` version. ``fetcher`` is injectable for tests.
    """
    fetch = fetcher or (lambda url: fetch_text(url, headers))
    for path in find_cargo_toml_paths(tree)[:max_manifests]:
        raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
        text = fetch(raw_url)
        version = parse_stylus_sdk_version(text) if text else None
        if version:
            return version
    return None


def _semver_key(tag: str):
    core = normalize_version(tag)
    if not core:
        return None
    nums = re.findall(r"\d+", core.split("-")[0])
    return tuple(int(n) for n in nums) if nums else None


def latest_release(repo: str, headers: Dict[str, str]) -> Optional[Dict]:
    """Resolve the latest release: ``{tag, published_at}`` or None.

    Prefers the GitHub "latest release" endpoint; falls back to the highest
    semver-looking tag. Lets a code source pin to a released version instead of
    a moving HEAD so its chunks carry a real ``sdk_version``.
    """
    data = safe_json(f"https://api.github.com/repos/{repo}/releases/latest", headers)
    if data and data.get("tag_name"):
        return {"tag": data["tag_name"], "published_at": data.get("published_at")}

    tags = safe_json(f"https://api.github.com/repos/{repo}/tags?per_page=30", headers)
    if isinstance(tags, list):
        best_key = None
        best_tag = None
        for entry in tags:
            name = entry.get("name", "")
            key = _semver_key(name)
            if key and (best_key is None or key > best_key):
                best_key = key
                best_tag = name
        if best_tag:
            return {"tag": best_tag, "published_at": None}
    return None


def _top_minor_tags(tags: List[str], count: int) -> List[str]:
    """Newest tag within each of the top ``count`` minor lines, newest minor first.

    Pure/testable. Groups tags by (major, minor) and keeps the highest patch in
    each group, e.g. from [0.10.8, 0.10.7, 0.9.0, 0.8.4, 0.8.3] with count=3 ->
    [0.10.8, 0.9.0, 0.8.4].
    """
    best: Dict[tuple, tuple] = {}  # (major, minor) -> (full_key, tag)
    for tag in tags:
        key = _semver_key(tag)
        if not key:
            continue
        minor = key[:2]
        if minor not in best or key > best[minor][0]:
            best[minor] = (key, tag)
    top_minors = sorted(best.keys(), reverse=True)[: max(count, 0)]
    return [best[minor][1] for minor in top_minors]


def latest_minor_releases(
    repo: str, headers: Dict[str, str], count: int = 3
) -> List[Dict]:
    """Resolve the newest patch of each of the last ``count`` minor releases.

    Returns ``[{tag, published_at, sdk_version}]`` newest-minor first. Lets a
    source keep several SDK versions side-by-side so version-specific questions
    ("how did storage work in 0.8?") have version-appropriate material, each
    chunk stamped with its own ``sdk_version``.
    """
    tags: List[str] = []
    published: Dict[str, Optional[str]] = {}

    releases = safe_json(
        f"https://api.github.com/repos/{repo}/releases?per_page=100", headers
    )
    if isinstance(releases, list):
        for entry in releases:
            tag = entry.get("tag_name")
            if tag:
                tags.append(tag)
                published[tag] = entry.get("published_at")

    tag_list = safe_json(f"https://api.github.com/repos/{repo}/tags?per_page=100", headers)
    if isinstance(tag_list, list):
        tags.extend(entry.get("name") for entry in tag_list if entry.get("name"))

    selected = _top_minor_tags(tags, count)
    return [
        {
            "tag": tag,
            "published_at": published.get(tag),
            "sdk_version": normalize_version(tag),
        }
        for tag in selected
    ]


# ---------------------------------------------------------------------------
# Generic code collection + save
# ---------------------------------------------------------------------------
def collect_repo_code_entries(
    repo: str,
    *,
    source: str,
    allowed_extensions: tuple,
    headers: Dict[str, str],
    ref: Optional[str] = None,
    sdk_version: Optional[str] = None,
    released_at: Optional[str] = None,
    extra_meta: Optional[Dict] = None,
    skip_dirs: tuple = DEFAULT_SKIP_DIRS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> List[Dict]:
    """Fetch code files from a repo and build version-stamped RAG entries.

    Resolves ``ref`` (default branch) and ``sdk_version`` (from Cargo.toml) when
    not supplied. Every entry's metadata carries ``sdk_version`` when known so
    retrieval can distinguish/rank by SDK version.
    """
    if ref is None:
        ref = choose_ref(repo, headers)
        if not ref:
            return []

    tree = github_tree(repo, ref, headers)
    if tree is None:
        return []

    if sdk_version is None:
        sdk_version = detect_sdk_version(repo, ref, tree, headers)

    now_iso = datetime.utcnow().isoformat() + "Z"
    entries: List[Dict] = []
    for node in tree:
        if node.get("type") != "blob":
            continue
        path = node.get("path", "")
        low = path.lower()
        if any(skip in f"/{low}/" for skip in skip_dirs):
            continue
        if not low.endswith(allowed_extensions):
            continue

        raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
        content = fetch_text(raw_url, headers, max_bytes=max_file_bytes)
        if not content:
            continue

        metadata: Dict = {
            "source": source,
            "repo": repo,
            "ref": ref,
            "path": path,
            "url": raw_url,
            "ingested_at": now_iso,
        }
        # Only set keys with real values — Chroma rejects None metadata values.
        if sdk_version:
            metadata["sdk_version"] = sdk_version
        if released_at:
            metadata["released_at"] = released_at
        if extra_meta:
            metadata.update({k: v for k, v in extra_meta.items() if v is not None})

        entries.append({"text": content, "metadata": metadata})

    version_note = f" (sdk {sdk_version})" if sdk_version else ""
    write_ingestion_log(f"[ok] Collected {len(entries)} files from {repo}@{ref}{version_note}")
    return entries


def save_code_entries(
    output_path: str,
    entries: List[Dict],
    job_name: str,
    *,
    multi_version: bool = False,
    keep_refs: Optional[set] = None,
) -> List[Dict]:
    """Merge code entries into their JSON file and record run stats.

    Single-version (default) uses a (repo, path) merge key so re-pinning a source
    to a new tag replaces its files in place. ``multi_version=True`` keys on
    (repo, ref, path) so several release tags of the same repo coexist. When
    ``keep_refs`` is given, merged entries whose ``ref`` is outside that set are
    pruned — this enforces a sliding window (e.g. only the last 3 minors) while
    still carrying forward a version that was merely unreachable on this run
    (its ref stays in ``keep_refs``).
    """
    if multi_version:
        def key_fn(e):
            meta = e.get("metadata", {})
            return (meta.get("repo"), meta.get("ref"), meta.get("path"))
    else:
        def key_fn(e):
            meta = e.get("metadata", {})
            return (meta.get("repo"), meta.get("path"))

    existing = load_entries(output_path)
    merged, stats = merge_entries(existing, entries, key_fn=key_fn)

    if keep_refs is not None:
        before = len(merged)
        merged = [e for e in merged if e.get("metadata", {}).get("ref") in keep_refs]
        pruned = before - len(merged)
        if pruned:
            write_ingestion_log(
                f"[info] {job_name}: pruned {pruned} entries outside pinned refs {sorted(keep_refs)}"
            )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    write_ingestion_log(
        f"[ok] {job_name}: saved {len(merged)} entries (added {stats['added']}, "
        f"updated {stats['updated']}, unchanged {stats['unchanged']}, "
        f"retained {stats['retained']}) to {output_path}"
    )
    record_ingestion_stats(job_name, stats)
    return merged
