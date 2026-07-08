---
name: sift-stylus-deploy
description: Guide an Arbitrum Stylus contract through the full deploy lifecycle — check, deploy, on-chain activation via ArbWasm, Arbiscan verification, cache-manager registration, and the mandatory reactivation every 365 days — the gotcha-heavy path where teams most often get burned.
---

# Skill: sift-stylus-deploy

Use this skill when a user is ready to deploy a Stylus contract, or asks about
deployment, activation, verification, caching, or why a deployed contract stopped
being callable. Stylus deployment is not just "send bytecode" — there are activation
and lifetime steps that have no Solidity equivalent, and skipping them makes a
contract uncallable.

## When to use
- "Deploy my Stylus contract", "how do I activate", "verify on Arbiscan",
  "why did my contract stop working", "cache my contract".

Do not use for writing contract logic (`sift-stylus-code-helper`) or pre-deploy
compile checks (`sift-stylus-verify`).

## The deploy lifecycle (in order)
1. **Pre-flight check** — `cargo stylus check` must pass. It compiles to WASM and
   dry-runs activation; a failure here means the contract cannot be deployed. Confirm
   the compressed binary is within the **24KB** on-chain code-size limit.
2. **Deploy** — `cargo stylus deploy --endpoint <RPC> --private-key <KEY>` (or a
   keystore). This uploads the contract and reports gas/fees. Never hardcode or echo
   the private key; use env vars / keystores.
3. **Activation** — a freshly deployed Stylus contract **reverts until activated**
   via the `ArbWasm` precompile. `cargo stylus deploy` normally activates as part of
   deployment; if you deploy bytecode by other means, activation is a required
   separate step before the contract is callable.
4. **Verify on Arbiscan** — `cargo stylus verify` (and Arbiscan's Stylus flow) so the
   source is publicly checkable. See the `verifying-contracts` / `verifying-contracts-arbiscan`
   docs for the exact invocation.
5. **Cache for cheaper calls** — register hot contracts with the Stylus cache manager
   (`cargo stylus cache ...`) so activation is cached and calls are cheaper; see the
   `caching-contracts` doc.

## The lifetime gotcha — reactivation
- Stylus contracts must be **re-activated at least once every 365 days**, and again
  after any Stylus network upgrade. **An un-reactivated contract becomes uncallable.**
- When a previously-working contract starts reverting on every call, suspect an
  expired activation first. Reactivate via `cargo stylus` / the `ArbWasm` precompile.
- Proactively flag this lifetime requirement whenever helping someone deploy — it is
  the single most surprising operational difference from Solidity.

## Required behavior
- Retrieve the exact current commands/flags via `search_stylus_docs` before asserting
  them — cargo-stylus flags change across versions; do not invent them.
- Report each step's expected outcome and how to confirm it (tx hash, activation
  status, Arbiscan link).
- Treat secrets carefully: never print private keys; recommend env vars / keystores
  and testnet-first (Arbitrum Sepolia) before mainnet.

## Guardrails
- Do not claim a deploy succeeded without the activation step accounted for.
- Do not skip testnet. Recommend a Sepolia dry-run before mainnet spend.
