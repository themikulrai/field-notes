"""SSE /events router.

Server-Sent Events stream backed by `events_bus`. EventSource cannot send
custom headers, so auth uses `?key=` instead. A `:` keepalive line is emitted
every `field_notes_sse_keepalive_seconds` to keep edge proxies (Fly.io,
Cloudflare) from idle-timing the connection.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from ..auth import require_api_key_query
from ..config import get_settings
from ..events_bus import bus

router = APIRouter(tags=["events"])


@router.get("/events", dependencies=[Depends(require_api_key_query)])
async def events(project: uuid.UUID | None = Query(default=None)) -> EventSourceResponse:
    settings = get_settings()
    keepalive = settings.field_notes_sse_keepalive_seconds

    async def gen() -> AsyncIterator[dict]:
        sub = bus.subscribe()
        sub_iter = sub.__aiter__()
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(sub_iter.__anext__(), timeout=keepalive)
                except TimeoutError:
                    # Comment line acts as the keepalive — sse-starlette renders this from {"comment"}.
                    yield {"comment": "keepalive"}
                    continue
                except StopAsyncIteration:
                    return
                if project is not None:
                    try:
                        env = json.loads(msg)
                    except json.JSONDecodeError:
                        continue
                    if env.get("project_id") != str(project):
                        continue
                yield {"data": msg}
        finally:
            await sub.aclose()

    return EventSourceResponse(gen(), ping=None)
