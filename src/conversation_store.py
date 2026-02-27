"""Append-only conversation capture utilities.

This module records multi-turn conversations for later review/retraining while
keeping the runtime dependency footprint light. Data is written to
`logs/conversation_events.jsonl` (or `LOG_DIR` override) so it can be shipped to
object storage or read for training exports. All functions are best-effort: IO
errors bubble up to callers so API handlers can return clear failures.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Dict, List, Optional


def _log_dir() -> str:
    path = os.getenv("LOG_DIR", "logs")
    os.makedirs(path, exist_ok=True)
    return path


def _conversation_log_path() -> str:
    return os.path.join(_log_dir(), "conversation_events.jsonl")


def _write_event(event: Dict) -> None:
    with open(_conversation_log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _normalize_rating(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if value not in (-1, 0, 1):
        raise ValueError("rating must be one of {-1, 0, 1} or omitted")
    return int(value)


def start_conversation(*, user_id: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
    """Open a new conversation session and return its id."""

    session_id = str(uuid.uuid4())
    event = {
        "type": "session_start",
        "session_id": session_id,
        "timestamp": int(time.time()),
    }
    if user_id:
        event["user_id"] = user_id
    if metadata:
        event["metadata"] = metadata

    _write_event(event)
    return session_id


def append_turn(
    *,
    session_id: str,
    prompt: str,
    response: str,
    rating: Optional[int] = None,
    skill: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> str:
    """Append a turn (user prompt + assistant response) to a conversation."""

    rating = _normalize_rating(rating)
    turn_id = str(uuid.uuid4())
    event = {
        "type": "turn",
        "session_id": session_id,
        "turn_id": turn_id,
        "timestamp": int(time.time()),
        "prompt": prompt,
        "response": response,
    }
    if rating is not None:
        event["rating"] = rating
    if skill:
        event["skill"] = skill
    if metadata:
        event["metadata"] = metadata

    _write_event(event)
    return turn_id


def _iter_events():
    path = _conversation_log_path()
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def get_conversation(session_id: str) -> Dict:
    """Return the full conversation thread for a session_id.

    Structure:
    {
        "session_id": "...",
        "user_id": "...",
        "metadata": {...},
        "started_at": 1234567890,
        "turns": [
            {"turn_id": "...", "prompt": "...", "response": "...", "rating": 1, ...},
            ...
        ],
    }
    Returns an empty dict if the session is unknown.
    """

    thread = {
        "session_id": session_id,
        "turns": [],
    }
    found = False

    for event in _iter_events() or []:
        if event.get("session_id") != session_id:
            continue
        etype = event.get("type")
        if etype == "session_start":
            found = True
            thread["started_at"] = event.get("timestamp")
            if event.get("user_id"):
                thread["user_id"] = event.get("user_id")
            if event.get("metadata"):
                thread["metadata"] = event.get("metadata")
        elif etype == "turn":
            found = True
            turn = {
                "turn_id": event.get("turn_id"),
                "prompt": event.get("prompt"),
                "response": event.get("response"),
                "timestamp": event.get("timestamp"),
            }
            if event.get("rating") is not None:
                turn["rating"] = event.get("rating")
            if event.get("skill"):
                turn["skill"] = event.get("skill")
            if event.get("metadata"):
                turn["metadata"] = event.get("metadata")
            thread["turns"].append(turn)

    return thread if found else {}


def export_conversations(*, min_rating: int = 1, since_timestamp: Optional[int] = None, max_sessions: int = 1000) -> List[Dict]:
    """Return conversations that contain at least one turn meeting the rating threshold.

    Used for training/export pipelines. Conversations are returned with only the
    qualifying turns (rating >= min_rating). The list is truncated to
    `max_sessions` to keep payloads reasonable for admin APIs.
    """

    if min_rating not in (-1, 0, 1):
        raise ValueError("min_rating must be one of {-1, 0, 1}")

    sessions: Dict[str, Dict] = {}
    qualifying_sessions = []

    for event in _iter_events() or []:
        etype = event.get("type")
        session_id = event.get("session_id")
        if not session_id:
            continue

        if etype == "session_start":
            sess = sessions.setdefault(session_id, {
                "session_id": session_id,
                "turns": [],
            })
            sess["started_at"] = event.get("timestamp")
            if event.get("user_id"):
                sess["user_id"] = event.get("user_id")
            if event.get("metadata"):
                sess["metadata"] = event.get("metadata")
            continue

        if etype != "turn":
            continue

        rating = event.get("rating")
        ts = event.get("timestamp")
        if rating is None or rating < min_rating:
            continue
        if since_timestamp is not None and (ts is None or ts < since_timestamp):
            continue

        sess = sessions.setdefault(session_id, {
            "session_id": session_id,
            "turns": [],
        })
        sess["turns"].append(
            {
                "turn_id": event.get("turn_id"),
                "prompt": event.get("prompt"),
                "response": event.get("response"),
                "rating": rating,
                "skill": event.get("skill"),
                "timestamp": ts,
                "metadata": event.get("metadata"),
            }
        )

    # Keep only sessions with qualifying turns, ordered by start time then fallback to first turn timestamp.
    for sess in sessions.values():
        if not sess.get("turns"):
            continue
        sess_turns = sess["turns"]
        sess_turns.sort(key=lambda t: t.get("timestamp") or 0)
        qualifying_sessions.append(sess)

    qualifying_sessions.sort(key=lambda s: s.get("started_at") or s["turns"][0].get("timestamp") or 0)
    return qualifying_sessions[:max_sessions]
