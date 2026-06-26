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


async def _updated_at_map(client, pid: str) -> dict[str, str]:
    r = await client.get(f"/projects/{pid}/cells")
    assert r.status_code == 200
    return {x["id"]: x["updated_at"] for x in r.json()}


async def test_reorder_does_not_bump_unrelated_updated_at(client, project_id) -> None:
    cells = []
    for t in ["A", "B", "C", "D", "E"]:
        cells.append(await _create_cell(client, project_id, title=t))
    before = await _updated_at_map(client, project_id)
    # Move D (idx 3) to position 0 -> [D, A, B, C, E]. Affected range = [0,3].
    r = await client.post(f"/cells/{cells[3]['id']}/reorder", json={"position": 0})
    assert r.status_code == 200, r.text
    after = await _updated_at_map(client, project_id)
    # E (idx 4) was outside the shifted range — must be untouched.
    assert before[cells[4]["id"]] == after[cells[4]["id"]]
    # A, B, C, D all had their positions shifted — they may bump.
    # (We don't require them to bump, but the key invariant is E untouched.)
    # Order is sanity-checked too.
    r = await client.get(f"/projects/{project_id}/cells")
    assert [x["title"] for x in r.json()] == ["D", "A", "B", "C", "E"]


async def test_delete_only_bumps_subsequent_updated_at(client, project_id) -> None:
    cells = []
    for t in ["A", "B", "C", "D", "E"]:
        cells.append(await _create_cell(client, project_id, title=t))
    before = await _updated_at_map(client, project_id)
    r = await client.delete(f"/cells/{cells[2]['id']}")
    assert r.status_code == 204
    after = await _updated_at_map(client, project_id)
    # A (idx 0) and B (idx 1) sit before the deleted cell — must NOT bump.
    assert before[cells[0]["id"]] == after[cells[0]["id"]]
    assert before[cells[1]["id"]] == after[cells[1]["id"]]


async def test_create_at_end_does_not_bump_existing(client, project_id) -> None:
    cells = []
    for t in ["A", "B", "C"]:
        cells.append(await _create_cell(client, project_id, title=t))
    before = await _updated_at_map(client, project_id)
    new_cell = await _create_cell(client, project_id, title="D")
    after = await _updated_at_map(client, project_id)
    for c in cells:
        assert before[c["id"]] == after[c["id"]], f"{c['title']} updated_at bumped"
    assert new_cell["position"] == 3


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


async def test_patch_visual_preserves_unspecified_sandbox_fields(client, project_id) -> None:
    """PATCH /cells/{id} with only `html` must not clobber existing js/css."""
    c = await _create_sandbox(
        client, project_id, html="<h1>orig</h1>", js="console.log('j')", css="body{}",
    )
    r = await client.patch(
        f"/cells/{c['id']}",
        json={"visual": {"kind": "sandbox", "html": "<h1>new</h1>"}},
    )
    assert r.status_code == 200, r.text
    v = r.json()["visual"]
    assert v["html"] == "<h1>new</h1>"
    assert v["js"] == "console.log('j')"
    assert v["css"] == "body{}"


async def test_patch_visual_replaces_on_kind_change(client, project_id) -> None:
    """Switching kind (sandbox -> svg) must replace fully, not merge."""
    c = await _create_sandbox(
        client, project_id, html="<h1>h</h1>", js="j", css="c",
    )
    r = await client.patch(
        f"/cells/{c['id']}",
        json={"visual": {"kind": "svg", "source": "<svg/>"}},
    )
    assert r.status_code == 200, r.text
    v = r.json()["visual"]
    assert v["kind"] == "svg"
    assert v["source"] == "<svg/>"
    assert "html" not in v
    assert "js" not in v


async def test_patch_visual_empty_string_does_not_overwrite(client, project_id) -> None:
    """Explicit "" is the schema default and indistinguishable from unset;
    must NOT clobber existing content."""
    c = await _create_sandbox(
        client, project_id, html="<h1>keep</h1>", js="keepjs", css="keepcss",
    )
    r = await client.patch(
        f"/cells/{c['id']}",
        json={"visual": {"kind": "sandbox", "html": "", "js": "", "css": ""}},
    )
    assert r.status_code == 200, r.text
    v = r.json()["visual"]
    assert v["html"] == "<h1>keep</h1>"
    assert v["js"] == "keepjs"
    assert v["css"] == "keepcss"


# ---------- append_visual_sandbox (chunked builder) ----------


async def test_append_sandbox_concatenates_in_order(client, project_id) -> None:
    c = await _create_cell(client, project_id, title="A")
    chunks = ["<div>", "hello", "</div>"]
    for i, ch in enumerate(chunks):
        r = await client.post(
            f"/cells/{c['id']}/visual-sandbox/append",
            json={"target": "html", "chunk": ch, "seq": i},
        )
        assert r.status_code == 200, r.text
    final = r.json()["visual"]
    assert final["html"] == "<div>hello</div>"
    assert final["kind"] == "sandbox"


