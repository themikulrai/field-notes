"""Project CRUD."""

from __future__ import annotations


async def test_create_list_patch_delete(client) -> None:
    r = await client.post("/projects", json={"name": "p1", "subtitle": "s", "repo": None})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["name"] == "p1"

    r = await client.get("/projects")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())

    r = await client.patch(f"/projects/{pid}", json={"subtitle": "s2"})
    assert r.status_code == 200
    assert r.json()["subtitle"] == "s2"

    r = await client.delete(f"/projects/{pid}")
    assert r.status_code == 204

    r = await client.get(f"/projects/{pid}")
    assert r.status_code == 404
