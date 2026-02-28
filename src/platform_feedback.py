"""Simple platform feedback logging backed by a JSONL file."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional

LOG_DIR_ENV = "LOG_DIR"
PLATFORM_FEEDBACK_LOG_ENV = "PLATFORM_FEEDBACK_LOG_PATH"
DEFAULT_LOG_FILE = "platform_feedback.jsonl"


def _log_dir() -> str:
    path = os.getenv(LOG_DIR_ENV, "logs")
    os.makedirs(path, exist_ok=True)
    return path


def _platform_feedback_log_path() -> str:
    override = os.getenv(PLATFORM_FEEDBACK_LOG_ENV)
    if override:
        dir_path = os.path.dirname(override)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        return override
    return os.path.join(_log_dir(), DEFAULT_LOG_FILE)


def _write_event(event: Dict[str, Any]) -> None:
    with open(_platform_feedback_log_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def _iter_events() -> Iterator[Dict[str, Any]]:
    path = _platform_feedback_log_path()
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def record_platform_feedback(
    *,
    message: str,
    source: Optional[str] = None,
) -> str:
    feedback_id = str(uuid.uuid4())
    event: Dict[str, Any] = {
        "id": feedback_id,
        "timestamp": int(time.time()),
        "message": message,
    }
    if source:
        event["source"] = source

    _write_event(event)
    return feedback_id


def list_platform_feedback_events(*, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    if limit <= 0:
        raise ValueError("limit must be > 0")
    if offset < 0:
        raise ValueError("offset must be >= 0")

    results: List[Dict[str, Any]] = []
    skipped = 0
    for event in _iter_events():
        if skipped < offset:
            skipped += 1
            continue
        results.append(event)
        if len(results) >= limit:
            break
    return results
