# Implementation Plan: Best-in-Class Stylus Agent as a Claude Code Plugin

Branch: `feat/stylus-claude-code-plugin`

## Context

Today the repo ("Sifter") is a **references-first, retrieval-only RAG backend for Arbitrum Stylus**: ChromaDB + Ollama `mxbai-embed-large`, 10 ingestion jobs, and three skills (`sift-stylus-research`, `sift-stylus-code-helper`, `sift-stylus-porting-auditor`) distributed **only to Codex** (`npx sift-stylus` → `~/.codex/skills`). The MCP "server" is a hosted external wrapper over the FastAPI backend; there is no MCP server code in-repo.

It is effectively a well-prompted search box. For it to be **meaningfully useful to people writing Stylus code**, it needs to close the coding loop (`retrieve → generate → verify → fix`), encode Stylus workflow expertise as skills, ship correct-by-default project scaffolding, and be measured so quality doesn't regress.

**Decisions locked in (by the user):**
- **Scope:** best-in-class *Stylus* (not "all Arbitrum"). No Orbit/Nitro/bridging/TS-SDK ingestion.
- **Target host:** a **Claude Code plugin** (skills + hooks + MCP + a `/stylus-init` command).
- Skill-suite expansion and `cargo stylus check` integration are agreed in principle; this plan gives them their concrete shape.

**Intended outcome:** a Claude Code plugin that, in any Stylus project, grounds answers in current docs (hosted MCP), verifies generated code against the real toolchain (local hooks), scaffolds correct projects, and is regression-guarded by an eval harness.

---

## Architecture (five layers)

| Layer | What | Where it runs | Status |
|---|---|---|---|
| 1. Grounding (RAG) | Current docs/code, cited | Hosted backend + MCP | ✅ have |
| 2. Skills | Stylus idioms, gotchas, lifecycle checklists | Plugin (`skills/`) | 🟡 3 → 7 |
| 3. Verification | `cargo stylus check`/size/abi | **User's repo** (hooks + skill) | ❌ build |
| 4. Scaffolding + hooks | Correct-by-default projects | Plugin (`commands/`, `hooks/`) | ❌ build |
| 5. Distribution | Claude Code plugin | `.claude-plugin/` | ❌ build |

**Key design call — verification runs locally, never server-side.** Compiling user code on the backend is an RCE surface and forces a Rust+WASM toolchain into the container. Instead: a **PostToolUse hook** runs `cargo stylus check` in the user's repo and feeds results back to the agent; a **`stylus-verify` skill** covers hosts without hooks; a **sandboxed CI compile-pass harness** (separate trust boundary) exists only for eval.

---

## Plugin structure (reuses the existing `skills/` dir as the plugin root)

The repo root becomes the plugin root. The existing `skills/` folder is consumed directly by Claude Code (it reads each `SKILL.md`; `agents/openai.yaml` and `references/` are harmless extras — Codex keeps working unchanged). New files:

```
.claude-plugin/plugin.json        # manifest
.mcp.json                          # hosted MCP: search_stylus_docs, search_stylus_code, porting audit
commands/stylus-init.md            # /stylus-init scaffolder
hooks/hooks.json                   # PostToolUse cargo stylus check
scripts/stylus-check-hook.sh       # the hook body (portable, no-op if cargo-stylus absent)
skills/
  sift-stylus-research/            # existing (reused)
  sift-stylus-code-helper/         # existing (reused)
  sift-stylus-porting-auditor/     # existing (reused)
  sift-stylus-verify/SKILL.md      # NEW
  sift-stylus-scaffold/SKILL.md    # NEW
  sift-stylus-deploy/SKILL.md      # NEW
  sift-stylus-review/SKILL.md      # NEW
assets/stylus-project-template/    # CLAUDE.md + Cargo profile flags dropped by /stylus-init
```

`.mcp.json` points at the **hosted** MCP wrapper (so users never run Ollama/Chroma locally). It must expose the three existing tools; the porting tool maps to the backend's `analyze_contract_target()` endpoint.

---

## Phase 0 — Measurement + drift fixes (do first; cheap, unblocks everything)

**0a. Fix integration drift** (exact edits):
- `skills/sift-stylus-code-helper/SKILL.md:171` and `:174` — endpoint `POST /skills/stylus-code-helper/search` → `POST /skills/sift-stylus-code-helper/search` (registry id is `sift-stylus-code-helper`, `src/skill_registry.py:18`, search path template `/skills/{skill_id}/search` at `:321`). Currently 404s.
- `skills/sift-stylus-research/references/mcp-tool-contract.md:1,9` — tool name `stylus_search_code` → `search_stylus_code` to match `skills/sift-stylus-code-helper/SKILL.md:170`. Pick one canonical name (recommend `search_stylus_code`) and grep the repo to ensure the hosted MCP uses it.
- Add a test asserting each skill's documented endpoint matches `run_skill_search`'s registered path (extend `tests/test_client_parity.py`).

**0b. Wire the orphaned eval harness** (`src/rag_evaluation.py` is imported nowhere):
- Add `eval/golden_stylus.jsonl` — 30–50 real Stylus Q&A (draw from ingested docs + GitHub issues; cover storage traits, `no_std`, host I/O, ABI, events, `cargo stylus` flow).
- Add `eval/run_eval.py` that runs each query through `retrieve_stylus_context()` and scores with the three existing graders (`eval_context_relevance`, `eval_response_groundness`, `eval_response_relevancy`).
- Add a **compile-pass metric**: for `code-helper` outputs, drop snippets into a minimal `cargo stylus` project in a sandbox and run `cargo stylus check`; record pass rate. Reuse the porting snapshot cases in `tests/test_porting_baseline_snapshots.py` as the porting-stability metric.
- Emit a scorecard artifact; gate in CI as informational first, then as a threshold.

