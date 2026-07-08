"""Tests for the MCP server layer (src/mcp_server.py) and its /mcp mount."""

import asyncio

import mcp_server
from fastmcp import Client

EXPECTED_TOOLS = {"search_stylus_docs", "search_stylus_code", "stylus_porting_audit"}


def _run(coro):
    return asyncio.run(coro)


def test_tools_are_registered():
    async def go():
        async with Client(mcp_server.mcp) as client:
            return {t.name for t in await client.list_tools()}

    assert EXPECTED_TOOLS <= _run(go())


def test_tool_calls_route_to_run_skill_search(monkeypatch):
    seen = {}

    def stub(skill_id, prompt, *args, **kwargs):
        seen["skill_id"] = skill_id
        seen["prompt"] = prompt
        return {"found": True, "context": "CTX", "references": [], "skill": skill_id}

    monkeypatch.setattr(mcp_server, "run_skill_search", stub)

    async def go():
        async with Client(mcp_server.mcp) as client:
            return await client.call_tool("search_stylus_code", {"prompt": "erc20 example"})

    result = _run(go())
    assert seen["skill_id"] == "sift-stylus-code-helper"
    assert seen["prompt"] == "erc20 example"
    data = getattr(result, "data", None) or getattr(result, "structured_content", None)
    assert data and data.get("context") == "CTX"


def test_porting_tool_routes_to_porting_skill(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mcp_server, "run_skill_search",
        lambda skill_id, prompt, *a, **k: seen.update(skill_id=skill_id) or {"found": True, "context": ""},
    )

    async def go():
        async with Client(mcp_server.mcp) as client:
            await client.call_tool("stylus_porting_audit", {"prompt": "https://github.com/x/y"})

    _run(go())
    assert seen["skill_id"] == "sift-stylus-porting-auditor"


def test_app_mounts_mcp_and_handshake_succeeds(monkeypatch):
    """End-to-end: the FastAPI app serves an MCP initialize handshake at /mcp (not 404)."""
    from fastapi.testclient import TestClient

    import main

    # /mcp mount is present on the app
    assert any("/mcp" in str(getattr(r, "path", "")) for r in main.app.routes)

    with TestClient(main.app) as client:
        resp = client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert resp.status_code == 200  # was 404 before the MCP layer existed
