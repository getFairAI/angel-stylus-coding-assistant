"""MCP server layer exposing Stylus retrieval as standard MCP tools.

The FastAPI backend already contains all retrieval logic; this adds the missing
*protocol* surface so any MCP-capable host (Claude Code, Codex, Cursor, ChatGPT)
can discover and call the tools. It mounts onto the FastAPI app at ``/mcp`` over the
Streamable HTTP transport (see ``main.py``).

Tools reuse ``skill_registry.run_skill_search`` — the exact function the REST
``/skills/{id}/search`` endpoints call — so REST and MCP share identical behavior.
The tool names match the contract the skills already advertise
(``search_stylus_docs`` / ``search_stylus_code``).

Auth: public for now (no bearer token). To protect it later, add FastMCP auth here
and set the ``Authorization`` header in the plugin's ``.mcp.json``.
"""

from fastmcp import FastMCP

from skill_registry import (
    SKILL_ID_CODE_HELPER,
    SKILL_ID_PORTING_AUDITOR,
    SKILL_ID_RESEARCH,
    run_skill_search,
)

mcp = FastMCP("sift-stylus")


@mcp.tool
def search_stylus_docs(prompt: str) -> dict:
    """Retrieve references-first Arbitrum Stylus documentation and context.

    Use before answering Stylus SDK, tooling, deployment, verification, optimization,
    or ecosystem questions. Returns retrieved `context`, `references`, and
    `agent_guidance` (references-first; no synthesized contract code).
    """
    return run_skill_search(SKILL_ID_RESEARCH, prompt)


@mcp.tool
def search_stylus_code(prompt: str) -> dict:
    """Retrieve source-backed Stylus code context and snippets.

    Use for "how do I implement X in Stylus" questions where a code example helps.
    Returns retrieved `context`, `references`, and code-oriented `agent_guidance`.
    """
    return run_skill_search(SKILL_ID_CODE_HELPER, prompt)


@mcp.tool
def stylus_porting_audit(prompt: str) -> dict:
    """Assess a Solidity contract for Arbitrum Stylus (Rust) porting candidacy.

    Pass a GitHub URL or contract source. Returns an upside-first candidacy analysis
    (score, signals, carve-outs) grounded in static analysis and retrieved evidence.
    """
    return run_skill_search(SKILL_ID_PORTING_AUDITOR, prompt)


# Streamable HTTP ASGI app. path="/" because the FastAPI mount adds the "/mcp"
# prefix; the resulting public endpoint is <base>/mcp.
mcp_app = mcp.http_app(path="/")
