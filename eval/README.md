# Stylus RAG eval harness

Measures whether the retrieval backend actually helps, so skill/retrieval changes
are graded instead of guessed. Two independent metrics:

| Metric | Script | Needs |
|---|---|---|
| Retrieval quality | `run_eval.py` | a running backend (`requests` only) |
| Compile-pass | `compile_pass.py` | cargo + cargo-stylus + wasm32 target |

Both degrade gracefully: no backend → items reported as `errored`; no toolchain →
compile-pass reports `status: "skipped"` with a reason. Neither hangs a machine
that lacks the infra.

## Retrieval quality

```bash
# against a local Docker backend
python eval/run_eval.py --backend-url http://localhost:8001 --out eval/scorecard.json

# also grade context relevance with an LLM (wires src/rag_evaluation.py)
export OPENAI_API_KEY=...            # or OPENROUTER_API_KEY + EVAL_LLM_BASE_URL
python eval/run_eval.py --grade
```

Golden set: `golden_stylus.jsonl` — one JSON object per line:

```json
{"id": "erc20", "question": "Show me an ERC20 in Stylus.", "skill": "code_helper",
 "expect_found": true, "expect_source_contains": ["erc20"]}
```

- `skill`: `research` | `code_helper` | `porting` (maps to the registered backend id).
- `expect_found`: whether retrieval *should* return context (includes off-topic
  negatives that must return `found:false` to prove the distance gate is honest).
- `expect_source_contains`: lowercase substrings expected somewhere in the returned
  context/reference title/url/source. Drives `avg_source_recall`.

Scorecard metrics: `found_accuracy`, `positive_found_rate`, `negative_correct_rate`,
`avg_source_recall`, `avg_chunks_used`. Gate CI with `--min-found-accuracy 0.9`.

## Compile-pass

```bash
# smoke test the toolchain with a version-matched scaffold
python eval/compile_pass.py --baseline

# check curated full-contract fixtures under eval/code_fixtures/<name>/
python eval/compile_pass.py
```

Each fixture is a complete cargo project (`Cargo.toml` + `src/lib.rs`). The
`--baseline` mode scaffolds `cargo stylus new --minimal` at runtime and checks it,
so the baseline never drifts from the installed SDK version.

**CI**: provision rustup + `rustup target add wasm32-unknown-unknown` +
`cargo install cargo-stylus`, then run both scripts and publish the scorecards.
Start informational; promote to a gate once a baseline is established.

## Trust boundary

`compile_pass.py` runs the toolchain on **curated fixtures only**. Never wire it to
compile untrusted, user-submitted code on a shared backend.
