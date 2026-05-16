"""SSE /events router.

Server-Sent Events stream backed by `events_bus`. EventSource cannot send
custom headers, so auth uses `?key=` instead. A `:` keepalive line is emitted
every `field_notes_sse_keepalive_seconds` to keep edge proxies (Fly.io,
Cloudflare) from idle-timing the connection.

Also exposes `/events/recent` (header-auth) for the MCP `tail_events` tool —
returns the latest audit-log rows newest-first, optionally filtered by project.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from field_notes_schema import EventEnvelope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from ..auth import require_api_key, require_api_key_query
from ..config import get_settings
from ..db import get_session
from ..events_bus import bus
from ..models import Event

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


@router.get(
    "/events/recent",
    response_model=list[EventEnvelope],
    dependencies=[Depends(require_api_key)],
)
async def recent_events(
    project: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[EventEnvelope]:
    """Tail the audit log. Header-auth (unlike /events SSE which uses `?key`)."""
    stmt = select(Event).order_by(Event.at.desc()).limit(limit)
    if project is not None:
        stmt = select(Event).where(Event.project_id == project).order_by(Event.at.desc()).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        EventEnvelope(
            id=r.id,
            at=r.at,
            kind=r.kind,
            project_id=r.project_id,
            cell_id=r.cell_id,
            payload=r.payload or {},
        )
        for r in rows
    ]
