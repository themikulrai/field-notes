"""Cell CRUD + ordering invariants."""

from __future__ import annotations

import pytest


@pytest.fixture
async def project_id(client) -> str:
    r = await client.post("/projects", json={"name": "P"})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_cell(client, pid: str, kind: str = "agent", **extra) -> dict:
    body = {"kind": kind, **extra}
    r = await client.post(f"/projects/{pid}/cells", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_agent_at_end(client, project_id) -> None:
    c1 = await _create_cell(client, project_id, title="A")
    c2 = await _create_cell(client, project_id, title="B")
    assert c1["position"] == 0
    assert c2["position"] == 1


async def test_create_markdown(client, project_id) -> None:
    c = await _create_cell(client, project_id, kind="markdown", body="# hi")
    assert c["kind"] == "markdown"
    assert c["body"] == "# hi"
    assert c["title"] is None


async def test_create_empty(client, project_id) -> None:
    c = await _create_cell(client, project_id, kind="empty")
    assert c["kind"] == "empty"
    assert c["status"] == "open"


async def test_markdown_rejects_agent_fields(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "markdown", "title": "no"},
    )
    assert r.status_code == 422


async def test_empty_rejects_body(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "empty", "body": "no"},
    )
    assert r.status_code == 422


async def test_insert_after(client, project_id) -> None:
    a = await _create_cell(client, project_id, title="A")
    await _create_cell(client, project_id, title="B")
    c = await _create_cell(client, project_id, title="C", after_cell_id=a["id"])
    # Order should now be A, C, B
    r = await client.get(f"/projects/{project_id}/cells")
    titles = [x["title"] for x in r.json()]
    assert titles == ["A", "C", "B"]
    positions = [x["position"] for x in r.json()]
    assert positions == [0, 1, 2]
    assert c["position"] == 1


async def test_list_cells_position_order(client, project_id) -> None:
    for t in ["A", "B", "C", "D"]:
        await _create_cell(client, project_id, title=t)
    r = await client.get(f"/projects/{project_id}/cells")
    assert [x["title"] for x in r.json()] == ["A", "B", "C", "D"]
    assert [x["position"] for x in r.json()] == [0, 1, 2, 3]


async def test_patch_metrics_roundtrip(client, project_id) -> None:
    c = await _create_cell(client, project_id, title="A")
    metrics = [{"k": "acc", "v": "0.5", "d": "delta"}, {"k": "loss", "v": "0.3", "d": None}]
    r = await client.patch(f"/cells/{c['id']}", json={"metrics": metrics})
    assert r.status_code == 200
    assert r.json()["metrics"] == metrics


async def test_patch_rejects_unknown_fields(client, project_id) -> None:
    c = await _create_cell(client, project_id, title="A")
    r = await client.patch(f"/cells/{c['id']}", json={"verdict": {"state": "accept"}})
    assert r.status_code == 422


async def test_delete_cell_renumbers(client, project_id) -> None:
    await _create_cell(client, project_id, title="A")
    b = await _create_cell(client, project_id, title="B")
    await _create_cell(client, project_id, title="C")
    r = await client.delete(f"/cells/{b['id']}")
    assert r.status_code == 204
    r = await client.get(f"/projects/{project_id}/cells")
    assert [x["title"] for x in r.json()] == ["A", "C"]
    assert [x["position"] for x in r.json()] == [0, 1]


async def test_reorder_direction_up(client, project_id) -> None:
    await _create_cell(client, project_id, title="A")
    b = await _create_cell(client, project_id, title="B")
    r = await client.post(f"/cells/{b['id']}/reorder", json={"direction": "up"})
    assert r.status_code == 200, r.text
    assert r.json()["position"] == 0
    r = await client.get(f"/projects/{project_id}/cells")
    assert [x["title"] for x in r.json()] == ["B", "A"]


