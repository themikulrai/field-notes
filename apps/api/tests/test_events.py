"""SSE + audit-log events."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time

import pytest
from field_notes_api.auth import mint_sse_token
from field_notes_api.db import get_sessionmaker
from field_notes_api.main import app
from field_notes_api.models import Event
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select


async def test_sse_requires_key(engine) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get("/events")
        assert r.status_code == 401
        r = await c.get("/events?key=wrong")
        assert r.status_code == 401


async def test_sse_receives_cell_created(client, api_key) -> None:
    """Subscribe, then have another client POST a cell, and verify we get the event."""
    r = await client.post("/projects", json={"name": "P"})
    pid = r.json()["id"]

    transport = ASGITransport(app=app)
    received: list[dict] = []

    async def subscribe() -> None:
        async with (
            AsyncClient(transport=transport, base_url="http://testserver", timeout=5.0) as c2,
            c2.stream("GET", f"/events?key={api_key}") as resp,
        ):
            assert resp.status_code == 200
            async for raw_line in resp.aiter_lines():
                if raw_line.startswith("data: "):
                    payload = raw_line[len("data: ") :]
                    try:
                        received.append(json.loads(payload))
                    except json.JSONDecodeError:
                        continue
                    if received[-1].get("kind") == "cell.created":
                        return

    sub_task = asyncio.create_task(subscribe())
    # Give the subscriber a tick to register.
    for _ in range(20):
        await asyncio.sleep(0.05)
        from field_notes_api.events_bus import bus

        if bus.subscriber_count >= 1:
            break

    r = await client.post(f"/projects/{pid}/cells", json={"kind": "agent", "title": "A"})
    assert r.status_code == 201

    try:
        await asyncio.wait_for(sub_task, timeout=5.0)
    except TimeoutError:
        sub_task.cancel()
        pytest.fail(f"never received cell.created; got {received!r}")

    assert any(e.get("kind") == "cell.created" for e in received)


async def test_sse_multi_subscribers(client, api_key) -> None:
    """Two subscribers both get the same event."""
    r = await client.post("/projects", json={"name": "P"})
    pid = r.json()["id"]

    transport = ASGITransport(app=app)

    async def one_sub() -> bool:
        async with (
            AsyncClient(transport=transport, base_url="http://testserver", timeout=5.0) as c2,
            c2.stream("GET", f"/events?key={api_key}") as resp,
        ):
            assert resp.status_code == 200
            async for raw_line in resp.aiter_lines():
                if raw_line.startswith("data: "):
                    env = json.loads(raw_line[len("data: ") :])
                    if env.get("kind") == "cell.created":
                        return True
        return False

    t1 = asyncio.create_task(one_sub())
    t2 = asyncio.create_task(one_sub())

    from field_notes_api.events_bus import bus

    for _ in range(40):
        await asyncio.sleep(0.05)
        if bus.subscriber_count >= 2:
            break

    await client.post(f"/projects/{pid}/cells", json={"kind": "agent", "title": "A"})

    done = await asyncio.gather(
        asyncio.wait_for(t1, timeout=5.0),
        asyncio.wait_for(t2, timeout=5.0),
    )
    assert all(done)


async def test_sse_keepalive_emitted(client, api_key) -> None:
    """With FIELD_NOTES_SSE_KEEPALIVE_SECONDS=0.5 (set in conftest), idle stream
    must emit a `:` comment line within ~1s."""
    transport = ASGITransport(app=app)
    saw_comment = False
    async with (
        AsyncClient(transport=transport, base_url="http://testserver", timeout=5.0) as c2,
        c2.stream("GET", f"/events?key={api_key}") as resp,
    ):
        assert resp.status_code == 200
        with contextlib.suppress(Exception):
            async for raw_line in resp.aiter_lines():
                if raw_line.startswith(":"):
                    saw_comment = True
                    break
    assert saw_comment, "expected a `:` keepalive comment within the timeout window"


async def test_events_table_populated(client) -> None:
    r = await client.post("/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.post(f"/projects/{pid}/cells", json={"kind": "agent", "title": "A"})

    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(select(Event))).scalars().all()
    kinds = [r.kind for r in rows]
    assert "project.created" in kinds
    assert "cell.created" in kinds


async def test_event_source_default_http(client) -> None:
    """Without an X-Field-Notes-Source header, payload.source == 'http'."""
    r = await client.post("/projects", json={"name": "P"})
    pid = r.json()["id"]

    sm = get_sessionmaker()
    async with sm() as s:
        ev = (await s.execute(select(Event).where(Event.kind == "project.created"))).scalars().first()
    assert ev is not None
    assert ev.payload["source"] == "http"
    assert str(ev.project_id) == pid


async def test_sse_token_endpoint_requires_key(engine) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post("/sse-token")
        assert r.status_code == 401


async def test_sse_token_endpoint_mints_token(client) -> None:
    r = await client.post("/sse-token")
    assert r.status_code == 200
    body = r.json()
    assert "token" in body and "expires_at" in body
    assert "." in body["token"]


async def test_sse_accepts_valid_token(client, api_key) -> None:
    """Mint a real token via the endpoint, then open SSE and receive an event."""
    r = await client.post("/sse-token")
    token = r.json()["token"]

    r = await client.post("/projects", json={"name": "P"})
    pid = r.json()["id"]

    transport = ASGITransport(app=app)
    received: list[dict] = []

    async def subscribe() -> None:
        async with (
            AsyncClient(transport=transport, base_url="http://testserver", timeout=5.0) as c2,
            c2.stream("GET", f"/events?token={token}") as resp,
        ):
            assert resp.status_code == 200
            async for raw_line in resp.aiter_lines():
                if raw_line.startswith("data: "):
                    payload = raw_line[len("data: ") :]
                    try:
                        received.append(json.loads(payload))
                    except json.JSONDecodeError:
                        continue
                    if received[-1].get("kind") == "cell.created":
                        return

    sub_task = asyncio.create_task(subscribe())
    for _ in range(20):
        await asyncio.sleep(0.05)
        from field_notes_api.events_bus import bus

        if bus.subscriber_count >= 1:
            break

    await client.post(f"/projects/{pid}/cells", json={"kind": "agent", "title": "A"})

    try:
        await asyncio.wait_for(sub_task, timeout=5.0)
    except TimeoutError:
        sub_task.cancel()
        pytest.fail(f"never received cell.created; got {received!r}")

    assert any(e.get("kind") == "cell.created" for e in received)


async def test_sse_rejects_expired_token(engine) -> None:
    """Token minted with negative TTL must be rejected."""
    token, _ = mint_sse_token(ttl_seconds=-1)
    # Sanity: exp is in the past.
    assert token  # non-empty
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get(f"/events?token={token}")
        assert r.status_code == 401


async def test_sse_rejects_forged_token(engine) -> None:
    """Same payload but wrong HMAC signature must fail."""
    import base64

    payload = json.dumps({"exp": int(time.time()) + 60}, separators=(",", ":"), sort_keys=True).encode()
    bad_sig = b"\x00" * 32
    payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    sig_b64 = base64.urlsafe_b64encode(bad_sig).rstrip(b"=").decode()
    bad = f"{payload_b64}.{sig_b64}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get(f"/events?token={bad}")
        assert r.status_code == 401
        # Also: garbage token.
        r = await c.get("/events?token=not-a-real-token")
        assert r.status_code == 401


async def test_sse_raw_key_still_works_but_logs_warning(client, api_key, caplog) -> None:
    """Backwards-compat: raw ?key= still accepted but emits a deprecation log."""
    # Reset the dedup so the warning fires for this test.
    import field_notes_api.auth as auth_mod

    auth_mod._warned_raw_key = False

    transport = ASGITransport(app=app)
    with caplog.at_level(logging.WARNING, logger="field_notes_api.auth"):
        async with (
            AsyncClient(transport=transport, base_url="http://testserver", timeout=2.0) as c2,
            c2.stream("GET", f"/events?key={api_key}") as resp,
        ):
            assert resp.status_code == 200
            with contextlib.suppress(Exception):
                async for raw_line in resp.aiter_lines():
                    # Just need to confirm the stream opens; bail on first line.
                    _ = raw_line
                    break
    assert any("DEPRECATED" in rec.message for rec in caplog.records), (
        f"expected deprecation warning, got {[r.message for r in caplog.records]!r}"
    )


async def test_event_source_mcp_header(client) -> None:
    """X-Field-Notes-Source: mcp propagates into payload.source."""
    r = await client.post("/projects", json={"name": "P"}, headers={"X-Field-Notes-Source": "mcp"})
    pid = r.json()["id"]
    sm = get_sessionmaker()
    async with sm() as s:
        ev = (await s.execute(select(Event).where(Event.kind == "project.created"))).scalars().first()
    assert ev.payload["source"] == "mcp"
    assert str(ev.project_id) == pid
