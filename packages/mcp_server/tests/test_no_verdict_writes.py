"""Guardrail: the agent must never have a path to write a verdict, lock, or unlock.

If a future change adds set_verdict / lock_cell / unlock_cell to the MCP tool
registry, this test fails loudly. The whole point of Field Notes is the
asymmetry: the agent produces; the human judges.
"""

from __future__ import annotations

import inspect

from field_notes_mcp import HUMAN_ONLY_TOOLS, TOOL_NAMES, FieldNotesClient
from field_notes_mcp.__main__ import build_server


def test_registered_tools_exactly_match_tool_names() -> None:
    """No extra tools, no missing tools — the surface is a fixed list."""
    import asyncio

    mcp, client = build_server("http://localhost:8000", "x")
    try:
        tools = asyncio.run(mcp.list_tools())
    finally:
        asyncio.run(client.aclose())

    registered = {t.name for t in tools}
    assert registered == set(TOOL_NAMES), f"tool surface drifted; expected {set(TOOL_NAMES)} got {registered}"


def test_human_only_tools_absent_from_registry() -> None:
    import asyncio

    mcp, client = build_server("http://localhost:8000", "x")
    try:
        tools = asyncio.run(mcp.list_tools())
    finally:
        asyncio.run(client.aclose())
    registered = {t.name for t in tools}
    for forbidden in HUMAN_ONLY_TOOLS:
        assert forbidden not in registered, (
            f"FORBIDDEN tool '{forbidden}' appeared on the agent's MCP surface — "
            "the human's authority must not be writable by the agent."
        )


def test_client_does_not_expose_verdict_or_lock_methods() -> None:
    """The HTTP client surface is also locked down: no `set_verdict`, no `lock_cell`,
    no `unlock_cell`. Even if someone wired a tool, it'd fail at the client."""
    public = {n for n, _ in inspect.getmembers(FieldNotesClient, inspect.isfunction) if not n.startswith("_")}
    for forbidden in ("set_verdict", "lock_cell", "unlock_cell", "set_verdict_for_cell", "lock", "unlock"):
        assert forbidden not in public, f"FieldNotesClient exposes forbidden method '{forbidden}'"
