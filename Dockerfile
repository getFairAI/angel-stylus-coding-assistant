FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src ./src
COPY data ./data
RUN mkdir -p /app/chroma_db /app/logs

EXPOSE 8001

ENV HOST=0.0.0.0 \
    PORT=8001 \
    CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=2)" || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8001"]
