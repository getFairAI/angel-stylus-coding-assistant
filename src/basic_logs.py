import os
from datetime import datetime

LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

INGESTION_LOG_FILE = os.path.join(LOG_DIR, "ingestion_logs.log")
REQUEST_LOG_FILE = os.path.join(LOG_DIR, "request_logs.log")


def _write_log(file_path: str, message: str):
    timestamp = datetime.now().isoformat()
    line = f"{timestamp} - {message}\n"

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(line)


# -----------------------------
# Ingestion / pipeline logs
# -----------------------------
def write_ingestion_log(message: str):
    """
    Used by ingestion scripts, orchestrators, cron jobs, etc.
    """
    _write_log(INGESTION_LOG_FILE, message)


# -----------------------------
# API / request logs
# -----------------------------
def write_request_log(message: str):
    """
    Used by FastAPI / MCP / request handlers.
    """
    _write_log(REQUEST_LOG_FILE, message)
