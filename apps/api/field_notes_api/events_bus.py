"""In-process pub/sub used by the SSE /events endpoint.

asyncio.Queue fan-out. Slow subscribers are NOT blocked on; instead, when a
subscriber's queue is full we drain it and push a single `resync` sentinel so
the client refetches state instead of desyncing forever. The audit log lives
in the `events` table; this bus is purely for live notification of currently-
connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from field_notes_schema import EventEnvelope

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    def _new_queue(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
        self._subscribers.add(q)
        return q

    def _drop_queue(self, q: asyncio.Queue[str]) -> None:
        self._subscribers.discard(q)

    @staticmethod
    def _resync_msg() -> str:
        return json.dumps({"kind": "resync", "at": _utcnow_iso()})

    def _drain_and_resync(self, q: asyncio.Queue[str]) -> None:
        """Drop everything pending on q and leave only a single resync sentinel.

        Bounded work: at most maxsize get_nowait + 1 put_nowait. Never blocks.
        """
        dropped = 0
        while True:
            try:
                q.get_nowait()
                dropped += 1
            except asyncio.QueueEmpty:
                break
        logger.warning(
            "events_bus: subscriber queue full; dropped %d pending event(s) and emitted resync sentinel (subscriber=%s)",
            dropped,
            id(q),
        )
        # Queue is now empty; this put_nowait cannot raise QueueFull.
        try:
            q.put_nowait(self._resync_msg())
        except asyncio.QueueFull:  # pragma: no cover — defensive
            pass

    async def publish(self, env: EventEnvelope) -> None:
        msg = env.model_dump_json()
        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                # Slow subscriber: never block the publisher. Drain + sentinel
                # so the client refetches state instead of silently desyncing.
                self._drain_and_resync(q)

    async def subscribe(self) -> AsyncIterator[str]:
        q = self._new_queue()
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            self._drop_queue(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


bus = EventBus()
