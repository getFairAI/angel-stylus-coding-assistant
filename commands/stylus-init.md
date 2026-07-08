---
description: Set up correct-by-default Arbitrum Stylus project conventions, toolchain, and size-oriented build profile in the current project.
argument-hint: "[project-name]"
allowed-tools: Bash(cargo:*), Bash(rustup:*), Bash(cp:*), Bash(ls:*), Bash(cat:*), Read, Write, Edit
---

Initialize this project for Arbitrum Stylus development so it is deployable-by-construction.

Target: `$ARGUMENTS` (optional project name/path; default to the current directory).

Do the following, explaining each step and asking before any destructive change:

1. **Detect state.** Check whether the target already has a `Cargo.toml` with
   `stylus-sdk`. If it is an empty/new project, scaffold one with
   `cargo stylus new $ARGUMENTS` (or `cargo stylus new --minimal $ARGUMENTS`); if a
   Stylus project already exists, work in place and do not overwrite source.

2. **Drop the conventions file.** Copy
   `${CLAUDE_PLUGIN_ROOT}/assets/stylus-project-template/CLAUDE.md` into the project
   root as `CLAUDE.md` (if one exists, show the diff and merge rather than clobber).

3. **Pin the toolchain.** Add `rust-toolchain.toml` from
   `${CLAUDE_PLUGIN_ROOT}/assets/stylus-project-template/rust-toolchain.toml` if
   absent, and ensure the wasm target: `rustup target add wasm32-unknown-unknown`.
   Align the pinned Rust `channel` with the installed `stylus-sdk` version.

4. **Add the size profile.** Merge the `[profile.release]` block from
   `${CLAUDE_PLUGIN_ROOT}/assets/stylus-project-template/cargo-release-profile.toml`
   into the project's `Cargo.toml` if it is not already size-optimized.

5. **Verify.** Run `cargo stylus check` (or the fast
   `cargo check --target wasm32-unknown-unknown`) and report the result plus the
   compressed WASM size against the 24KB limit. If it fails, fix the setup before
   finishing.

Then summarize what changed and point to the `sift-stylus-scaffold`,
`sift-stylus-code-helper`, `sift-stylus-verify`, and `sift-stylus-deploy` skills for
next steps. Never print or commit private keys.
