"""Tests for events_bus QueueFull -> drain + resync sentinel behavior."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
from field_notes_schema import EventEnvelope

from field_notes_api.events_bus import EventBus


def _make_env(kind: str = "cell.updated") -> EventEnvelope:
    return EventEnvelope(
        id=uuid.uuid4(),
        at=datetime.now(timezone.utc),
        kind=kind,
        project_id=None,
        cell_id=None,
        payload={},
    )


async def _drain_available(q: asyncio.Queue[str]) -> list[str]:
    """Pull everything currently buffered without blocking."""
    out: list[str] = []
    while True:
        try:
            out.append(q.get_nowait())
        except asyncio.QueueEmpty:
            return out


@pytest.mark.asyncio
async def test_queue_full_drains_and_emits_resync():
    bus = EventBus()
    # Manually attach a tiny queue as a subscriber.
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    bus._subscribers.add(q)

    # Publish 5 events without consuming → 1 fits, the next 4 overflow.
    for _ in range(5):
        await bus.publish(_make_env())

    msgs = await _drain_available(q)
    assert len(msgs) >= 1, "expected at least the resync sentinel"

    # The LAST item readable must be the resync sentinel.
    last = json.loads(msgs[-1])
    assert last["kind"] == "resync", f"final item should be resync, got {last}"

    # All intermediate items must NOT be additional resyncs piled up — the bus
    # should keep one sentinel, not N. And nothing comes after resync.
    assert sum(1 for m in msgs if json.loads(m).get("kind") == "resync") == 1

    # Drained: queue is now empty.
    assert q.empty()


@pytest.mark.asyncio
async def test_normal_flow_no_resync():
    bus = EventBus()
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=8)
    bus._subscribers.add(q)

    for _ in range(4):
        await bus.publish(_make_env())

    msgs = await _drain_available(q)
    assert len(msgs) == 4
    for m in msgs:
        assert json.loads(m).get("kind") != "resync"


@pytest.mark.asyncio
async def test_resync_payload_shape():
    bus = EventBus()
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    bus._subscribers.add(q)

    # Force overflow.
    for _ in range(3):
        await bus.publish(_make_env())

    msgs = await _drain_available(q)
    resyncs = [json.loads(m) for m in msgs if json.loads(m).get("kind") == "resync"]
    assert len(resyncs) == 1
    payload = resyncs[0]
    assert set(payload.keys()) == {"kind", "at"}
    assert payload["kind"] == "resync"
    # `at` must parse as ISO-8601 with timezone.
    parsed = datetime.fromisoformat(payload["at"])
    assert parsed.tzinfo is not None


@pytest.mark.asyncio
async def test_publisher_never_blocks_on_full_subscriber():
    """Even with a slow subscriber that never consumes, publish() must return quickly."""
    bus = EventBus()
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    bus._subscribers.add(q)

    async def hammer():
        for _ in range(1000):
            await bus.publish(_make_env())

    await asyncio.wait_for(hammer(), timeout=2.0)
    # And the queue is still bounded — at most 1 (the latest resync sentinel).
    assert q.qsize() <= 1


@pytest.mark.asyncio
async def test_warning_logged_on_drop(caplog):
    bus = EventBus()
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    bus._subscribers.add(q)

    with caplog.at_level("WARNING", logger="field_notes_api.events_bus"):
        for _ in range(3):
            await bus.publish(_make_env())

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("resync" in r.getMessage() for r in warnings)
