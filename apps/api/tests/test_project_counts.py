"""Project counts on ProjectRead.

These power the tab-strip pip indicators in the web UI: counts must be
available on the project list response (so inactive tabs render correctly
without loading each project's cells) and must reflect every cell-status
mutation.
"""

from __future__ import annotations

import pytest


@pytest.fixture
async def project_id(client) -> str:
    r = await client.post("/projects", json={"name": "P"})
    assert r.status_code == 201
    body = r.json()
    assert body["counts"] == {"in_progress": 0, "open": 0, "verified": 0, "rejected": 0}
    return body["id"]


async def _agent_cell(client, pid: str, title: str = "a") -> dict:
    r = await client.post(f"/projects/{pid}/cells", json={"kind": "agent", "title": title})
    assert r.status_code == 201, r.text
    return r.json()


async def _set_status(client, cid: str, status: str) -> None:
    r = await client.patch(f"/cells/{cid}", json={"status": status})
    assert r.status_code == 200, r.text


async def test_counts_present_on_list_and_get(client, project_id) -> None:
    r = await client.get("/projects")
    proj = next(p for p in r.json() if p["id"] == project_id)
    assert proj["counts"] == {"in_progress": 0, "open": 0, "verified": 0, "rejected": 0}

    r = await client.get(f"/projects/{project_id}")
    assert r.json()["counts"] == {"in_progress": 0, "open": 0, "verified": 0, "rejected": 0}


async def test_counts_reflect_mixed_statuses(client, project_id) -> None:
    # Agent cells are created with status=NULL by default; set each explicitly
    # so the counts aggregate has something to bucket.
    c1 = await _agent_cell(client, project_id, "in_prog")
    c2 = await _agent_cell(client, project_id, "open1")
    c3 = await _agent_cell(client, project_id, "open2")
    c4 = await _agent_cell(client, project_id, "verified")
    c5 = await _agent_cell(client, project_id, "rejected")
    await _set_status(client, c1["id"], "in_progress")
    await _set_status(client, c2["id"], "open")
    await _set_status(client, c3["id"], "open")
    await _set_status(client, c4["id"], "verified")
    await _set_status(client, c5["id"], "rejected")

    r = await client.get(f"/projects/{project_id}")
    counts = r.json()["counts"]
    assert counts == {"in_progress": 1, "open": 2, "verified": 1, "rejected": 1}

    # Sanity: list endpoint returns the same counts for this project.
    r = await client.get("/projects")
    proj = next(p for p in r.json() if p["id"] == project_id)
    assert proj["counts"] == counts


async def test_counts_ignore_non_agent_cells(client, project_id) -> None:
    agent = await _agent_cell(client, project_id, "a")
    await _set_status(client, agent["id"], "open")
    # Empty cells default to status="open"; should still be excluded because
    # kind != agent. Markdown cells never get a status.
    await client.post(f"/projects/{project_id}/cells", json={"kind": "markdown", "body": "x"})
    await client.post(f"/projects/{project_id}/cells", json={"kind": "empty"})

    r = await client.get(f"/projects/{project_id}")
    counts = r.json()["counts"]
    # Only the single agent cell contributes; the open=1 empty cell does not.
    assert counts["open"] == 1
    assert counts["in_progress"] == 0
    assert counts["verified"] == 0
    assert counts["rejected"] == 0


async def test_counts_decrement_on_status_change_and_delete(client, project_id) -> None:
    c = await _agent_cell(client, project_id, "x")
    await _set_status(client, c["id"], "open")
    r = await client.get(f"/projects/{project_id}")
    assert r.json()["counts"]["open"] == 1

    await _set_status(client, c["id"], "verified")
    r = await client.get(f"/projects/{project_id}")
    assert r.json()["counts"] == {"in_progress": 0, "open": 0, "verified": 1, "rejected": 0}

    r = await client.delete(f"/cells/{c['id']}")
    assert r.status_code == 204
    r = await client.get(f"/projects/{project_id}")
    assert r.json()["counts"] == {"in_progress": 0, "open": 0, "verified": 0, "rejected": 0}


async def test_list_isolates_counts_per_project(client) -> None:
    r1 = await client.post("/projects", json={"name": "A"})
    r2 = await client.post("/projects", json={"name": "B"})
    pid1, pid2 = r1.json()["id"], r2.json()["id"]

    a1 = await _agent_cell(client, pid1, "a1")
    await _set_status(client, a1["id"], "in_progress")
    b1 = await _agent_cell(client, pid2, "b1")
    await _set_status(client, b1["id"], "rejected")

    r = await client.get("/projects")
    by_id = {p["id"]: p for p in r.json()}
    assert by_id[pid1]["counts"] == {"in_progress": 1, "open": 0, "verified": 0, "rejected": 0}
    assert by_id[pid2]["counts"] == {"in_progress": 0, "open": 0, "verified": 0, "rejected": 1}
