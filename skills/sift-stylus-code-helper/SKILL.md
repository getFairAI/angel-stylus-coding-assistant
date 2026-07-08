---
name: sift-stylus-code-helper
description: Provide small, practical Stylus code snippets and examples using the backend MCP retrieval contract (search_stylus_code) with sources-first behavior, plus brief explanations and safe “how to adapt” guidance.
---

# Skill: stylus-code-helper

Use this skill when users ask for Stylus code examples/snippets, patterns, or “how do I implement X” guidance, and you should respond with source-backed snippets (or clearly-labeled illustrative snippets when sources don’t contain exact code).

This is the “code-enabled” companion to sift-stylus-research.

---

## What this skill does

- Calls `search_stylus_code` to retrieve relevant Stylus context before writing snippets.
- Produces short, composable code examples (not full contracts unless explicitly requested).
- Prioritizes references-first outputs:
  - Snippet(s) that map to retrieved sources
  - Brief explanation
  - Clear adaptation notes
  - Direct links from retrieval `references`
- Explicitly reports when the backend retrieval lacks the needed detail.

---

## Trigger conditions

### Use this skill for:

- “Show me an example of …” (storage, calls, ABI, events/logs, precompiles, host I/O)
- “How do I do X in Stylus?” where a snippet helps (deployment setup, invocation patterns, testing harness shape)
- “Convert/translate this Solidity idea into Stylus (Rust)” at the pattern level
- Common patterns:
  - Access control
  - Ownership
  - Pausing
  - Mapping-like storage
  - Error handling
  - Reentrancy-safe structure (pattern guidance)
  - Gas/perf tips with code-level adjustments

### Do not use this skill for:

- Non-Stylus topics
- Requests that clearly require full project scaffolding or multi-file repos (unless the user explicitly asks for a larger artifact)
- Requests to produce exploits, malware, or instructions to break systems

---

## Required workflow

### 1. Retrieve first

Call `search_stylus_code` with the user’s question (or a refined technical query).

Prefer queries that name:
- The concept
- “Stylus”
- The likely API surface  

Example queries:
- “Stylus storage Rust example”
- “Stylus host call pattern”
- “Stylus ABI encoding”

---

### 2. Read the response fields

- `found`
- `context`
- `references`
- `agent_guidance`
- `quality_signals` (`confidence`, `time_sensitive`, `evidence_profile`)
- `as_of_date`

Calibrate to `quality_signals`:
- `confidence=low` → do not fabricate APIs/flags; label snippets illustrative and note what is missing.
- `time_sensitive=true` → verify against the latest release/changelog and cite `as_of_date`.
- Prefer sources with higher `evidence_profile.official_count` / `canonical_count`.

---

### 3. If `found=false`

- State that no relevant retrieval context was found.
- Provide only conservative guidance:
  - Either ask the user for more context
  - Or give a minimal illustrative snippet clearly labeled:

    > **Illustrative (not source-backed)**

- Include a **Retrieval limitation** note.

---

### 4. If `found=true`

Produce a references-first answer:

- **Direct answer** (1–3 sentences)
- **Snippet(s)** (small, focused, runnable fragments where possible)
- **Explanation** (why it works + key gotchas)
- **Adaptation notes** (what to change for their use case)
- **References** (URLs from `references`)

---

### 5. Respect backend guidance

- Follow `agent_guidance` defaults (e.g., `references_first`).
- If backend says code generation is restricted, obey it and only describe changes unless the user explicitly asks to override.

---

## Output style

- Start with a concise direct answer.
- Provide one primary snippet and optionally 1–2 variants (e.g., “minimal” vs “production-ish”), but keep each snippet short.
- Prefer:
  - Comments in code to explain key lines
  - Minimal dependencies
  - Drop-in fragments over theoretical pseudo-code
- Mark uncertainty clearly:
  - If the retrieved material doesn’t specify a function signature/API, say so.
- Never fabricate APIs, flags, or commands not present in retrieved material.

---

## Code scope rules

- Default: snippets and small examples, not full contracts.
- Full contract generation is allowed only if:
  - The user explicitly requests it, and
  - Retrieval context supports the structure sufficiently (or you clearly mark un-sourced parts).

If the user requests a large scaffold:
- Propose an outline and the critical files.
- Then generate only the minimal core code they asked for.

---

## Snippet quality guidelines

- Prefer correctness and clarity over cleverness.
- Show safe defaults:
  - Input validation
  - Clear error handling
  - Avoid footguns (e.g., confusing storage layout changes)
- Include:
  - Expected function inputs/outputs
  - Any assumptions (e.g., “this assumes you have X imported / feature flag enabled”)

If relevant, include a short **Testing note** section with how to exercise the snippet (only if sources mention it or it’s generic and safe).

---

## Safety and policy constraints

- Refuse requests that aim to exploit vulnerabilities or bypass security.
- Do not provide instructions to steal keys, drain contracts, or create malicious payloads.
- When discussing optimization:
  - Avoid unsafe micro-optimizations that risk correctness unless clearly labeled and source-supported.

---

## Backend contract

- Tool name: `search_stylus_code`
- Backend endpoint: `POST /skills/sift-stylus-code-helper/search`
- Expected deployment: hosted remote MCP/retrieval server managed by your team.
- Local fallback (debugging only):  
  `http://localhost:8001/skills/sift-stylus-code-helper/search`

### Request body

```json
{ "prompt": "<query>" }
```

---

## Suggested `agent_guidance` defaults

When configuring the backend for this skill:

- `references_first: true`
- `code_generation: allowed`
- `max_snippet_size_lines: 80`
- `full_contracts: on_request_only`
- `uncertainty_marking: required`

---

## Example response skeleton (for the assistant)

**Answer:**  
<1–3 sentences>

**Snippet:**
```rust
// focused example
```

**Explanation:**
- …

**Adaptation notes:**
- …

**References:**
- <URLs from retrieval output>