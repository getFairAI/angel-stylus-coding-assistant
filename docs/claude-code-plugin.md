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
| MCP | `.mcp.json` → backend `/mcp` (`src/mcp_server.py`) | tools: `search_stylus_docs`, `search_stylus_code`, `stylus_porting_audit` |
| Template | `assets/stylus-project-template/` | CLAUDE.md, `rust-toolchain.toml`, release profile |

The three retrieval-oriented skills (research, code-helper, porting-auditor) call the
hosted MCP server; verify/scaffold/deploy/review run locally in the user's repo.

## The MCP server

The MCP surface is served by the backend itself (`src/mcp_server.py`, mounted at
`/mcp` via FastMCP Streamable HTTP in `main.py`), reusing the same
`skill_registry.run_skill_search` as the REST `/skills/{id}/search` endpoints. It
exposes three tools: `search_stylus_docs`, `search_stylus_code`, and
`stylus_porting_audit`. **Public — no auth** for now.

`.mcp.json` points at `${SIFT_MCP_URL:-https://sifter.azule.xyz/mcp}`; override
`SIFT_MCP_URL` to target another deployment:

```bash
export SIFT_MCP_URL="https://<your-backend>/mcp"
```

To add auth later: add a FastMCP auth provider in `src/mcp_server.py` and restore an
`Authorization: Bearer ${SIFT_MCP_TOKEN}` header in `.mcp.json`.

**Deployment note:** the reverse proxy fronting the backend must forward `/mcp` with
response buffering disabled (e.g. nginx `proxy_buffering off;`) so the Streamable HTTP
transport can stream. Verify with an MCP `initialize` handshake:

```bash
curl -sS -X POST https://<base>/mcp/ \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
# expect HTTP 200 (not 404)
```

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
