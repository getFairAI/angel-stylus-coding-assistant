---
name: sift-stylus-research
description: Research Arbitrum Stylus topics using the backend MCP retrieval contract (`search_stylus_docs`) with references-first behavior and no synthesized contract code unless explicitly requested.
---

# Skill: sift-stylus-research

Use this skill when users ask technical Stylus questions and you need evidence-backed answers from your hosted Stylus retrieval MCP backend.

## What this skill does
- Calls `search_stylus_docs` to retrieve relevant Stylus context before answering.
- Prioritizes references and links over speculative explanation.
- Follows backend `agent_guidance` (`references_first`, `code_generation=disallowed`) by default.
- Reports retrieval limitations explicitly when context is missing.

## Trigger conditions
Use this skill for:
- Stylus SDK, tooling, deployment, verification, optimization, debugging, or ecosystem questions.
- Requests for current or practical Stylus resources.
- Questions that benefit from source-backed references.

Do not use this skill for non-Stylus topics.

## Required workflow
1. Call `search_stylus_docs` with the user's question (or a refined technical query).
2. Read `found`, `context`, `references`, `agent_guidance`, and `quality_signals` from the response.
3. If `found=false`, state that no relevant retrieval context was found and provide only conservative guidance.
4. If `found=true`, answer with references-first structure:
- Short answer.
- Key retrieved points.
- Direct links from `references`.
5. Respect `code_generation=disallowed` unless the user explicitly overrides this constraint.
6. Calibrate to `quality_signals`:
- `confidence=low` → state the uncertainty explicitly and offer a clearly-labeled best-bet.
- `time_sensitive=true` → warn that results may be outdated and cite `as_of_date`.
- Prefer sources with higher `evidence_profile.official_count` / `canonical_count`.
- You may use `recommended_answer_outline` as a scaffold (fill `direct_answer`, keep `why`/`links`/`caveats`).

## Output style
- Start with a concise direct answer.
- Include a `References` section with URLs from retrieval output.
- Mark uncertain statements as uncertain.
- Do not fabricate APIs, flags, or commands not present in retrieved material.

## Backend contract
See `references/mcp-tool-contract.md` for expected request/response behavior.

## Endpoint mapping (remote-first)
- Tool name: `search_stylus_docs`
- Backend endpoint: `POST /skills/sift-stylus-research/search`
- Expected deployment: hosted remote MCP/retrieval server managed by your team.
- Do not require local backend startup to use this skill.
- Local fallback for debugging only: `http://localhost:8001/skills/sift-stylus-research/search`
- Request body:
```json
{ "prompt": "<query>" }
```
