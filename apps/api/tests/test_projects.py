"""Project CRUD."""

from __future__ import annotations


async def test_create_list_patch_delete(client) -> None:
    r = await client.post("/projects", json={"name": "p1", "subtitle": "s", "repo": None})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["name"] == "p1"
    # New nullable column appears with default null on a fresh project.
    assert r.json()["ui_filter"] is None

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


async def test_ui_filter_set_and_event(client) -> None:
    """POST /projects/{pid}/ui-filter persists the value AND emits ui.filter_changed."""
    r = await client.post("/projects", json={"name": "P"})
    pid = r.json()["id"]

    r = await client.post(f"/projects/{pid}/ui-filter", json={"filter": "open"})
    assert r.status_code == 200, r.text
    assert r.json()["ui_filter"] == "open"

    r = await client.get(f"/projects/{pid}")
    assert r.json()["ui_filter"] == "open"

    # Check the audit log captured ui.filter_changed.
    from field_notes_api.db import get_sessionmaker
    from field_notes_api.models import Event
    from sqlalchemy import select

    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(select(Event).where(Event.kind == "ui.filter_changed"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].payload["filter"] == "open"
    assert str(rows[0].project_id) == pid


async def test_ui_filter_invalid_value(client) -> None:
    r = await client.post("/projects", json={"name": "P"})
    pid = r.json()["id"]
    r = await client.post(f"/projects/{pid}/ui-filter", json={"filter": "bogus"})
    assert r.status_code == 422


async def test_ui_filter_404(client) -> None:
    import uuid as _uuid

    r = await client.post(f"/projects/{_uuid.uuid4()}/ui-filter", json={"filter": "all"})
    assert r.status_code == 404


async def test_events_recent(client) -> None:
    r = await client.post("/projects", json={"name": "P"})
    pid = r.json()["id"]
    await client.post(f"/projects/{pid}/cells", json={"kind": "agent", "title": "A"})

    r = await client.get("/events/recent?limit=10")
    assert r.status_code == 200, r.text
    kinds = [e["kind"] for e in r.json()]
    # Newest first — cell.created should come before project.created.
    assert "project.created" in kinds
    assert "cell.created" in kinds
    assert kinds.index("cell.created") < kinds.index("project.created")


async def test_events_recent_project_filter(client) -> None:
    r1 = await client.post("/projects", json={"name": "A"})
    pid1 = r1.json()["id"]
    r2 = await client.post("/projects", json={"name": "B"})
    pid2 = r2.json()["id"]
    await client.post(f"/projects/{pid1}/cells", json={"kind": "agent", "title": "x"})
    await client.post(f"/projects/{pid2}/cells", json={"kind": "agent", "title": "y"})

    r = await client.get(f"/events/recent?project={pid1}&limit=20")
    assert r.status_code == 200
    rows = r.json()
    assert all(e["project_id"] == pid1 for e in rows)
    assert any(e["kind"] == "cell.created" for e in rows)


async def test_events_recent_requires_key(engine) -> None:
    from field_notes_api.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get("/events/recent")
        assert r.status_code == 401


# ---------- Project manual order (drag-to-reorder) ----------


async def _mk_projects(client, names: list[str]) -> list[str]:
    ids = []
    for n in names:
        r = await client.post("/projects", json={"name": n})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


async def _order(client) -> list[str]:
    r = await client.get("/projects")
    assert r.status_code == 200
    return [p["name"] for p in r.json()]


async def test_new_projects_get_increasing_positions(client) -> None:
    r0 = await client.post("/projects", json={"name": "A"})
    r1 = await client.post("/projects", json={"name": "B"})
    assert r0.json()["position"] == 0
    assert r1.json()["position"] == 1
    assert await _order(client) == ["A", "B"]


async def test_reorder_by_position_moves_and_persists(client) -> None:
    await _mk_projects(client, ["A", "B", "C"])
    ids = {p["name"]: p["id"] for p in (await client.get("/projects")).json()}
    # Move C to the front (position 0).
    r = await client.post(f"/projects/{ids['C']}/reorder", json={"position": 0})
    assert r.status_code == 200, r.text
    assert r.json()["position"] == 0
    assert await _order(client) == ["C", "A", "B"]
    # Persisted across a fresh list.
    assert await _order(client) == ["C", "A", "B"]


async def test_reorder_by_direction(client) -> None:
    await _mk_projects(client, ["A", "B", "C"])
    ids = {p["name"]: p["id"] for p in (await client.get("/projects")).json()}
    r = await client.post(f"/projects/{ids['A']}/reorder", json={"direction": "down"})
    assert r.status_code == 200, r.text
    assert await _order(client) == ["B", "A", "C"]
    r = await client.post(f"/projects/{ids['C']}/reorder", json={"direction": "up"})
    assert r.status_code == 200, r.text
    assert await _order(client) == ["B", "C", "A"]


async def test_reorder_position_clamps_out_of_range(client) -> None:
    await _mk_projects(client, ["A", "B", "C"])
    ids = {p["name"]: p["id"] for p in (await client.get("/projects")).json()}
    r = await client.post(f"/projects/{ids['A']}/reorder", json={"position": 99})
    assert r.status_code == 200, r.text
    assert await _order(client) == ["B", "C", "A"]


async def test_reorder_emits_event(client) -> None:
    ids = await _mk_projects(client, ["A", "B"])
    await client.post(f"/projects/{ids[1]}/reorder", json={"position": 0})
    r = await client.get(f"/events/recent?project={ids[1]}&limit=20")
    assert r.status_code == 200
    assert any(e["kind"] == "project.reordered" for e in r.json())


async def test_reorder_unknown_project_404(client) -> None:
    import uuid

    r = await client.post(f"/projects/{uuid.uuid4()}/reorder", json={"position": 0})
    assert r.status_code == 404


async def test_archived_defaults_false_and_patch_toggles(client) -> None:
    r = await client.post("/projects", json={"name": "arch"})
    pid = r.json()["id"]
    assert r.json()["archived"] is False

    r = await client.patch(f"/projects/{pid}", json={"archived": True})
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is True

    r = await client.patch(f"/projects/{pid}", json={"archived": False})
    assert r.json()["archived"] is False
