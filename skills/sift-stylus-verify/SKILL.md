---
name: sift-stylus-verify
description: Verify Stylus Rust contracts against the real toolchain — run cargo stylus check, export the ABI, and enforce the 24KB compressed-WASM limit — then interpret failures and drive fixes. Complements the PostToolUse verify hook for hosts/sessions without it.
---

# Skill: sift-stylus-verify

Use this skill after writing or changing Stylus contract code, and before suggesting
a deploy. A snippet that reads plausibly but does not compile (or does not fit the
size limit) is not done. This skill closes the `retrieve → generate → verify → fix`
loop locally, in the user's repo, using the installed toolchain — it does not send
code to any backend.

If the plugin's PostToolUse hook is active it already runs a fast `cargo check` after
each `.rs` edit; this skill covers the full gate and hosts where the hook is absent.

## When to use
- After generating or editing a Stylus contract, module, or storage layout.
- Before recommending deployment or activation.
- When a build/size/activation error needs interpreting.

Do not use for non-Stylus Rust or non-Rust code.

## Required workflow
1. **Type-check first (fast, offline):**
   `cargo check --target wasm32-unknown-unknown` (falls back to host `cargo check`
   if the wasm target is not installed — suggest `rustup target add wasm32-unknown-unknown`).
2. **Full gate before deploy:** `cargo stylus check`. This compiles to WASM and
   dry-runs activation against an RPC endpoint (`--endpoint`, default a local Nitro
   dev node). It reports whether the contract can be deployed and activated on-chain
   and why not if it cannot.
3. **Size:** confirm the Brotli-compressed WASM fits the **24KB** on-chain code-size
   limit (uncompressed must be ≤ 128KB). If over, apply size guidance (opt-level,
   `panic = "abort"`, strip, avoid heavy generics/formatting) before proceeding.
4. **ABI when integrating:** `cargo stylus export-abi` to get the Solidity ABI for
   callers/tests; verify it matches the intended external interface.
5. **Report** the exact command run and its result. On failure, show the relevant
   compiler/toolchain output and fix the root cause — do not paper over it.

## Interpreting common failures
- **`can't find crate for 'std'` / target errors** → wasm32 target missing:
  `rustup target add wasm32-unknown-unknown`.
- **Contract too large / exceeds 24KB** → optimize the binary (see size step); this
  is a hard on-chain limit, not a warning.
- **Activation/`ArbWasm` errors** → the check reached the activation dry-run; ensure
  the endpoint points at a working Stylus-enabled chain, and remember deployed
  contracts must be (re)activated and re-activated at least every 365 days.
- **Storage / `#[borrow]` / entrypoint macro errors** → structural; consult
  `sift-stylus-code-helper` / `search_stylus_docs` for the correct pattern rather
  than guessing macro syntax.

## Guardrails
- Never claim a contract compiles or is deploy-ready without an actual successful
  `cargo stylus check` (or at minimum a `cargo check`) — state which was run.
- Do not disable safety lints or use `unsafe` to force a build to pass.
- If the toolchain is unavailable in the environment, say so and give the exact
  commands the user should run locally instead of asserting success.

## Toolchain notes
- Requires `cargo` and `cargo-stylus` (`cargo install cargo-stylus`) and the
  `wasm32-unknown-unknown` target for accurate checks.
- This skill runs local commands only; it needs no hosted backend.
