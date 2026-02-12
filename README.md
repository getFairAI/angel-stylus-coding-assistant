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

## Local Run

```bash
source .venv/bin/activate
python src/run_all_data_ingestions.py
uvicorn main:app --app-dir src --host 0.0.0.0 --port 8001
```

## QA

From workspace root:

```bash
./scripts/qa-backend.sh setup-dev-env 8001
```

This runs:

- Python compile check
- `pytest` suite
- health probe
- `/stylus-chat` smoke request

## Notes

- `src/run_all_data_ingestions.py` now rebuilds Chroma after ingestion.
- `src/debug_chroma_query.py` is a manual utility, not a pytest module.
