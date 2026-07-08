---
name: sift-stylus-scaffold
description: Scaffold a new Arbitrum Stylus Rust project the right way — cargo stylus new, a pinned rust-toolchain, a size-oriented release profile, and vetted crates — so the project is correct-by-default before any contract logic is written.
---

# Skill: sift-stylus-scaffold

Use this skill when a user starts a new Stylus contract or project, or asks how to
set one up. The goal is a project that is deployable-by-construction: the toolchain,
build profile, and dependencies are configured so `cargo stylus check` and the 24KB
size limit are satisfiable from day one.

Prefer the `/stylus-init` command when it is available — it drops the conventions
file and template flags directly. This skill is the manual/guided path and the
knowledge behind that command.

## When to use
- "Start a new Stylus project", "set up a Stylus contract", "how do I scaffold X".
- Before writing contract logic in an empty or non-Stylus repo.

## Required workflow
1. **Scaffold with the official tool** — do not hand-roll the layout:
   - `cargo stylus new <name>` (full template) or `cargo stylus new --minimal <name>`
     (bare entrypoint). This guarantees a version-matched, compilable starting point.
2. **Pin the toolchain** — add a `rust-toolchain.toml` so builds are reproducible and
   the wasm target is declared:
   ```toml
   [toolchain]
   channel = "1.83"            # match the SDK's supported Rust version
   targets = ["wasm32-unknown-unknown"]
   ```
3. **Add a size-oriented release profile** to `Cargo.toml` (contracts must fit 24KB
   Brotli-compressed / 128KB uncompressed):
   ```toml
   [profile.release]
   opt-level = "z"     # optimize for size
   lto = true
   codegen-units = 1
   panic = "abort"
   strip = true
   ```
4. **Use vetted crates, not ad-hoc ones:**
   - `stylus-sdk` (the SDK) and `alloy-primitives` for types.
   - `openzeppelin-stylus` for standard, audited implementations (ERC-20/721 etc.)
     instead of reimplementing token logic.
   - Keep the dependency graph lean — every dependency is code-size the 24KB limit
     has to absorb.
5. **Verify the empty scaffold builds** before adding logic: run `cargo stylus check`
   (see `sift-stylus-verify`). A scaffold that does not check is a setup bug, not a
   code bug.

## Guardrails
- Never invent `cargo stylus` flags or `Cargo.toml` keys — confirm via
  `search_stylus_docs` / `sift-stylus-code-helper` when unsure.
- Do not add heavy dependencies (formatting, large generic frameworks) casually; call
  out their code-size cost.
- Match the pinned Rust channel to what the installed `stylus-sdk` version supports;
  if unknown, retrieve it rather than guessing.

## Handoff
- After scaffolding, use `sift-stylus-code-helper` for contract logic,
  `sift-stylus-verify` before deploy, and `sift-stylus-deploy` to ship.
