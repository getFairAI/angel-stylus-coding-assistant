# Stylus Retrieval Backend

Retrieval-only backend for Arbitrum Stylus ecosystem research.

It indexes official docs, Stylus blog posts, and curated community repos, then returns
`context + references + agent_guidance` to downstream LLM consumers (MCP, IDE tools, web chat).

## Behavior Contract

- Returns references-first context for Stylus questions.
- Emits `agent_guidance` that sets `code_generation=disallowed`.
- Does not synthesize contract/application code.

## API

- `GET /health`
- `POST /stylus-chat`
- `POST /openrouter/chat/completions` (server-side OpenRouter proxy; keeps API key off the frontend)

Request:

```json
{ "prompt": "What tooling is current for Stylus testing?" }
```

Response (example):

```json
{
  "found": true,
  "context": "Top references:\n1. ...",
  "chunks_used": 25,
  "query_mode": "tooling",
  "agent_guidance": {
    "behavior": "references_first",
    "code_generation": "disallowed"
  },
  "references": [{ "title": "...", "url": "..." }]
}
```

OpenRouter proxy request (example):

```json
{
  "model": "openai/gpt-4o-mini",
  "messages": [{ "role": "user", "content": "What are the newest Stylus tools?" }],
  "tools": [],
  "tool_choice": "auto"
}
```

## Local Run

```bash
source .venv/bin/activate
python src/run_all_data_ingestions.py
uvicorn main:app --app-dir src --host 0.0.0.0 --port 8001
```

To enable the LLM proxy endpoint:

```bash
export OPENROUTER_API_KEY=...
```

## Environment

`.env.example` documents the runtime contract:

- `HOST` / `PORT` for API bind address
- `CORS_ORIGINS` for allowed frontend origins
- `OPENROUTER_API_KEY` for server-side LLM proxying

## QA

Repo-level checks:

```bash
python -m pytest -q
```

Workspace-level check (if using paired workspace scripts):

```bash
./scripts/qa-backend.sh setup-dev-env 8001
```

This runs:

- Python compile check
- `pytest` suite
- health probe
- `/stylus-chat` smoke request

## Docker

Run directly from this repo:

```bash
docker network create stylus-dev-net 2>/dev/null || true
docker compose up -d --build
```

Stop:

```bash
docker compose down --remove-orphans
```

Health checks:

```bash
curl http://localhost:8001/health
curl -X POST http://localhost:8001/openrouter/chat/completions \
  -H "content-type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}'
```

## Notes

- `src/run_all_data_ingestions.py` now rebuilds Chroma after ingestion.
- `src/debug_chroma_query.py` is a manual utility, not a pytest module.

## Additional Docs

- `docs/deployment-and-proxy.md` for architecture, security model, and deployment flow.
