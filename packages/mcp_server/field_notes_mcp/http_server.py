"""HTTP/SSE entrypoint for the Field Notes MCP server.

Run via:
    python -m field_notes_mcp.http_server --host 0.0.0.0 --port 7800

FastMCP exposes an SSE-based ASGI app via `mcp.sse_app()`. We mount it under
"/" and run it with uvicorn. Same tools, same FieldNotesClient, just a
different transport. Useful for remote agents (Claude Desktop) or as a
sidecar alongside the main API.

Env:
    FIELD_NOTES_API_URL              (default http://localhost:8000)
    FIELD_NOTES_KEY                  (REQUIRED)
    FIELD_NOTES_MCP_HTTP_HOST        (default 127.0.0.1)
    FIELD_NOTES_MCP_HTTP_PORT        (default 7800)

CLI flags override env. uvicorn must be installed (it ships with FastAPI which
the API package already depends on, so in the workspace it's always present).
"""

from __future__ import annotations

import argparse

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from .client import FieldNotesClient
from .config import load_or_exit
from .tools import register_tools


def build_app(api_url: str, api_key: str) -> tuple[Starlette, FastMCP, FieldNotesClient]:
    """Build a Starlette app exposing the MCP server over SSE."""
    mcp = FastMCP("field-notes")
    client = FieldNotesClient(base_url=api_url, api_key=api_key)
    register_tools(mcp, lambda: client)
    app = mcp.sse_app()
    return app, mcp, client


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Field Notes MCP HTTP/SSE server")
    parser.add_argument("--host", default=None, help="bind host (default from env)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default from env)")
    args = parser.parse_args(argv)

    settings = load_or_exit()
    host = args.host or settings.field_notes_mcp_http_host
    port = args.port if args.port is not None else settings.field_notes_mcp_http_port

    app, _mcp, _client = build_app(settings.field_notes_api_url, settings.field_notes_key)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
