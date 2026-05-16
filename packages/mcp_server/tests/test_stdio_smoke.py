"""Spawn the stdio MCP server as a subprocess and verify the handshake works.

This is the bedrock check that `python -m field_notes_mcp` actually responds
to MCP `initialize` / `tools/list` over stdio. If the SDK API changes or our
wiring is wrong, this test catches it before anyone tries to plug us into
Claude Code.
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_stdio_initialize_and_list_tools() -> None:
    # The server fails fast without FIELD_NOTES_KEY, so pass a dummy. We don't
    # actually make any API calls in this smoke test — just initialize + list_tools.
    env = dict(os.environ)
    env["FIELD_NOTES_KEY"] = "smoketest-key"
    env["FIELD_NOTES_API_URL"] = "http://127.0.0.1:1"  # never called

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "field_notes_mcp"],
        env=env,
    )

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        # Bounded wait so a hung server fails the test rather than the harness.
        await asyncio.wait_for(session.initialize(), timeout=10.0)
        tools_resp = await asyncio.wait_for(session.list_tools(), timeout=10.0)
        names = {t.name for t in tools_resp.tools}

    assert "list_projects" in names
    assert "create_cell" in names
    assert "get_feedback" in names
    assert "set_filter" in names
    assert "tail_events" in names
    # And the human-only ones MUST NOT be in the registry.
    assert "set_verdict" not in names
    assert "lock_cell" not in names
    assert "unlock_cell" not in names


async def test_stdio_exits_when_key_missing() -> None:
    """Spawn the stdio entry without FIELD_NOTES_KEY; the process must exit non-zero
    with a clear stderr message."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("FIELD_NOTES_")}

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "field_notes_mcp",
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise AssertionError("server should have exited fast when FIELD_NOTES_KEY missing") from None
    assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}"
    assert b"FIELD_NOTES_KEY" in stderr
