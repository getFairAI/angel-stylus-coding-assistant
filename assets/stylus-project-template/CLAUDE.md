# Stylus project conventions

This is an Arbitrum Stylus (Rust → WASM) smart-contract project. The following are
ground-truth constraints for work in this repo.

## Hard constraints
- Contracts compile to WASM. The **Brotli-compressed binary must be ≤ 24KB**
  (uncompressed ≤ 128KB). Exceeding this blocks deployment.
- `cargo stylus check` must pass before any deploy — it compiles to WASM and dry-runs
  on-chain activation.
- Deployed contracts require **on-chain activation** (via the `ArbWasm` precompile)
  and must be **re-activated at least every 365 days** and after network upgrades, or
  they become uncallable.

## Toolchain
- Rust channel is pinned in `rust-toolchain.toml`; the `wasm32-unknown-unknown` target
  is required (`rustup target add wasm32-unknown-unknown`).
- `cargo-stylus` is the CLI: `cargo stylus new|check|deploy|verify|cache|export-abi`.

## Build profile
- The release profile is size-optimized (`opt-level = "z"`, `lto`, `codegen-units = 1`,
  `panic = "abort"`, `strip`). Do not relax these without a size budget check.

## Dependencies
- Use `stylus-sdk` + `alloy-primitives` for core types.
- Prefer `openzeppelin-stylus` for standard token/access patterns over reimplementation.
- Every dependency counts against the 24KB limit — keep the graph lean.

## Working style
- Verify with `cargo stylus check` (or the fast `cargo check --target wasm32-unknown-unknown`)
  after contract edits; a PostToolUse hook may run this automatically.
- Update storage before external calls (checks-effects-interactions); external calls
  can re-enter.
- Prefer checked/saturating arithmetic on value-bearing paths.
- Test on Arbitrum Sepolia before mainnet.
