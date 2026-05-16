"""Verdict + lock semantics."""

from __future__ import annotations

import pytest


@pytest.fixture
async def cell(client) -> dict:
    r = await client.post("/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(f"/projects/{pid}/cells", json={"kind": "agent", "title": "A"})
    return r.json()


async def test_set_verdict_accept_verifies(client, cell) -> None:
    r = await client.post(f"/cells/{cell['id']}/verdict", json={"state": "accept", "note": "ok"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "verified"
    assert r.json()["verdict"]["state"] == "accept"
    assert r.json()["verdict"]["note"] == "ok"


async def test_set_verdict_reject_rejects(client, cell) -> None:
    r = await client.post(f"/cells/{cell['id']}/verdict", json={"state": "reject", "note": "no"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


async def test_clear_verdict_returns_to_open(client, cell) -> None:
    await client.post(f"/cells/{cell['id']}/verdict", json={"state": "accept"})
    # JSON null body to clear.
    r = await client.post(f"/cells/{cell['id']}/verdict", json=None)
    assert r.status_code == 200, r.text
    assert r.json()["verdict"] is None
    assert r.json()["status"] == "open"


async def test_lock_requires_accept(client, cell) -> None:
    r = await client.post(f"/cells/{cell['id']}/lock")
    assert r.status_code == 409


async def test_lock_with_reject_rejected(client, cell) -> None:
    await client.post(f"/cells/{cell['id']}/verdict", json={"state": "reject"})
    r = await client.post(f"/cells/{cell['id']}/lock")
    assert r.status_code == 409


async def test_lock_with_accept_works(client, cell) -> None:
    await client.post(f"/cells/{cell['id']}/verdict", json={"state": "accept"})
    r = await client.post(f"/cells/{cell['id']}/lock")
    assert r.status_code == 200, r.text
    assert r.json()["locked"] is True


async def test_locked_rejects_patch(client, cell) -> None:
    await client.post(f"/cells/{cell['id']}/verdict", json={"state": "accept"})
    await client.post(f"/cells/{cell['id']}/lock")
    r = await client.patch(f"/cells/{cell['id']}", json={"title": "nope"})
    assert r.status_code == 409


async def test_locked_rejects_delete(client, cell) -> None:
    await client.post(f"/cells/{cell['id']}/verdict", json={"state": "accept"})
    await client.post(f"/cells/{cell['id']}/lock")
    r = await client.delete(f"/cells/{cell['id']}")
    assert r.status_code == 409


async def test_locked_rejects_verdict_change(client, cell) -> None:
    await client.post(f"/cells/{cell['id']}/verdict", json={"state": "accept"})
    await client.post(f"/cells/{cell['id']}/lock")
    r = await client.post(f"/cells/{cell['id']}/verdict", json={"state": "reject"})
    assert r.status_code == 409


async def test_unlock_works(client, cell) -> None:
    await client.post(f"/cells/{cell['id']}/verdict", json={"state": "accept"})
    await client.post(f"/cells/{cell['id']}/lock")
    r = await client.post(f"/cells/{cell['id']}/unlock")
    assert r.status_code == 200
    assert r.json()["locked"] is False
    # And now patch works again.
    r = await client.patch(f"/cells/{cell['id']}", json={"title": "ok"})
    assert r.status_code == 200