async def test_reorder_direction_down(client, project_id) -> None:
    a = await _create_cell(client, project_id, title="A")
    await _create_cell(client, project_id, title="B")
    r = await client.post(f"/cells/{a['id']}/reorder", json={"direction": "down"})
    assert r.status_code == 200
    r = await client.get(f"/projects/{project_id}/cells")
    assert [x["title"] for x in r.json()] == ["B", "A"]


async def test_reorder_absolute_position(client, project_id) -> None:
    cells = []
    for t in ["A", "B", "C", "D"]:
        cells.append(await _create_cell(client, project_id, title=t))
    # Move D (idx 3) to position 1 -> [A, D, B, C]
    r = await client.post(f"/cells/{cells[3]['id']}/reorder", json={"position": 1})
    assert r.status_code == 200, r.text
    r = await client.get(f"/projects/{project_id}/cells")
    assert [x["title"] for x in r.json()] == ["A", "D", "B", "C"]
    assert [x["position"] for x in r.json()] == [0, 1, 2, 3]


async def test_reorder_validation_error(client, project_id) -> None:
    a = await _create_cell(client, project_id, title="A")
    r = await client.post(f"/cells/{a['id']}/reorder", json={})
    assert r.status_code == 422
    r = await client.post(f"/cells/{a['id']}/reorder", json={"direction": "up", "position": 0})
    assert r.status_code == 422


async def _create_sandbox(client, pid: str, html="<div>old</div><p class='hint'>x</p>", js="", css="") -> dict:
    return await _create_cell(
        client,
        pid,
        title="S",
        visual={"kind": "sandbox", "html": html, "js": js, "css": css},
    )


async def test_patch_sandbox_html_basic(client, project_id) -> None:
    c = await _create_sandbox(client, project_id)
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/patch",
        json={"target": "html", "find": "<p class='hint'>x</p>", "replace": ""},
    )
    assert r.status_code == 200, r.text
    assert r.json()["visual"]["html"] == "<div>old</div>"


async def test_patch_sandbox_rejects_count_mismatch(client, project_id) -> None:
    c = await _create_sandbox(client, project_id, html="aa-bb-aa")
    # `aa` appears twice, default expected_count=1 → 422
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/patch",
        json={"target": "html", "find": "aa", "replace": "Z"},
    )
    assert r.status_code == 422
    assert "2 time" in r.json()["detail"]


async def test_patch_sandbox_explicit_count_replaces_all(client, project_id) -> None:
    c = await _create_sandbox(client, project_id, html="aa-bb-aa")
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/patch",
        json={"target": "html", "find": "aa", "replace": "Z", "expected_count": 2},
    )
    assert r.status_code == 200
    assert r.json()["visual"]["html"] == "Z-bb-Z"


async def test_patch_sandbox_rejects_missing_find(client, project_id) -> None:
    c = await _create_sandbox(client, project_id)
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/patch",
        json={"target": "html", "find": "not-there", "replace": "Z"},
    )
    assert r.status_code == 422
    assert "0 time" in r.json()["detail"]


async def test_patch_sandbox_404_on_unknown_cell(client) -> None:
    import uuid as _u
    r = await client.post(
        f"/cells/{_u.uuid4()}/visual-sandbox/patch",
        json={"target": "html", "find": "x", "replace": "y"},
    )
    assert r.status_code == 404


async def test_patch_sandbox_422_on_non_sandbox_visual(client, project_id) -> None:
    c = await _create_cell(
        client, project_id, title="S",
        visual={"kind": "svg", "source": "<svg/>"},
    )
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/patch",
        json={"target": "html", "find": "x", "replace": "y"},
    )
    assert r.status_code == 422
    assert "no visual.sandbox" in r.json()["detail"]


async def test_patch_sandbox_locked_returns_409(client, project_id) -> None:
    c = await _create_sandbox(client, project_id)
    await client.post(f"/cells/{c['id']}/verdict", json={"state": "accept"})
    lr = await client.post(f"/cells/{c['id']}/lock")
    assert lr.status_code == 200, lr.text
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/patch",
        json={"target": "html", "find": "<div>old</div>", "replace": "<div>new</div>"},
    )
    assert r.status_code == 409
