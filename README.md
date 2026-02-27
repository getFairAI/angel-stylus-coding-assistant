# Stylus Retrieval Backend

Retrieval-only backend for Arbitrum Stylus ecosystem research.

It indexes official docs, Stylus blog posts, and curated community repos, then returns
`context + references + agent_guidance` to downstream LLM consumers (MCP, IDE tools, web chat).

## Behavior Contract

- Returns references-first context for Stylus questions.
- Emits `agent_guidance` that sets `code_generation=disallowed`.
- Does not synthesize contract/application code.
- For porting-auditor requests with a GitHub target URL, performs static Solidity signal extraction on the target repository/files and injects those findings into the returned context.

## API

- `GET /health`
- `GET /skills`
- `POST /skills/{skill_id}/search`
- `POST /feedback` (thumbs up/down for a prompt + response, feeds logs and optional RAG booster)
- `POST /openrouter/chat/completions` (server-side OpenRouter proxy; keeps API key off the frontend)
- `POST /admin/auth` (exchange admin password for a short-lived bearer token)
- `GET /admin/logs/{request|ingestion|stats}/paginate` (paged log/text slice)
- `GET /admin/logs/{request|ingestion|stats}/stream` (stream entire log file)
- Conversation capture endpoints:
  - `POST /conversations/start` -> returns `session_id`
  - `POST /conversations/{session_id}/turn` -> append prompt/response (+optional rating/skill/metadata)
  - `GET /conversations/{session_id}` -> fetch thread
  - `GET /admin/conversations/export` (admin token) -> export rated turns for retraining
  - Shortcut: user-facing search endpoints (`/stylus-chat`, `/stylus-porting-audit`, `/skills/{id}/search`) auto-create a session on first call and return `X-Session-Id` response header; clients should resend that header to keep appending turns.
  - Rated turns (`rating=1`) are indexed into Chroma alongside feedback so retrieval can surface high-signal user-approved answers; hits from the same `X-Session-Id` are boosted during ranking.

Skill metadata contract (`GET /skills`):
- `system_prompt`: canonical prompt loaded from `skills/<id>/agents/openai.yaml#default_prompt`
- `prompt_source`: explicit source path for traceability
- `skill_doc_path`: path to the published skill instructions (`SKILL.md`)
- `behavior_hash`: SHA-256 fingerprint over the published skill behavior files

Consumers should use `system_prompt` from `/skills` (instead of frontend-local prompt text) to keep behavior consistent with published skills.

Compatibility aliases:
- `POST /stylus-chat` -> research skill
- `POST /stylus-porting-audit` -> porting auditor skill

Request:

```json
{ "prompt": "What tooling is current for Stylus testing?" }
```

Response (example):

```json
{
  "found": true,
  "as_of_date": "2026-02-25",
  "context": "Top references:\n1. ...",
  "chunks_used": 25,
  "query_mode": "tooling",
  "quality_signals": {
    "confidence": "high",
    "time_sensitive": false,
    "evidence_profile": {
      "official_count": 2,
      "community_count": 4,
      "canonical_count": 1,
      "unique_domains": 3
    }
  },
  "answer_contract": {
    "format": "direct_answer_why_links",
    "length_target_lines": "10-20",
    "uncertainty_mode": "state_uncertainty_plus_best_bet",
    "audience": "builder_engineer"
  },
  "recommended_answer_outline": {
    "direct_answer": "...",
    "why": ["..."],
    "links": [{ "title": "...", "url": "...", "source_type": "official" }],
    "caveats": []
  },
  "agent_guidance": {
    "behavior": "references_first",
    "code_generation": "disallowed"
  },
  "references": [{ "title": "...", "url": "..." }]
}
```

Note: the extended quality fields in this example are produced by
`/skills/sift-stylus-research/search`. Other skill endpoints may return only the core fields.

OpenRouter proxy request (example):

```json
{
  "model": "openai/gpt-4o-mini",
  "messages": [{ "role": "user", "content": "What are the newest Stylus tools?" }],
  "tools": [],
  "tool_choice": "auto"
}
```

## Feedback

