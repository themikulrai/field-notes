"""Unit tests for FieldNotesClient — purely through MockTransport, no API needed.

We assert the wire-level behaviour the rest of the system depends on:
- Every request carries `X-Field-Notes-Key` and `X-Field-Notes-Source: mcp`.
- Each method hits the right URL + verb.
- 409 on cell endpoints raises LockedCellError; everything else raises
  FieldNotesAPIError with status + detail intact.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest
from field_notes_mcp.client import FieldNotesAPIError, FieldNotesClient, LockedCellError
from field_notes_schema import (
    CellCreate,
    CellKind,
    CellUpdate,
    ProjectCreate,
    ProjectUpdate,
    ReorderRequest,
    UiFilterSet,
)

# ---------------- helpers ----------------


def _check_headers(request: httpx.Request) -> None:
    assert request.headers.get("X-Field-Notes-Key") == "test-key"
    assert request.headers.get("X-Field-Notes-Source") == "mcp"


def _now_iso() -> str:
    return "2026-05-15T12:00:00+00:00"


def _proj_json(pid: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    return {
        "id": str(pid),
        "name": overrides.get("name", "P"),
        "subtitle": overrides.get("subtitle"),
        "repo": overrides.get("repo"),
        "ui_filter": overrides.get("ui_filter"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }


def _cell_json(cid: uuid.UUID, pid: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    return {
        "id": str(cid),
        "project_id": str(pid),
        "kind": overrides.get("kind", "agent"),
        "position": overrides.get("position", 0),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "title": overrides.get("title"),
        "agent_id": overrides.get("agent_id"),
        "status": overrides.get("status"),
        "conclusion": overrides.get("conclusion"),
        "metrics": overrides.get("metrics"),
        "visual": overrides.get("visual"),
        "video": overrides.get("video"),
        "deep": overrides.get("deep"),
        "verdict": overrides.get("verdict"),
        "locked": overrides.get("locked", False),
        "body": overrides.get("body"),
    }


def _make_client(handler) -> FieldNotesClient:
    return FieldNotesClient(
        base_url="http://api.test",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )


# ---------------- tests ----------------


async def test_list_projects_sends_correct_request_and_parses() -> None:
    pid = uuid.uuid4()
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        _check_headers(req)
        assert req.method == "GET"
        assert req.url.path == "/projects"
        return httpx.Response(200, json=[_proj_json(pid, name="A")])

    async with _make_client(handler) as c:
        projects = await c.list_projects()
    assert len(projects) == 1
    assert projects[0].id == pid
    assert projects[0].name == "A"
    assert len(seen) == 1


async def test_get_project() -> None:
    pid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        _check_headers(req)
        assert req.method == "GET" and req.url.path == f"/projects/{pid}"
        return httpx.Response(200, json=_proj_json(pid))

    async with _make_client(handler) as c:
        p = await c.get_project(pid)
    assert p.id == pid


async def test_create_project() -> None:
    pid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        _check_headers(req)
        assert req.method == "POST" and req.url.path == "/projects"
        body = json.loads(req.content)
        assert body["name"] == "New"
        assert body["repo"] == "git@x"
        return httpx.Response(201, json=_proj_json(pid, name="New", repo="git@x"))

    async with _make_client(handler) as c:
        p = await c.create_project(ProjectCreate(name="New", repo="git@x"))
    assert p.name == "New"


async def test_update_project_patch_only_set_fields() -> None:
    pid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PATCH" and req.url.path == f"/projects/{pid}"
        body = json.loads(req.content)
        # exclude_unset means only subtitle should appear, not name/repo.
        assert "subtitle" in body and body["subtitle"] == "S"
        assert "name" not in body
        assert "repo" not in body
        return httpx.Response(200, json=_proj_json(pid, subtitle="S"))

    async with _make_client(handler) as c:
        p = await c.update_project(pid, ProjectUpdate(subtitle="S"))
    assert p.subtitle == "S"


async def test_delete_project() -> None:
    pid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "DELETE" and req.url.path == f"/projects/{pid}"
        return httpx.Response(204)

    async with _make_client(handler) as c:
        await c.delete_project(pid)


async def test_set_ui_filter_hits_dedicated_endpoint() -> None:
    pid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST" and req.url.path == f"/projects/{pid}/ui-filter"
        body = json.loads(req.content)
        assert body == {"filter": "verified"}
        return httpx.Response(200, json=_proj_json(pid, ui_filter="verified"))

    async with _make_client(handler) as c:
        p = await c.set_ui_filter(pid, UiFilterSet(filter="verified"))
    assert p.ui_filter == "verified"


async def test_list_cells_and_get_cell() -> None:
    pid = uuid.uuid4()
    cid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == f"/projects/{pid}/cells":
            return httpx.Response(200, json=[_cell_json(cid, pid, title="T")])
        if req.url.path == f"/cells/{cid}":
            return httpx.Response(200, json=_cell_json(cid, pid, title="T"))
        return httpx.Response(404)

    async with _make_client(handler) as c:
        cells = await c.list_cells(pid)
        one = await c.get_cell(cid)
    assert len(cells) == 1 and cells[0].title == "T"
    assert one.id == cid


async def test_create_cell_omits_none_fields() -> None:
    pid = uuid.uuid4()
    cid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST" and req.url.path == f"/projects/{pid}/cells"
        body = json.loads(req.content)
        # exclude_none must drop the unset visual/video/deep/metrics so the server's
        # markdown/empty validators don't see junk.
        assert "kind" in body and body["kind"] == "agent"
        assert "title" in body
        for k in ("visual", "video", "deep", "metrics"):
            assert k not in body, f"{k} should be omitted when None"
        return httpx.Response(201, json=_cell_json(cid, pid, title="T"))

    async with _make_client(handler) as c:
        await c.create_cell(pid, CellCreate(kind=CellKind.agent, title="T"))


async def test_update_cell_409_raises_locked() -> None:
    cid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "cell is locked"})

    async with _make_client(handler) as c:
        with pytest.raises(LockedCellError) as exc:
            await c.update_cell(cid, CellUpdate(title="x"))
    assert exc.value.cell_id == str(cid)
    assert exc.value.status == 409


async def test_delete_cell_409_raises_locked() -> None:
    cid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "cell is locked"})

    async with _make_client(handler) as c:
        with pytest.raises(LockedCellError):
            await c.delete_cell(cid)


async def test_reorder_cell_passes_body() -> None:
    cid = uuid.uuid4()
    pid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == f"/cells/{cid}/reorder"
        body = json.loads(req.content)
        assert body == {"direction": "up"}
        return httpx.Response(200, json=_cell_json(cid, pid))

    async with _make_client(handler) as c:
        await c.reorder_cell(cid, ReorderRequest(direction="up"))


async def test_recent_events_passes_params() -> None:
    pid = uuid.uuid4()
    event_payload = {
        "id": str(uuid.uuid4()),
        "at": _now_iso(),
        "kind": "cell.created",
        "project_id": str(pid),
        "cell_id": None,
        "payload": {"source": "mcp"},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/events/recent"
        assert req.url.params.get("limit") == "25"
        assert req.url.params.get("project") == str(pid)
        return httpx.Response(200, json=[event_payload])

    async with _make_client(handler) as c:
        evs = await c.recent_events(project=pid, limit=25)
    assert len(evs) == 1 and evs[0].kind == "cell.created"


async def test_generic_api_error_for_non_409() -> None:
    pid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    async with _make_client(handler) as c:
        with pytest.raises(FieldNotesAPIError) as exc:
            await c.get_project(pid)
    assert exc.value.status == 500
    assert "boom" in exc.value.detail
