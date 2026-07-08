# Stylus verify hook — per-host install

One script, `../scripts/stylus-check-hook.sh`, powers the verify loop on every host.
It reads the PostToolUse payload on stdin and is **payload-tolerant**:

- **Claude Code** — edits arrive as `tool_input.file_path` (absolute).
- **Codex** — edits arrive via `apply_patch`; the file paths are embedded in
  `tool_input.command` and resolved against the payload `cwd`.

On a compile failure it prints the errors to stderr and exits `2`; both hosts feed
that back to the agent as actionable context. It no-ops for non-`.rs` edits,
non-Stylus crates, missing `cargo`, or `STYLUS_HOOK_DISABLE=1`.

## Claude Code

Shipped as part of the plugin via `hooks.json` (this directory), which points at
`${CLAUDE_PLUGIN_ROOT}/scripts/stylus-check-hook.sh`. Installing the plugin wires it
automatically — no manual step.

## Codex

Codex has the same hook model (`PostToolUse`, matcher on `tool_name`, exit-2
feedback) but its own config location and no plugin-root variable, so install
manually:

```bash
mkdir -p ~/.codex/hooks
cp scripts/stylus-check-hook.sh ~/.codex/hooks/
chmod +x ~/.codex/hooks/stylus-check-hook.sh
cp hooks/codex-hooks.json ~/.codex/hooks.json      # or merge into an existing one
```

`codex-hooks.json` matches `apply_patch|Edit|Write`. To scope it to one repo instead
of globally, place it at `<repo>/.codex/hooks.json`.

## Shared env toggles

- `STYLUS_HOOK_DISABLE=1` — disable entirely.
- `STYLUS_HOOK_FULL=1` — run `cargo stylus check` (WASM + size + activation dry-run)
  instead of the fast `cargo check`.
- `STYLUS_RPC_ENDPOINT` — RPC used by the full check.

Cursor 1.7+ has an equivalent hook model (`.cursor/hooks.json`); the same script
works there once its payload shape is added to the extractor — not yet wired.
