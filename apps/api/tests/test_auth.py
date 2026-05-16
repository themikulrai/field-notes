"""Auth: header for JSON endpoints, /healthz public."""

from __future__ import annotations

from field_notes_api.main import app
from httpx import ASGITransport, AsyncClient


async def test_healthz_is_open() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get("/healthz")
        assert r.status_code == 200


async def test_missing_header_rejected(engine, api_key) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get("/projects")
        assert r.status_code == 401
        assert r.json()["detail"] == "missing or invalid api key"


async def test_wrong_key_rejected(engine, api_key) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get("/projects", headers={"X-Field-Notes-Key": "wrong"})
        assert r.status_code == 401


async def test_correct_key_accepted(client, api_key) -> None:
    r = await client.get("/projects")
    assert r.status_code == 200
