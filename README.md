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
- `POST /platform-feedback` (captures general platform feedback entries and logs them for later review)
- `POST /openrouter/chat/completions` (server-side OpenRouter proxy; keeps API key off the frontend)
- `GET /admin/platform-feedback` (requires admin token; streams the most recent platform feedback lines)
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

- Platform feedback: `POST /platform-feedback` lets clients submit free-form messages, optional categories, and metadata; entries append to `logs/platform_feedback.jsonl` (override path with `PLATFORM_FEEDBACK_LOG_PATH`). Administrators can fetch those entries via `GET /admin/platform-feedback` when authenticated.

## Quickstart

```bash
# one-time setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# embeddings backend: ollama serving mxbai-embed-large (1024-dim, cosine)
ollama serve &          # or run the ollama app / container
ollama pull mxbai-embed-large

# refresh data + (incrementally) rebuild Chroma
python src/run_all_data_ingestions.py

# serve the API
uvicorn main:app --app-dir src --host 0.0.0.0 --port 8001
```

Notes:
- Embeddings are generated by a local **ollama** server (`mxbai-embed-large`). Index and query
  share the same embedding function (`src/embeddings.py`) so the vector spaces cannot drift.
  Configure with `OLLAMA_HOST` / `EMBEDDING_MODEL`. The API logs a clear warning at startup if the
  server is unreachable or the model is not pulled.
- Ingestion is **incremental**: chunk ids are content-derived, so re-running only embeds new/changed
  chunks and deletes removed ones. The collection is never emptied, so the live API keeps serving
  results during a rebuild (no restart needed). Changing `EMBEDDING_MODEL` triggers a one-time full
  rebuild of the collection.
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
- `OLLAMA_HOST` embeddings backend URL (default `http://localhost:11434`)
- `EMBEDDING_MODEL` ollama embedding model (default `mxbai-embed-large`)
- `CHROMA_SERVER_HOST` / `CHROMA_SERVER_PORT` — when set, connect to a standalone Chroma server (Docker); shared by API + ingestion so writes are seen live
- `CHROMA_PATH` embedded-store directory (default `./chroma_db`), used only when `CHROMA_SERVER_HOST` is unset; honored by index, query, and feedback store
- `INGEST_INTERVAL_SECONDS` / `RUN_ON_START` / `INGEST_FORCE_REFRESH` — ingestion scheduler cadence (Docker `ingestion` service)
- `CHROMA_MAX_DISTANCE` (optional) cosine-distance cutoff; hits farther than this are dropped so the API can report `found:false` honestly. Empirically, `mxbai-embed-large` puts relevant Stylus chunks at ~0.2–0.5 and off-topic ones at ~0.65+, so `0.6` is a good starting value (leave unset to disable filtering)
- `CHUNK_MAX_CHARS` / `CHUNK_OVERLAP` (optional) chunk sizing for ingestion (defaults `800` / `100`)
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

`docker compose up` brings up the whole stack — no systemd timers or services needed:

| Service | Role |
| --- | --- |
| `chroma` | Standalone Chroma vector store (shared by API + ingestion) |
| `stylus-backend` | The FastAPI retrieval API (port 8001) |
| `ingestion` | Scheduled ingestion — runs on start, then every `INGEST_INTERVAL_SECONDS` |

**ollama runs on the host, not in compose.** Ensure it listens on all interfaces
(`OLLAMA_HOST=0.0.0.0:11434` in its service) and the model is pulled
(`ollama pull mxbai-embed-large`). The containers reach it via
`host.docker.internal` (wired with `extra_hosts`); override with `OLLAMA_HOST` if needed.

```bash
docker network create stylus-dev-net 2>/dev/null || true
docker compose up -d --build
```

Because Chroma runs as its own server, the `ingestion` container's writes are
**immediately visible to the live API** — no restart, no per-process cache staleness.
On first boot the initial ingestion run must complete before the corpus is populated
(the API returns `found:false` until then). Ensure the host ollama has the embedding
model pulled beforehand.

Stop:

```bash
docker compose down --remove-orphans
```

Trigger an ingestion run manually (in addition to the schedule):

```bash
docker compose exec ingestion python src/run_all_data_ingestions.py
```

Health checks:

```bash
curl http://localhost:8001/health
curl http://localhost:8000/api/v2/heartbeat   # chroma
curl -X POST http://localhost:8001/openrouter/chat/completions \
  -H "content-type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}'
```

Relevant env (see `docker-compose.yml` for defaults):
`CHROMA_SERVER_HOST`/`CHROMA_SERVER_PORT` (API+ingestion → chroma), `CHROMA_IMAGE_TAG`
(match your `chromadb` client minor version, default `1.5.9`), `INGEST_INTERVAL_SECONDS`,
`RUN_ON_START`, `INGEST_FORCE_REFRESH`.

## Notes

- `src/run_all_data_ingestions.py` incrementally upserts into Chroma after ingestion
  (`run_all()` is importable; `src/ingestion_scheduler.py` runs it on a loop in Docker).
- Deploying without Docker: set `CHROMA_SERVER_HOST` to a running Chroma server, or leave it
  unset to use an embedded on-disk store (`CHROMA_PATH`) — note that with the embedded store a
  long-running API won't see a separate ingestion process's writes until it restarts.
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
