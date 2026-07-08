---
name: sift-stylus-review
description: Review an Arbitrum Stylus Rust contract against a Stylus-specific security, gas, and size checklist — storage-trait correctness, no_std/host-I/O cost, unsafe memory, cross-contract reentrancy, and the 24KB code-size limit — and report findings with severity, not vague praise.
---

# Skill: sift-stylus-review

Use this skill when a user asks to review, audit, or harden a Stylus contract, or
before recommending a mainnet deploy. Apply the checklist below as an enforced pass
and report concrete findings with severity and a fix — never a generic "looks good."
This is a first-pass engineering review, not a substitute for a professional audit;
say so.

## When to use
- "Review / audit / check my Stylus contract", "is this safe to deploy",
  "why is this so expensive / so large".

## Review checklist
**Correctness & storage**
- Storage types use the SDK storage traits correctly (`sol_storage!` / `StorageType`);
  no raw-slot assumptions, no aliasing of the same slot from two fields.
- `#[borrow]` / inheritance composition is sound; no double-borrow of storage.
- The entrypoint and external method routing match the intended ABI
  (`cargo stylus export-abi`).

**Security**
- **Cross-contract reentrancy**: external calls into other contracts can re-enter —
  apply checks-effects-interactions; update storage before external calls. Stylus
  reentrancy protection is opt-in / feature-gated — confirm it is actually enabled if
  relied upon.
- No `unsafe` used to force compilation or do unchecked memory ops; unsafe that
  passes native tests can still be exploitable on-chain.
- Access control on privileged methods (owner/admin) is present and correct.
- Arithmetic: use checked/saturating math for value-bearing paths; no silent wraps.
- Untrusted input (calldata, addresses) validated before use.

**Gas / performance**
- Minimize host I/O (storage reads/writes, external calls) — these dominate cost in
  the Stylus ink model; cache in memory, batch writes, avoid rereads in loops.
- Avoid unnecessary heap allocation and heavy generics/formatting on hot paths.

**Size (hard limit)**
- Compressed WASM fits **24KB** (uncompressed ≤ 128KB). If near/over: size-optimized
  release profile (`opt-level="z"`, `lto`, `panic="abort"`, `strip`), trim
  dependencies, reduce monomorphization. This is a deploy blocker, not a nit.

## Output
- List findings as `severity — issue — why it matters — fix`, ordered
  critical → high → medium → low → nit.
- Ground claims in retrieved docs/examples (`search_stylus_docs` /
  `sift-stylus-code-helper`) rather than assertion; mark anything uncertain.
- End with an explicit deploy recommendation (block / fix-then-ship / ok for testnet)
  and the reminder that this is not a formal audit.

## Guardrails
- Do not invent SDK APIs, attributes, or feature flags — verify via retrieval.
- Do not provide exploitation payloads; this skill hardens contracts, it does not
  attack them.
