FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# git is required at runtime by the Porting Auditor: it clones target repos
# (src/contract_analysis.py) to run static Solidity signal extraction.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Chromium + OS deps for the playwright-based ingestion jobs (Stylus course,
# Stylus Saturdays). --with-deps installs the required apt libraries.
RUN playwright install --with-deps chromium

COPY src ./src
# skills/ holds the Porting Auditor's extractor script, referenced at runtime by
# src/contract_analysis.py (EXTRACTOR_SCRIPT). It must be present in the image.
COPY skills ./skills
# `data/` is gitignored and provided at runtime via a bind mount (see
# docker-compose.yml), so it is not COPYed here — a clean checkout has no data/
# dir and COPY would fail the build. Just ensure the mount points exist.
RUN mkdir -p /app/chroma_db /app/logs /app/data

EXPOSE 8001

ENV HOST=0.0.0.0 \
    PORT=8001 \
    CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=2)" || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8001"]