async def test_append_rejects_out_of_order_seq(client, project_id) -> None:
    c = await _create_cell(client, project_id, title="A")
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/append",
        json={"target": "html", "chunk": "x", "seq": 0},
    )
    assert r.status_code == 200, r.text
    # chunks=1, sending seq=2 (skipping seq=1) must be rejected
    r2 = await client.post(
        f"/cells/{c['id']}/visual-sandbox/append",
        json={"target": "html", "chunk": "y", "seq": 2},
    )
    assert r2.status_code == 422
    assert "seq" in r2.json()["detail"]


async def test_append_initializes_visual_if_none(client, project_id) -> None:
    # Empty cell → has no visual at all
    r = await client.post(f"/projects/{project_id}/cells", json={"kind": "empty"})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["visual"] is None
    r2 = await client.post(
        f"/cells/{c['id']}/visual-sandbox/append",
        json={"target": "js", "chunk": "console.log(1)", "seq": 0},
    )
    assert r2.status_code == 200, r2.text
    v = r2.json()["visual"]
    assert v["kind"] == "sandbox"
    assert v["js"] == "console.log(1)"
    assert v["html"] == ""
    assert v["css"] == ""


async def test_append_rejects_kind_change(client, project_id) -> None:
    c = await _create_cell(
        client, project_id, title="S",
        visual={"kind": "svg", "source": "<svg/>"},
    )
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/append",
        json={"target": "html", "chunk": "<p/>", "seq": 0},
    )
    assert r.status_code == 422
    assert "non-sandbox" in r.json()["detail"]


async def test_append_finalize_sets_status_open(client, project_id) -> None:
    # finalize is a content write, so it must route the cell to "open" (review
    # queue) — NOT the deprecated "ready", which the web UI cannot render.
    c = await _create_cell(client, project_id, title="A")
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/append",
        json={"target": "html", "chunk": "<p>done</p>", "seq": 0, "finalize": True},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "open"
    assert out["status"] != "ready"
    assert out["visual"]["html"] == "<p>done</p>"
    # _chunks cleared on finalize
    assert "_chunks" not in out["visual"]


