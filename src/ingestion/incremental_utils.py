"""
Lightweight helpers to make ingestion scripts incremental.

Usage pattern (per ingestion script):
  existing = load_entries(path)
  merged, stats = merge_entries(existing, new_entries, key_fn=my_key)
  save merged back to disk

The merge logic keeps previous entries when the content is unchanged,
updates an entry when the text changes, and adds brand new keys. Entries
missing a merge key are skipped to avoid accidental duplication.
"""

import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


# Path where per-ingestion run stats are stored. Overridable for tests.
INGESTION_STATS_PATH = os.getenv("INGESTION_STATS_PATH", "logs/ingestion_stats.json")
# How long a zero-change run suppresses another fetch (seconds). Keeps us from
# hammering sources while still allowing future runs to proceed.
# default is 1 week - 7 days
DEFAULT_SKIP_WINDOW_SECONDS = 7 * 24 * 60 * 60


def load_entries(path: str) -> List[Dict[str, Any]]:
    """Load a JSON list from disk; return empty list if missing/invalid."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def _normalize_key(key: Any) -> Optional[str]:
    """
    Convert arbitrary key objects into a stable string key used for hashing/sorting.
    Returns None when no key is provided.
    """
    if key is None:
        return None
    if isinstance(key, (list, tuple)):
        return "|".join("" if part is None else str(part) for part in key)
    return str(key)


def merge_entries(
    existing_entries: List[Dict[str, Any]],
    new_entries: List[Dict[str, Any]],
    key_fn: Callable[[Dict[str, Any]], Any],
    *,
    sort: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Merge existing + new entries using a key function.

    - Preserves existing entry when content is identical (keeps older ingested_at).
    - Replaces entry when the text changed.
    - Adds brand new keys.
    - Carries forward existing entries whose keys were not present in the new set.

    Returns (merged_entries, stats).
    """

    existing_map: Dict[str, Dict[str, Any]] = {}
    for entry in existing_entries:
        key = _normalize_key(key_fn(entry))
        if key is not None:
            existing_map[key] = entry

    merged: List[Dict[str, Any]] = []
    seen_keys = set()
    added = updated = unchanged = 0

    for entry in new_entries:
        key = _normalize_key(key_fn(entry))
        if key is None:
            continue

        previous = existing_map.get(key)
        if previous is None:
            added += 1
            merged_entry = entry
        elif previous.get("text") == entry.get("text"):
            unchanged += 1
            merged_entry = previous
        else:
            updated += 1
            merged_entry = entry

        merged.append(merged_entry)
        seen_keys.add(key)

    # Carry forward entries that weren't part of this run (e.g., temporarily unreachable repos)
    retained = 0
    for key, entry in existing_map.items():
        if key not in seen_keys:
            merged.append(entry)
            retained += 1

    if sort:
        merged.sort(key=lambda e: _normalize_key(key_fn(e)) or "")

    stats = {
        "added": added,
        "updated": updated,
        "unchanged": unchanged,
        "retained": retained,
    }

    return merged, stats


# -----------------------------------------------------------------------------
# Run stats helpers
# -----------------------------------------------------------------------------
def _ensure_stats_dir():
    os.makedirs(os.path.dirname(INGESTION_STATS_PATH), exist_ok=True)


def load_ingestion_stats() -> Dict[str, Any]:
    """Load the JSON map of ingestion stats; return empty dict if missing/invalid."""
    if not os.path.exists(INGESTION_STATS_PATH):
        return {}
    try:
        with open(INGESTION_STATS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def record_ingestion_stats(job_name: str, stats: Dict[str, int], *, skipped: bool = False) -> None:
    """Persist stats for a job along with a timestamp."""
    _ensure_stats_dir()
    payload = load_ingestion_stats()
    payload[job_name] = {
        "timestamp": int(time.time()),
        "skipped": skipped,
        **stats,
    }
    with open(INGESTION_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def should_skip_ingestion(
    job_name: str,
    *,
    force_refresh: bool = False,
    skip_window_seconds: int = DEFAULT_SKIP_WINDOW_SECONDS,
) -> bool:
    """
    Decide whether to skip a job based on the last recorded stats.

    Policy: skip when the previous run recorded zero additions and zero updates
    and that run happened within `skip_window_seconds`, unless force_refresh is True.
    """
    if force_refresh:
        return False

    stats = load_ingestion_stats().get(job_name)
    if not stats:
        return False

    if stats.get("added", 0) > 0 or stats.get("updated", 0) > 0:
        return False

    ts = stats.get("timestamp")
    if ts is None or skip_window_seconds <= 0:
        return True

    age = time.time() - ts
    return age < skip_window_seconds
