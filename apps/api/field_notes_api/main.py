"""FastAPI application entrypoint.

This is intentionally minimal in Chunk 1. Chunk 2 will mount routers,
add auth middleware, and wire SQLAlchemy + the events bus.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Field Notes API")


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    """Liveness probe used by docker-compose and Fly.io."""
    return {"ok": True}


# TODO: Chunk 2 — include routers (projects, cells, verdicts, events) and auth dependency.
