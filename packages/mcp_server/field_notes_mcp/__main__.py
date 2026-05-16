"""stdio entrypoint for the Field Notes MCP server.

Run via:
    python -m field_notes_mcp
or the console script `field-notes-mcp` (defined in pyproject.toml).

Env:
    FIELD_NOTES_API_URL  (default http://localhost:8000)
    FIELD_NOTES_KEY      (REQUIRED — shared secret)

The agent's connection: stdio. The FastMCP SDK serialises tool I/O over
newline-delimited JSON-RPC on stdin/stdout, so any logging MUST go to stderr.
"""

from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from .client import FieldNotesClient
from .config import load_or_exit
from .tools import register_tools


def build_server(api_url: str, api_key: str) -> tuple[FastMCP, FieldNotesClient]:
    """Construct a wired FastMCP + the underlying HTTP client. Test helper too."""
    mcp = FastMCP("field-notes")
    client = FieldNotesClient(base_url=api_url, api_key=api_key)
    register_tools(mcp, lambda: client)
    return mcp, client


async def _arun() -> None:
    settings = load_or_exit()
    mcp, client = build_server(settings.field_notes_api_url, settings.field_notes_key)
    try:
        await mcp.run_stdio_async()
    finally:
        await client.aclose()


def main() -> None:
    asyncio.run(_arun())


if __name__ == "__main__":
    main()
