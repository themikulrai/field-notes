"""Start the HTTP/SSE MCP server in a uvicorn thread and verify the SSE
handshake works. Same shape as the stdio smoke test, different transport.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import threading
from collections.abc import Iterator

import uvicorn
from field_notes_mcp.http_server import build_app
from mcp import ClientSession
from mcp.client.sse import sse_client


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _ServerThread(threading.Thread):
    def __init__(self, app, host: str, port: int) -> None:
        super().__init__(daemon=True)
        cfg = uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="on")
        self.server = uvicorn.Server(cfg)

    def run(self) -> None:
        self.server.run()


@contextlib.contextmanager
def _running_server(host: str, port: int) -> Iterator[None]:
    app, _mcp, client = build_app("http://127.0.0.1:1", "test-key")
    t = _ServerThread(app, host, port)
    t.start()
    # Wait until uvicorn is accepting connections.
    deadline = 5.0
    elapsed = 0.0
    while elapsed < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                break
        except OSError:
            import time as _t

            _t.sleep(0.1)
            elapsed += 0.1
    else:
        raise AssertionError(f"uvicorn never came up on {host}:{port}")
    try:
        yield
    finally:
        t.server.should_exit = True
        t.join(timeout=5.0)

        # Close the shared httpx client on a worker thread so we don't conflict
        # with the test's own pytest-asyncio loop.
        def _close() -> None:
            asyncio.run(client.aclose())

        cleanup = threading.Thread(target=_close, daemon=True)
        cleanup.start()
        cleanup.join(timeout=5.0)


async def test_http_initialize_and_list_tools() -> None:
    host = "127.0.0.1"
    port = _free_port()
    with _running_server(host, port):
        url = f"http://{host}:{port}/sse"
        async with sse_client(url) as (read, write), ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=10.0)
            tools_resp = await asyncio.wait_for(session.list_tools(), timeout=10.0)
            names = {t.name for t in tools_resp.tools}
    assert "list_projects" in names
    assert "get_feedback" in names
    assert "set_verdict" not in names


def test_http_build_app_registers_tools() -> None:
    """Lightweight: building the app wires the same registry as stdio. Proves
    the HTTP entrypoint shares the tool surface."""
    import asyncio as _a

    app, mcp, client = build_app("http://127.0.0.1:1", "test-key")
    try:
        tools = _a.run(mcp.list_tools())
    finally:
        _a.run(client.aclose())
    names = {t.name for t in tools}
    assert "list_projects" in names
    assert "create_cell" in names
    assert "get_feedback" in names
    assert "tail_events" in names
    assert "set_filter" in names
    # Boundary holds.
    assert "set_verdict" not in names
    assert "lock_cell" not in names
    assert "unlock_cell" not in names
    # And the Starlette app actually has SSE routes mounted.
    paths = {getattr(r, "path", None) for r in app.routes}
    assert any(p and "sse" in p for p in paths), f"no SSE route on the app; routes={paths!r}"