---

## Phase 1 — Close the verification loop (highest single quality jump)

**1a. `hooks/hooks.json` + `scripts/stylus-check-hook.sh`:**
- PostToolUse matcher on `Edit|Write` where the path matches `*.rs`.
- Hook detects a Stylus project (`cargo-stylus` installed + `Cargo.toml` with `stylus-sdk`), runs `cargo stylus check`, and on failure returns the compiler output as hook feedback so the agent self-corrects; also reports compressed WASM size vs the **24KB** limit. No-ops cleanly (exit 0, informational note) when `cargo-stylus` is absent so non-Stylus edits aren't blocked.
- Keep it fast/non-blocking where possible; make full `check` opt-in via env if it's slow on large contracts.

**1b. `skills/sift-stylus-verify/SKILL.md`:** teaches the agent *when/how* to run `cargo stylus check`, `cargo stylus export-abi`, and size checks, and how to read failures — so verification still happens in hosts/sessions without the hook. Cross-links `sift-stylus-code-helper`.

---

## Phase 2 — Skill suite + scaffolding (the lifecycle)

New skills (deterministic, cheap, this is where "expert" lives — encode gotchas as enforced checklists, not prose):
- **`sift-stylus-scaffold`** — `cargo stylus new`, pinned `rust-toolchain`, size-oriented `Cargo.toml`/profile flags, recommended crates (OpenZeppelin-Stylus, alloy).
- **`sift-stylus-deploy`** — the gotcha-heavy path: `check → deploy → activation → Arbiscan verify → caching → reactivation every 365 days`.
- **`sift-stylus-review`** — security/gas/size checklist: storage-trait misuse, `no_std` pitfalls, host-I/O cost, unsafe memory, reentrancy across EVM calls.
- (`sift-stylus-verify` from Phase 1 completes the set alongside the existing research / code-helper / porting-auditor.)

**Scaffolding command** — `commands/stylus-init.md` (`/stylus-init`): drops `assets/stylus-project-template/` into the project — a `CLAUDE.md` with Stylus conventions (the 24KB limit, reactivation, `cargo stylus check` before deploy, storage model) + Cargo profile flags. This is the "correct-by-default project setup."

**Plugin manifest** — `.claude-plugin/plugin.json` (name, version, description, and declared `commands`/`skills`/`hooks`/`mcpServers` if not auto-discovered) and `.mcp.json` for the hosted MCP. Add a plugin marketplace entry (or document local install) so users can `plugin install`.

---

## Phase 3 — Retrieval quality (measured against Phase 0's eval set)

- Add **hybrid retrieval (BM25 keyword + dense vector)** on at least the code collections (`data_stylus_framework_ingestion`, `data_awesome_stylus_code_ingestion` outputs). Candidate: a keyword pre-filter/union merged into `get_chroma_documents()` (`src/chroma_query.py:46`) before the `score_hit()` re-rank (`src/retrieve_chroma_docs.py:293`).
- Consider code-aware chunking for Rust files (respect `fn`/`impl`/`mod` boundaries) in `recursive_chunk` (`src/fill_chroma.py`).
- **Ship only if the eval scorecard improves** — no faith-based changes.

---

## Files touched (summary)

- New: `.claude-plugin/plugin.json`, `.mcp.json`, `commands/stylus-init.md`, `hooks/hooks.json`, `scripts/stylus-check-hook.sh`, `assets/stylus-project-template/*`, `skills/sift-stylus-{verify,scaffold,deploy,review}/SKILL.md`, `eval/golden_stylus.jsonl`, `eval/run_eval.py`.
- Edit: `skills/sift-stylus-code-helper/SKILL.md` (endpoint), `skills/sift-stylus-research/references/mcp-tool-contract.md` (tool name), `tests/test_client_parity.py` (drift assertion), CI workflow under `.github/workflows/` (eval scorecard), README (plugin install + Claude Code section).
- Reused unchanged: existing three `skills/*` dirs, the whole `src/` backend and ingestion, the Codex installer (`tools/sift-stylus-skills-installer/`).

---

## Verification (how we prove each phase works)

- **P0 drift:** `uv run pytest tests/test_client_parity.py` passes; manual `curl -XPOST $HOST/skills/sift-stylus-code-helper/search -d '{"prompt":"erc20"}'` returns 200 (not 404).
- **P0 eval:** `python eval/run_eval.py` emits a scorecard; grader scores and compile-pass rate recorded as the baseline.
- **P1 verify loop:** in a scratch Stylus project, have the agent write a deliberately non-compiling contract; confirm the PostToolUse hook surfaces the `cargo stylus check` error and the agent fixes it. Confirm size is reported vs 24KB. Confirm a `.py`/non-Stylus edit is a clean no-op.
- **P2 plugin:** `plugin install` the branch locally; confirm all 7 skills load (`/help` or skill listing), `/stylus-init` scaffolds the template, and the hosted MCP tools (`search_stylus_docs`, `search_stylus_code`) are callable.
- **P3 retrieval:** re-run `eval/run_eval.py`; hybrid retrieval must beat the P0 baseline on context-relevance and compile-pass before merge.
- **Regression gate:** the full existing suite stays green (`uv run pytest`, 80% coverage floor) throughout.

---

## Open follow-ups (not blocking)

- The hosted MCP wrapper is external/undocumented in-repo — confirm it exposes a porting-audit tool (not just the two search tools) so `sift-stylus-porting-auditor` works from Claude Code.
- Decide whether plugin skills stay single-source in `skills/` (recommended) or diverge from the Codex `openai.yaml` prompts over time.
