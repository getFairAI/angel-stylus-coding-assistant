# Deployment and LLM Proxy

## Purpose

This backend now provides two responsibilities:

1. Skill-scoped Stylus retrieval (`/skills/{skill_id}/search`) with references-first context.
2. Server-side OpenRouter proxy (`/openrouter/chat/completions`) so frontend clients never hold provider API keys.

## Request Flow

1. Browser sends request to frontend (`/openrouter/chat/completions`).
2. Frontend reverse-proxy forwards to backend endpoint.
3. Backend injects `OPENROUTER_API_KEY` from server env and calls OpenRouter.
4. Backend returns upstream response/status to caller.

## Security Model

- `OPENROUTER_API_KEY` is read only on backend runtime.
- Frontend build/runtime does not require `VITE_OPENROUTER_API_KEY`.
- If key is missing, backend returns `503` with explicit message.
- Upstream connectivity failures return `502`.

## Endpoints

- `GET /health`
- `GET /skills`
- `POST /skills/{skill_id}/search`
- `POST /openrouter/chat/completions`

Compatibility aliases:
- `POST /stylus-chat` -> research skill
- `POST /stylus-porting-audit` -> porting auditor skill

## Environment Variables

- `HOST` (default `0.0.0.0`)
- `PORT` (default `8001`)
- `CORS_ORIGINS` (comma-separated)
- `OPENROUTER_API_KEY` (required for LLM proxy)

## Docker Runtime

`docker-compose.yml` expects an external network:

- `stylus-dev-net`

Container behavior:

- Exposes port `8001`
- Mounts `./chroma_db`, `./logs`, `./data`
- Healthcheck probes `http://127.0.0.1:8001/health`

## Validation Checklist

1. `python -m pytest -q`
2. `docker compose up -d --build`
3. `curl http://localhost:8001/health`
4. `curl -X POST http://localhost:8001/openrouter/chat/completions ...`

Expected LLM-proxy behavior:

- With missing key: `503` and `OPENROUTER_API_KEY is not configured on the backend.`
- With valid key: `200` with upstream completion payload.