async def test_append_finalize_on_verified_cell_returns_to_open(client, project_id) -> None:
    # Regression: re-finalizing a sandbox on an already-verified cell used to
    # clobber status to "ready", desyncing it from the accept verdict and
    # silently skipping re-review. It must come back to "open" like any edit.
    c = await _create_cell(client, project_id, title="V")
    rv = await client.post(f"/cells/{c['id']}/verdict", json={"state": "accept", "note": "lgtm"})
    assert rv.status_code == 200, rv.text
    assert rv.json()["status"] == "verified"
    r = await client.post(
        f"/cells/{c['id']}/visual-sandbox/append",
        json={"target": "js", "chunk": "console.log(1)", "seq": 0, "finalize": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "open"


# ---------- MCP source pins cell status to "open" ----------
#
# Server-side invariant: any write with X-Field-Notes-Source: mcp forces
# `status = "open"` regardless of payload. http-sourced writes are unchanged.


async def test_create_mcp_forces_status_open_overriding_body(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "A", "status": "verified", "deep": {"na": True}},
        headers={"X-Field-Notes-Source": "mcp"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "open"


async def test_create_mcp_forces_status_open_when_unset(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "A", "deep": {"na": True}},
        headers={"X-Field-Notes-Source": "mcp"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "open"


async def test_create_http_status_passes_through(client, project_id) -> None:
    # No header → defaults to http; status from body wins.
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "A", "status": "verified"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "verified"
    # Explicit http header behaves the same.
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "B", "status": "rejected"},
        headers={"X-Field-Notes-Source": "http"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "rejected"


async def test_patch_mcp_status_forced_open_even_when_body_says_verified(
    client, project_id
) -> None:
    # Seed cell + verdict (so we can confirm verdict relationship is untouched).
    c = await _create_cell(client, project_id, title="A", deep={"na": True})
    vr = await client.post(f"/cells/{c['id']}/verdict", json={"state": "accept", "note": "ok"})
    assert vr.status_code == 200, vr.text
    assert vr.json()["status"] == "verified"
    assert vr.json()["verdict"]["state"] == "accept"

    # Agent edit via MCP — request says status=verified, server must force "open".
    r = await client.patch(
        f"/cells/{c['id']}",
        json={"status": "verified"},
        headers={"X-Field-Notes-Source": "mcp"},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "open"
    # Verdict row untouched — only cell.status flipped.
    assert out["verdict"] is not None
    assert out["verdict"]["state"] == "accept"
    assert out["verdict"]["note"] == "ok"


async def test_patch_mcp_no_status_in_body_still_reopens(client, project_id) -> None:
    c = await _create_cell(client, project_id, title="A", status="verified", deep={"na": True})
    assert c["status"] == "verified"
    # Touching only `conclusion` via MCP must still flip status -> open.
    r = await client.patch(
        f"/cells/{c['id']}",
        json={"conclusion": "redo"},
        headers={"X-Field-Notes-Source": "mcp"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "open"
    assert r.json()["conclusion"] == "redo"


async def test_patch_http_status_passes_through(client, project_id) -> None:
    c = await _create_cell(client, project_id, title="A")
    r = await client.patch(
        f"/cells/{c['id']}",
        json={"status": "verified"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "verified"
    # And with explicit http header.
    r = await client.patch(
        f"/cells/{c['id']}",
        json={"status": "rejected"},
        headers={"X-Field-Notes-Source": "http"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"


# ---------- Mandatory deep block on MCP-sourced agent cells ----------
#
# Agent cells written by agents (source=mcp) must carry a deep block (or na), and
# it must stay within size caps. http (human) writes are never blocked.

MCP = {"X-Field-Notes-Source": "mcp"}


async def test_mcp_agent_create_without_deep_is_rejected(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "A"},
        headers=MCP,
    )
    assert r.status_code == 422, r.text
    assert "deep" in r.json()["detail"].lower()


async def test_mcp_agent_create_with_na_is_accepted(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "A", "deep": {"na": True}},
        headers=MCP,
    )
    assert r.status_code == 201, r.text


async def test_mcp_agent_create_with_filled_deep_is_accepted(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "A", "deep": {"hparams": {"lr": "3e-4"}}},
        headers=MCP,
    )
    assert r.status_code == 201, r.text


async def test_mcp_agent_create_oversized_logs_is_rejected(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "A", "deep": {"logs": "x" * 2000}},
        headers=MCP,
    )
    assert r.status_code == 422, r.text
    assert "logs" in r.json()["detail"].lower()


async def test_mcp_agent_create_too_many_hparams_is_rejected(client, project_id) -> None:
    hparams = {f"k{i}": str(i) for i in range(40)}
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "A", "deep": {"hparams": hparams}},
        headers=MCP,
    )
    assert r.status_code == 422, r.text
    assert "hparams" in r.json()["detail"].lower()


async def test_http_agent_create_without_deep_is_allowed(client, project_id) -> None:
    # The human (source=http) is never blocked for a missing deep block.
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "A"},
    )
    assert r.status_code == 201, r.text


async def test_mcp_markdown_create_not_subject_to_deep_rule(client, project_id) -> None:
    # Enforcement is agent-only; a markdown note via mcp needs no deep.
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "markdown", "body": "## Results"},
        headers=MCP,
    )
    assert r.status_code == 201, r.text


async def test_mcp_update_deepless_agent_without_deep_is_rejected(client, project_id) -> None:
    c = await _create_cell(client, project_id, title="A")  # http create, no deep
    r = await client.patch(f"/cells/{c['id']}", json={"conclusion": "redo"}, headers=MCP)
    assert r.status_code == 422, r.text
    assert "deep" in r.json()["detail"].lower()


async def test_mcp_update_supplying_deep_is_accepted(client, project_id) -> None:
    c = await _create_cell(client, project_id, title="A")  # http create, no deep
    r = await client.patch(
        f"/cells/{c['id']}",
        json={"conclusion": "redo", "deep": {"hparams": {"lr": "1e-4"}}},
        headers=MCP,
    )
    assert r.status_code == 200, r.text
    assert r.json()["deep"]["hparams"]["lr"] == "1e-4"


async def test_http_update_deepless_agent_is_allowed(client, project_id) -> None:
    # Human edit of a deep-less agent cell is not blocked.
    c = await _create_cell(client, project_id, title="A")
    r = await client.patch(f"/cells/{c['id']}", json={"conclusion": "human note"})
    assert r.status_code == 200, r.text
    assert r.json()["conclusion"] == "human note"


# ---------- Video URL guardrails (reject ephemeral tunnels on agent writes) ----------


def _vid(url: str) -> dict:
    return {"label": "clip", "duration": "0:05", "url": url}


async def test_mcp_agent_video_ephemeral_url_rejected(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "V", "deep": {"na": True}, "video": _vid("https://foo.trycloudflare.com/c.mp4")},
        headers=MCP,
    )
    assert r.status_code == 422, r.text
    assert "trycloudflare" in r.json()["detail"].lower()


async def test_mcp_agent_video_media_url_ok(client, project_id) -> None:
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "V", "deep": {"na": True}, "video": _vid("/media/lb/clip.mp4")},
        headers=MCP,
    )
    assert r.status_code == 201, r.text


async def test_http_agent_video_ephemeral_url_allowed(client, project_id) -> None:
    # The human (source=http) is never blocked.
    r = await client.post(
        f"/projects/{project_id}/cells",
        json={"kind": "agent", "title": "V", "video": _vid("https://x.trycloudflare.com/c.mp4")},
    )
    assert r.status_code == 201, r.text


async def test_mcp_update_setting_ephemeral_video_rejected(client, project_id) -> None:
    c = await _create_cell(client, project_id, title="A", deep={"na": True})
    r = await client.patch(
        f"/cells/{c['id']}",
        json={"video": _vid("https://x.ngrok.io/c.mp4")},
        headers=MCP,
    )
    assert r.status_code == 422, r.text
    assert "ngrok" in r.json()["detail"].lower()
