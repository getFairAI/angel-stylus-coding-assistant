"""In-container ingestion scheduler.

Replaces the systemd timer / cron: runs the full Stylus ingestion pipeline on an
interval inside its own container. Because Chroma runs as a standalone server
(``CHROMA_SERVER_HOST``), the writes this job makes are immediately visible to
the live API — no restart needed.

Environment:
- ``INGEST_INTERVAL_SECONDS``  seconds between runs (default ``86400`` = 24h)
- ``RUN_ON_START``             run immediately on boot before the first sleep
                               (default ``true``)
- ``INGEST_FORCE_REFRESH``     pass --force-refresh semantics every run
                               (default ``false``)

The loop never exits on a pipeline error — it logs and waits for the next tick —
so a transient scraping/network failure can't kill the scheduler.
"""

from __future__ import annotations

import logging
import os
import time

from embeddings import get_chroma_client
from run_all_data_ingestions import run_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ingestion_scheduler")


def wait_for_chroma(timeout_seconds: int = 120, poll_seconds: int = 3) -> bool:
    """Block until the Chroma server answers a heartbeat, or timeout.

    Dependents only wait for Chroma to *start* (its image has no healthcheck), so
    poll here before the first ingestion run to avoid failing on a not-yet-ready
    server. Returns True if Chroma became reachable.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            get_chroma_client().heartbeat()
            logger.info("Chroma is reachable")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.info("Waiting for Chroma to be ready (%s)", type(exc).__name__)
            time.sleep(poll_seconds)
    logger.warning("Chroma not reachable after %ss; proceeding anyway", timeout_seconds)
    return False


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _interval_seconds() -> int:
    raw = os.getenv("INGEST_INTERVAL_SECONDS", "86400")
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid INGEST_INTERVAL_SECONDS=%r; using 86400", raw)
        return 86400
    return max(60, value)


def run_once() -> None:
    force = _env_bool("INGEST_FORCE_REFRESH", False)
    logger.info("Starting ingestion run (force_refresh=%s)", force)
    try:
        run_all(force_refresh=force)
        logger.info("Ingestion run complete")
    except Exception:  # noqa: BLE001 - never let one run kill the scheduler
        logger.exception("Ingestion run failed; will retry next interval")


def main() -> None:
    interval = _interval_seconds()
    run_on_start = _env_bool("RUN_ON_START", True)
    logger.info(
        "Ingestion scheduler up (interval=%ss, run_on_start=%s)",
        interval, run_on_start,
    )

    wait_for_chroma()

    if run_on_start:
        run_once()

    while True:
        logger.info("Sleeping %ss until next ingestion run", interval)
        time.sleep(interval)
        run_once()


if __name__ == "__main__":
    main()