- Endpoint: `POST /feedback`
- Payload: `prompt` (string), `response` (string), `rating` (-1 | 0 | 1), optional `skill` and `metadata` (dict).
- Side effects:
  - Appends every event to `logs/feedback_events.jsonl` (respects `LOG_DIR` env override).
  - Positive ratings (`1`) are also added to Chroma collection `stylus_feedback` for retrieval enrichment.
- Example:

```bash
curl -X POST http://localhost:8001/feedback \
  -H "content-type: application/json" \
  -d '{
    "prompt":"How do I test Stylus contracts?",
    "response":"Use cargo stylus test ...",
    "rating":1,
    "skill":"sift-stylus-research",
    "metadata":{"client":"cli"}
  }'
```

## Quickstart

```bash
# one-time setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# refresh data + rebuild Chroma
python src/run_all_data_ingestions.py

# serve the API
uvicorn main:app --app-dir src --host 0.0.0.0 --port 8001
```

Notes:
- Ingestion requires outbound internet access to GitHub, Arbitrum docs/blog, and OpenZeppelin docs.
- Logs land in `logs/ingestion_logs.log`; see `src/basic_logs.py`.
- Full pipeline details live in `src/ingestion/README.md`.

To enable the LLM proxy endpoint:

```bash
export OPENROUTER_API_KEY=...
```

Admin auth & protected logs:

- `POST /admin/auth` expects `{ "password": "..." }` and returns a signed bearer token with `expires_in` (seconds). Tokens are HMAC-SHA256 signed using `ADMIN_BEARER_TOKEN` and include an expiry set by `ADMIN_TOKEN_TTL_SECONDS` (default 3600).
- Store the password hash in env as base64(SHA256(password)). Quick helper:

```bash
python3 - <<'PY'
import hashlib, base64, getpass
p = getpass.getpass('Admin password: ')
print(base64.b64encode(hashlib.sha256(p.encode()).digest()).decode())
PY
```
- Log endpoints require `Authorization: Bearer <token>` and expose three sources:
  - `request` -> `logs/request_logs.log`
  - `ingestion` -> `logs/ingestion_logs.log`
  - `stats` -> `logs/ingestion_stats.json`

## Environment

`.env.example` documents the runtime contract:

- `HOST` / `PORT` for API bind address
- `CORS_ORIGINS` for allowed frontend origins
- `OPENROUTER_API_KEY` for server-side LLM proxying
- `GITHUB_TOKEN` for ingestion scraping
- `ADMIN_HASHED_PASSWORD` base64(SHA256(...)) used by `/admin/auth`
- `ADMIN_BEARER_TOKEN` signing secret for issued bearer tokens
- `ADMIN_TOKEN_TTL_SECONDS` (optional) validity window for issued admin tokens (default `3600`)

Runtime note:
- On startup, backend auto-loads missing env vars from `.env` candidates (current backend repo/worktree, workspace root, and sibling `backend`/`frontend` repos/worktrees) without overriding already-exported shell variables.

## QA

Repo-level checks:

```bash
python -m pytest
```

`pytest` now runs with coverage reporting and an `80%` fail-under gate for backend runtime modules (configured via `pytest.ini` + `.coveragerc`).

Workspace-level check (if using paired workspace scripts):

```bash
./scripts/qa-backend.sh setup-dev-env 8001
```

This runs:

- Python compile check
- `pytest` suite
- health probe
- `/skills/{skill_id}/search` smoke request

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

## Codex Skills

This repo contains Codex skills under `skills/`:

- `sift-stylus-porting-auditor`
- `sift-stylus-research`
- `sift-stylus-code-helper`

Install all from one CLI command:

```bash
npx sift-stylus \
  --repo getFairAI/angel-stylus-coding-assistant
```

Install one skill only:

```bash
npx sift-stylus \
  --repo getFairAI/angel-stylus-coding-assistant \
  --skills sift-stylus-research
```

Installer package source:

- `tools/sift-stylus-skills-installer/`

## Additional Docs

- `docs/deployment-and-proxy.md` for architecture, security model, and deployment flow.
