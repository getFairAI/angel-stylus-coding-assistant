# Sift Stylus — Claude Code plugin

This repo doubles as a Claude Code plugin (`sift-stylus`) that turns Claude Code into
a best-in-class Arbitrum Stylus development agent: source-grounded research + code
help, porting audits, a local `cargo stylus` verify loop, and correct-by-default
project scaffolding.

## What ships

| Component | Path | What it does |
|---|---|---|
| Manifest | `.claude-plugin/plugin.json` | plugin identity |
| Skills | `skills/sift-stylus-*/SKILL.md` | research, code-helper, porting-auditor, verify, scaffold, deploy, review |
| Command | `commands/stylus-init.md` | `/stylus-init` — project conventions + toolchain + size profile |
| Hook | `hooks/hooks.json` → `scripts/stylus-check-hook.sh` | PostToolUse `cargo check` on `.rs` edits |
| MCP | `.mcp.json` | remote retrieval server exposing `search_stylus_docs` / `search_stylus_code` |
| Template | `assets/stylus-project-template/` | CLAUDE.md, `rust-toolchain.toml`, release profile |

The three retrieval-oriented skills (research, code-helper, porting-auditor) call the
hosted MCP server; verify/scaffold/deploy/review run locally in the user's repo.

## Configure the MCP server

The retrieval MCP is a hosted server managed by your team (not started by the plugin).
Set its URL (and token, if the server requires auth) before use:

```bash
export SIFT_MCP_URL="https://<your-hosted-mcp>/mcp"   # defaults to sifter.azule.xyz/mcp
export SIFT_MCP_TOKEN="<token>"                        # only if the server requires auth
```

`.mcp.json` expands these at connect time. If your server needs no auth, remove the
`Authorization` header from `.mcp.json`.

> Open item: confirm the hosted MCP exposes a **porting-audit tool** (the backend's
> static-analysis endpoint), not only the two search tools — the `sift-stylus-porting-auditor`
> skill depends on it.

## Install / test locally

```bash
# load for one session from this repo (repo root is the plugin root)
claude --plugin-dir .

# validate structure before release
claude plugin validate .

# inspect what loaded
claude plugin details sift-stylus
```

Verify inside a session: the `sift-stylus-*` skills appear in the `/` menu,
`/stylus-init` scaffolds a project, and (in a Stylus project) editing a `.rs` file
triggers the verify hook.

## Hook toggles

`STYLUS_HOOK_DISABLE=1` disables the verify hook; `STYLUS_HOOK_FULL=1` runs
`cargo stylus check` instead of the fast `cargo check`; `STYLUS_RPC_ENDPOINT` sets the
RPC for the full check. Codex install is documented in `hooks/README.md`.
