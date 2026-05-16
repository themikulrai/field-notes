"""In-process pub/sub used by the SSE /events endpoint.

TODO: Chunk 2 — asyncio.Queue fan-out so MCP clients and the web UI can subscribe
to cell-update / verdict / lock events.
"""
