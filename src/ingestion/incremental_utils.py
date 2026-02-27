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
from typing import Any, Callable, Dict, List, Optional, Tuple


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
