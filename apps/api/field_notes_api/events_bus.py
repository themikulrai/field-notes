"""In-process pub/sub used by the SSE /events endpoint.

asyncio.Queue fan-out. Slow subscribers are dropped (we never block a write
endpoint on a stuck consumer). The audit log lives in the `events` table; this
bus is purely for live notification of currently-connected clients.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from field_notes_schema import EventEnvelope


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    def _new_queue(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
        self._subscribers.add(q)
        return q

    def _drop_queue(self, q: asyncio.Queue[str]) -> None:
        self._subscribers.discard(q)

    async def subscribe(self) -> AsyncIterator[str]:
        q = self._new_queue()
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            self._drop_queue(q)

    async def publish(self, env: EventEnvelope) -> None:
        msg = env.model_dump_json()
        for q in list(self._subscribers):
            # Slow subscribers are dropped rather than blocking the writer.
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(msg)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


bus = EventBus()
