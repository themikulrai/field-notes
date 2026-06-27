"""Tool-layer tests — drive the FieldNotesClient via MockTransport and
exercise each tool body. Asserts:
- Tool returns JSON-serialisable shape.
- update_cell + delete_cell map a 409 to the structured locked_cell error.
- get_feedback only surfaces cells WITH a verdict.
- list_cells client-side filters work.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from field_notes_mcp import tools as T
from field_notes_mcp.client import FieldNotesClient


def _now_iso() -> str:
    return "2026-05-15T12:00:00+00:00"


def _proj(pid: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    return {
        "id": str(pid),
        "name": overrides.get("name", "P"),
        "subtitle": None,
        "repo": None,
        "ui_filter": overrides.get("ui_filter"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }


def _cell(cid: uuid.UUID, pid: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    return {
        "id": str(cid),
        "project_id": str(pid),
        "kind": overrides.get("kind", "agent"),
        "position": overrides.get("position", 0),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "title": overrides.get("title"),
        "agent_id": None,
        "status": overrides.get("status"),
        "conclusion": overrides.get("conclusion"),
        "metrics": None,
        "visual": None,
        "video": None,
        "deep": None,
        "verdict": overrides.get("verdict"),
        "locked": overrides.get("locked", False),
        "body": overrides.get("body"),
    }


def _make_client(handler) -> FieldNotesClient:
    return FieldNotesClient("http://api.test", "test-key", transport=httpx.MockTransport(handler))


async def test_t_list_projects_returns_list_of_dicts() -> None:
    pid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_proj(pid)])

    async with _make_client(handler) as c:
        result = await T.t_list_projects(c)
    assert isinstance(result, list)
    assert result[0]["id"] == str(pid)


async def test_t_create_project_posts_pydantic_body() -> None:
    pid = uuid.uuid4()
    seen_body: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen_body.update(json.loads(req.content))
        return httpx.Response(201, json=_proj(pid, name="N"))

    async with _make_client(handler) as c:
        out = await T.t_create_project(c, T.CreateProjectInput(name="N", subtitle="S"))
    assert out["name"] == "N"
    assert seen_body["name"] == "N"
    assert seen_body["subtitle"] == "S"


async def test_t_update_project_only_set_fields() -> None:
    pid = uuid.uuid4()
    seen_body: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen_body.update(json.loads(req.content))
        return httpx.Response(200, json=_proj(pid, name="renamed"))

    async with _make_client(handler) as c:
        await T.t_update_project(c, T.UpdateProjectInput(project_id=pid, patch=T.ProjectPatch(name="renamed")))
    assert seen_body == {"name": "renamed"}


async def test_t_list_cells_client_side_filters() -> None:
    pid = uuid.uuid4()
    a, b, cm = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                _cell(a, pid, status="open", kind="agent", locked=False),
                _cell(b, pid, status="verified", kind="agent", locked=True),
                _cell(cm, pid, kind="markdown", body="x"),
            ],
        )

    async with _make_client(handler) as c:
        all_cells = await T.t_list_cells(c, T.ListCellsInput(project_id=pid))
        only_verified = await T.t_list_cells(c, T.ListCellsInput(project_id=pid, status="verified"))
        only_markdown = await T.t_list_cells(c, T.ListCellsInput(project_id=pid, kind="markdown"))
        only_locked = await T.t_list_cells(c, T.ListCellsInput(project_id=pid, locked=True))
        only_unlocked = await T.t_list_cells(c, T.ListCellsInput(project_id=pid, locked=False))

    assert len(all_cells) == 3
    assert [x["id"] for x in only_verified] == [str(b)]
    assert [x["id"] for x in only_markdown] == [str(cm)]
    assert [x["id"] for x in only_locked] == [str(b)]
    # Both the open and the markdown cell are unlocked.
    assert {x["id"] for x in only_unlocked} == {str(a), str(cm)}


async def test_t_update_cell_locked_returns_structured_error() -> None:
    cid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "cell is locked"})

    async with _make_client(handler) as c:
        out = await T.t_update_cell(c, T.UpdateCellInput(cell_id=cid, patch=T.CellPatch(title="x")))
    assert out["error"] == "locked_cell"
    assert out["cell_id"] == str(cid)
    assert "locked" in out["message"].lower()


async def test_t_delete_cell_locked_returns_structured_error() -> None:
    cid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "cell is locked"})

    async with _make_client(handler) as c:
        out = await T.t_delete_cell(c, T._CellId(cell_id=cid))
    assert out["error"] == "locked_cell"


async def test_t_reorder_cell_locked_returns_structured_error() -> None:
    cid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "cell is locked"})

    async with _make_client(handler) as c:
        out = await T.t_reorder_cell(c, T.ReorderCellInput(cell_id=cid, direction="up"))
    assert out["error"] == "locked_cell"


async def test_t_patch_visual_sandbox_forwards_body() -> None:
    pid = uuid.uuid4()
    cid = uuid.uuid4()
    seen: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json=_cell(cid, pid, visual={"kind": "sandbox", "html": "Z", "js": "", "css": ""}),
        )

    async with _make_client(handler) as c:
        out = await T.t_patch_visual_sandbox(
            c,
            T.PatchVisualSandboxInput(cell_id=cid, target="html", find="<old>", replace="<new>"),
        )
    assert seen["path"].endswith(f"/cells/{cid}/visual-sandbox/patch")
    assert seen["body"] == {"target": "html", "find": "<old>", "replace": "<new>", "expected_count": 1}
    assert out["id"] == str(cid)


async def test_t_patch_visual_sandbox_locked_returns_structured_error() -> None:
    cid = uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "cell is locked"})

    async with _make_client(handler) as c:
        out = await T.t_patch_visual_sandbox(
            c,
            T.PatchVisualSandboxInput(cell_id=cid, target="html", find="x", replace="y"),
        )
    assert out["error"] == "locked_cell"
    assert out["cell_id"] == str(cid)


async def test_t_get_feedback_filters_out_no_verdict() -> None:
    pid = uuid.uuid4()
    a, b = uuid.uuid4(), uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == f"/projects/{pid}/cells":
            return httpx.Response(
                200,
                json=[
                    _cell(a, pid, title="A", status="open"),  # no verdict
                    _cell(
                        b,
                        pid,
                        title="B",
                        status="verified",
                        verdict={"state": "accept", "note": "looks right", "by": "you", "at": _now_iso()},
                    ),
                ],
            )
        return httpx.Response(404)

    async with _make_client(handler) as c:
        out = await T.t_get_feedback(c, T.GetFeedbackInput(project_id=pid))
    assert len(out) == 1
    assert out[0]["cell_id"] == str(b)
    assert out[0]["verdict_state"] == "accept"
    assert out[0]["note"] == "looks right"
    assert out[0]["locked"] is False


async def test_t_get_feedback_cross_project_lists_all() -> None:
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    c1, c2 = uuid.uuid4(), uuid.uuid4()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/projects":
            return httpx.Response(200, json=[_proj(p1), _proj(p2)])
        if req.url.path == f"/projects/{p1}/cells":
            return httpx.Response(
                200,
                json=[
                    _cell(
                        c1,
                        p1,
                        title="x",
                        verdict={"state": "accept", "note": "", "by": "you", "at": _now_iso()},
                    )
                ],
            )
        if req.url.path == f"/projects/{p2}/cells":
            return httpx.Response(
                200,
                json=[
                    _cell(
                        c2,
                        p2,
                        title="y",
                        verdict={"state": "reject", "note": "no", "by": "you", "at": _now_iso()},
                    )
                ],
            )
        return httpx.Response(404)

    async with _make_client(handler) as c:
        out = await T.t_get_feedback(c, T.GetFeedbackInput())
    assert {x["cell_id"] for x in out} == {str(c1), str(c2)}
    assert {x["verdict_state"] for x in out} == {"accept", "reject"}


async def test_t_set_filter_posts_to_ui_filter() -> None:
    pid = uuid.uuid4()
    seen_path: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_path.append(req.url.path)
        return httpx.Response(200, json=_proj(pid, ui_filter="open"))

    async with _make_client(handler) as c:
        out = await T.t_set_filter(c, T.SetFilterInput(project_id=pid, filter="open"))
    assert seen_path == [f"/projects/{pid}/ui-filter"]
    assert out["ui_filter"] == "open"


async def test_t_tail_events_passes_limit() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/events/recent"
        assert req.url.params.get("limit") == "5"
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(uuid.uuid4()),
                    "at": _now_iso(),
                    "kind": "cell.created",
                    "project_id": None,
                    "cell_id": None,
                    "payload": {},
                }
            ],
        )

    async with _make_client(handler) as c:
        out = await T.t_tail_events(c, T.TailEventsInput(limit=5))
    assert len(out) == 1
    assert out[0]["kind"] == "cell.created"


# ----- Forgiving flat-args lift for update_cell / update_project ----------
# Agents (Opus 4.7) routinely emit `{cell_id, conclusion: "..."}` despite the
# nested-`patch` schema. The before-validator lifts known patch fields into a
# `patch` wrapper while still rejecting unknown top-level keys.


def test_update_cell_accepts_flat_args() -> None:
    cid = uuid.uuid4()
    m = T.UpdateCellInput.model_validate({"cell_id": str(cid), "conclusion": "done", "status": "verified"})
    assert m.cell_id == cid
    assert m.patch.conclusion == "done"
    assert m.patch.status == "verified"


def test_update_cell_accepts_nested_patch() -> None:
    cid = uuid.uuid4()
    m = T.UpdateCellInput.model_validate({"cell_id": str(cid), "patch": {"conclusion": "done"}})
    assert m.patch.conclusion == "done"


def test_update_cell_unknown_field_rejected() -> None:
    import pytest

    cid = uuid.uuid4()
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        T.UpdateCellInput.model_validate({"cell_id": str(cid), "typo_field": "x"})


def test_update_cell_both_flat_and_nested_rejected() -> None:
    import pytest

    cid = uuid.uuid4()
    with pytest.raises(Exception):  # noqa: B017
        T.UpdateCellInput.model_validate({"cell_id": str(cid), "patch": {"conclusion": "a"}, "conclusion": "b"})


def test_update_project_accepts_flat_args() -> None:
    pid = uuid.uuid4()
    m = T.UpdateProjectInput.model_validate({"project_id": str(pid), "name": "renamed"})
    assert m.project_id == pid
    assert m.patch.name == "renamed"


def test_update_project_accepts_nested_patch() -> None:
    pid = uuid.uuid4()
    m = T.UpdateProjectInput.model_validate({"project_id": str(pid), "patch": {"name": "renamed"}})
    assert m.patch.name == "renamed"


def test_update_project_unknown_field_rejected() -> None:
    import pytest

    pid = uuid.uuid4()
    with pytest.raises(Exception):  # noqa: B017
        T.UpdateProjectInput.model_validate({"project_id": str(pid), "bogus": "x"})


# ----- Tool descriptions nudge agents to fill the deep block --------------
# Pins the intent of the create_cell/update_cell descriptions: agents only fill
# hparams/files/runs/logs if the tool surface tells them to. A future reword
# that drops this guidance should fail loudly here.


async def _registered_descriptions() -> dict[str, str]:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test")
    T.register_tools(mcp, lambda: None)  # type: ignore[arg-type,return-value]
    return {t.name: (t.description or "") for t in await mcp.list_tools()}


async def test_create_cell_description_mentions_deep_block() -> None:
    desc = (await _registered_descriptions())["create_cell"].lower()
    assert "deep" in desc
    for part in ("hparams", "files", "runs", "logs"):
        assert part in desc, f"create_cell description should mention deep.{part}"


async def test_create_cell_description_distinguishes_note_section_result() -> None:
    # Item 1: agents must be able to tell note vs section vs result apart. The
    # description must spell out that a section is a markdown cell with a heading
    # body (no separate kind), a note is markdown prose, a result is an agent cell.
    desc = (await _registered_descriptions())["create_cell"].lower()
    assert "section" in desc
    assert "## " in desc or "# " in desc, "must show the heading-body recipe for a section"
    for word in ("note", "result", "markdown", "agent"):
        assert word in desc, f"create_cell description should mention {word!r}"


async def test_update_cell_description_mentions_deep_block() -> None:
    desc = (await _registered_descriptions())["update_cell"].lower()
    assert "deep" in desc


def test_update_project_both_flat_and_nested_rejected() -> None:
    import pytest

    pid = uuid.uuid4()
    with pytest.raises(Exception):  # noqa: B017
        T.UpdateProjectInput.model_validate({"project_id": str(pid), "patch": {"name": "a"}, "name": "b"})
