"""Cells CRUD + reorder.

Invariants enforced here (with tests in test_cells.py / test_verdicts.py):
- Cells of a project have dense, contiguous `position` values 0..N-1 at rest.
- A locked cell rejects PATCH/DELETE with 409.
- Markdown cells reject agent fields at create time. Empty cells reject any
  payload fields besides `kind` and `after_cell_id` and default status="open".

Reorder strategy: load all rows for the project in a single transaction
(`with session.begin()` implied by FastAPI dep + explicit commit), rewrite
positions in a deterministic order, commit once. This is O(N) per reorder
which is fine for the cell counts a research notebook ever hits.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from field_notes_schema import (
    AppendSandboxBody,
    CellCreate,
    CellKind,
    CellRead,
    CellStatus,
    CellUpdate,
    PatchVisualSandboxRequest,
    ReorderRequest,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key
from ..db import get_session
from ..models import Cell, Project
from ..services import cell_to_read, emit_event, load_cell_full, schedule_publish

router = APIRouter(tags=["cells"], dependencies=[Depends(require_api_key)])


def _source(request: Request) -> str:
    return request.headers.get("X-Field-Notes-Source", "http")


def _validate_cell_payload(body: CellCreate) -> None:
    """Server-side enforcement of per-kind field rules."""
    if body.kind == CellKind.markdown:
        offenders = [
            f
            for f in ("title", "agent_id", "status", "conclusion", "metrics", "visual", "video", "deep")
            if getattr(body, f) is not None
        ]
        if offenders:
            raise HTTPException(
                status_code=422,
                detail=f"markdown cells may not set agent fields: {offenders}",
            )
    elif body.kind == CellKind.empty:
        offenders = [
            f
            for f in (
                "title",
                "agent_id",
                "conclusion",
                "metrics",
                "visual",
                "video",
                "deep",
                "body",
            )
            if getattr(body, f) is not None
        ]
        if offenders:
            raise HTTPException(
                status_code=422,
                detail=f"empty cells may not set any payload fields: {offenders}",
            )
    else:  # agent
        if body.body is not None:
            raise HTTPException(status_code=422, detail="agent cells may not set `body` (markdown only)")


# Deep-block (hparams/files/runs/logs) is how the human audits an agent cell, so
# agent cells written by agents (source=mcp) must carry one — or be flagged
# not-applicable. It must also stay SMALL so the notebook is fast to read; these
# caps reject a data-dump and ask the agent to summarize. Enforcement is scoped
# to source=mcp: the human (source=http) is never blocked.
DEEP_MAX_HPARAMS = 24
DEEP_MAX_KV_CHARS = 120  # key + value, per hparam
DEEP_MAX_FILES = 24
DEEP_MAX_RUNS = 12
DEEP_MAX_LOG_CHARS = 1500


def _deep_filled(deep: dict | None) -> bool:
    """A deep block counts as 'filled' if na=True or any of the four parts has content."""
    if not deep:
        return False
    if deep.get("na") is True:
        return True
    return bool(deep.get("hparams") or deep.get("files") or deep.get("runs") or deep.get("logs"))


def _validate_deep_size(deep: dict | None) -> None:
    if not deep:
        return
    hp = deep.get("hparams") or {}
    if len(hp) > DEEP_MAX_HPARAMS:
        raise HTTPException(
            status_code=422,
            detail=f"deep.hparams has {len(hp)} entries; keep it ≤ {DEEP_MAX_HPARAMS} — list only the key config",
        )
    for k, val in hp.items():
        if len(str(k)) + len(str(val)) > DEEP_MAX_KV_CHARS:
            raise HTTPException(
                status_code=422,
                detail=f"deep.hparams['{k}'] is too long (>{DEEP_MAX_KV_CHARS} chars key+value) — summarize it",
            )
    files = deep.get("files") or []
    if len(files) > DEEP_MAX_FILES:
        raise HTTPException(
            status_code=422,
            detail=f"deep.files has {len(files)} entries; keep it ≤ {DEEP_MAX_FILES} — list only the key paths",
        )
    runs = deep.get("runs") or []
    if len(runs) > DEEP_MAX_RUNS:
        raise HTTPException(
            status_code=422,
            detail=f"deep.runs has {len(runs)} entries; keep it ≤ {DEEP_MAX_RUNS}",
        )
    logs = deep.get("logs") or ""
    if len(logs) > DEEP_MAX_LOG_CHARS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"deep.logs is {len(logs)} chars; keep it ≤ {DEEP_MAX_LOG_CHARS} — "
                "paste only the salient metric/stdout lines"
            ),
        )


def _enforce_agent_deep(deep: dict | None, source: str) -> None:
    """For MCP-sourced agent cells: deep must be present (or na) and within caps.

    No-op for source=http so a human web edit is never blocked.
    """
    if source != "mcp":
        return
    _validate_deep_size(deep)
    if not _deep_filled(deep):
        raise HTTPException(
            status_code=422,
            detail=(
                "agent cells must include a deep block (hparams/files/runs/logs) or set deep.na=true — "
                "it is how the human audits the work"
            ),
        )


async def _project_cells_ordered(session: AsyncSession, pid: uuid.UUID) -> list[Cell]:
    result = await session.execute(select(Cell).where(Cell.project_id == pid).order_by(Cell.position))
    return list(result.scalars().all())


async def _renumber(session: AsyncSession, cells: list[Cell]) -> None:
    """Renumber `cells` to positions 0..N-1 in current list order, touching ONLY
    rows whose position actually changes.

    Why this matters: SQLAlchemy's `onupdate=func.now()` bumps `updated_at` on
    every row whose mapped attributes are set, even to the same value with
    `position`. The verdict-staleness signal (`cell.updated_at > verdict.at`)
    relies on `updated_at` being touched only when the user edits a cell —
    bumping it on unrelated cells during a neighbour's reorder/delete poisons
    that signal.

    Strategy: identify the contiguous "dirty" subset (cells whose position !=
    target). Park them at distinct negative positions, flush, then assign final
    positions and flush. This keeps the unique constraint satisfied on backends
    (SQLite) that check it row-by-row instead of at statement end.
    """
    dirty: list[tuple[Cell, int]] = [(c, i) for i, c in enumerate(cells) if c.position != i]
    if not dirty:
        return
    for j, (c, _) in enumerate(dirty):
        c.position = -(j + 1) - 10_000_000
    await session.flush()
    for c, target in dirty:
        c.position = target
    await session.flush()


@router.post("/projects/{pid}/cells", response_model=CellRead, status_code=status.HTTP_201_CREATED)
async def create_cell(
    pid: uuid.UUID,
    body: CellCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CellRead:
    p = await session.get(Project, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    _validate_cell_payload(body)
    if body.kind == CellKind.agent:
        _enforce_agent_deep(body.deep.model_dump() if body.deep is not None else None, _source(request))

    cells = await _project_cells_ordered(session, pid)
    if body.after_cell_id is None:
        insert_at = len(cells)
    else:
        idx = next((i for i, c in enumerate(cells) if c.id == body.after_cell_id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail="after_cell_id not in project")
        insert_at = idx + 1

    # Default status for empty cells; agent status passes through.
    # MCP-sourced writes are server-pinned to "open" — any agent edit re-opens
    # the cell, regardless of what `body.status` (or kind) wanted. This is the
    # invariant; cell status reflects review state, not agent self-reporting.
    status_value: str | None
    if _source(request) == "mcp":
        status_value = CellStatus.open.value
    elif body.kind == CellKind.empty:
        status_value = CellStatus.open.value
    else:
        status_value = body.status.value if body.status is not None else None

    new_cell = Cell(
        id=uuid.uuid4(),
        project_id=pid,
        kind=body.kind.value,
        position=0,  # placeholder, finalized in renumber
        title=body.title,
        agent_id=body.agent_id,
        status=status_value,
        conclusion=body.conclusion,
        metrics=[m.model_dump() for m in body.metrics] if body.metrics is not None else None,
        visual=body.visual.model_dump() if body.visual is not None else None,
        video=body.video.model_dump() if body.video is not None else None,
        deep=body.deep.model_dump() if body.deep is not None else None,
        body=body.body,
    )
    cells.insert(insert_at, new_cell)
    session.add(new_cell)
    await _renumber(session, cells)
    env = await emit_event(
        session,
        "cell.created",
        project_id=pid,
        cell_id=new_cell.id,
        payload={"kind": new_cell.kind, "position": new_cell.position},
        source=_source(request),
    )
    await session.commit()
    schedule_publish(env)
    fresh = await load_cell_full(session, new_cell.id)
    assert fresh is not None
    return cell_to_read(fresh, fresh.verdict)


@router.get("/cells/{cid}", response_model=CellRead)
async def get_cell(cid: uuid.UUID, session: AsyncSession = Depends(get_session)) -> CellRead:
    c = await load_cell_full(session, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="cell not found")
    return cell_to_read(c, c.verdict)


@router.patch("/cells/{cid}", response_model=CellRead)
async def update_cell(
    cid: uuid.UUID,
    body: CellUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CellRead:
    c = await session.get(Cell, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="cell not found")
    if c.locked:
        raise HTTPException(status_code=409, detail="cell is locked")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "metrics" and v is not None:
            c.metrics = v  # already plain dicts from model_dump
        elif k == "visual" and v is not None:
            # Deep-merge sandbox-on-sandbox so PATCH with only `html` does not
            # clobber existing `js`/`css` (VisualSandbox schema defaults them
            # to "" — indistinguishable from "not provided"). For any other
            # case (kind change, non-sandbox), replace as before.
            existing = c.visual
            if (
                isinstance(existing, dict)
                and existing.get("kind") == "sandbox"
                and isinstance(v, dict)
                and v.get("kind") == "sandbox"
            ):
                merged = dict(existing)
                for vk, vv in v.items():
                    if vk == "kind":
                        continue
                    # Treat "" as "not provided" since it's the schema default
                    # and indistinguishable from an unset field.
                    if isinstance(vv, str) and vv == "":
                        continue
                    merged[vk] = vv
                merged["kind"] = "sandbox"
                c.visual = merged
            else:
                c.visual = v
        elif k in ("video", "deep") and v is not None:
            setattr(c, k, v)
        elif k == "status" and v is not None:
            c.status = v.value if hasattr(v, "value") else v
        else:
            setattr(c, k, v)
    # Mandatory deep block on MCP-sourced agent-cell edits (no-op for http/human).
    # Checks the MERGED result, so an edit that doesn't touch an already-filled
    # deep passes, and one that leaves it empty is rejected.
    if c.kind == CellKind.agent.value:
        _enforce_agent_deep(c.deep, _source(request))
    # Server-side invariant: any MCP-sourced edit re-opens the cell. Applies
    # after all field merges so it overrides any explicit `status` in the patch
    # as well as any "no status field at all" case. Verdict relationship is
    # intentionally untouched — only the cell's own status flips.
    if _source(request) == "mcp":
        c.status = CellStatus.open.value
    await session.flush()
    env = await emit_event(
        session,
        "cell.updated",
        project_id=c.project_id,
        cell_id=c.id,
        payload={"fields": list(data.keys())},
        source=_source(request),
    )
    await session.commit()
    schedule_publish(env)
    fresh = await load_cell_full(session, cid)
    assert fresh is not None
    return cell_to_read(fresh, fresh.verdict)


@router.post("/cells/{cid}/visual-sandbox/patch", response_model=CellRead)
async def patch_visual_sandbox(
    cid: uuid.UUID,
    body: PatchVisualSandboxRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CellRead:
    """Substring-replace inside a cell's visual.sandbox.{html,js,css}.

    Exists so agents don't have to retransmit the entire sandbox to do a small
    edit — the MCP tool-call channel silently truncates large inputs to `{}`.
    """
    c = await session.get(Cell, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="cell not found")
    if c.locked:
        raise HTTPException(status_code=409, detail="cell is locked")
    if not isinstance(c.visual, dict) or c.visual.get("kind") != "sandbox":
        raise HTTPException(status_code=422, detail="cell has no visual.sandbox")
    current = c.visual.get(body.target, "")
    if not isinstance(current, str):
        raise HTTPException(status_code=422, detail=f"visual.sandbox.{body.target} is not a string")
    actual = current.count(body.find)
    if actual != body.expected_count:
        raise HTTPException(
            status_code=422,
            detail=(
                f"`find` appears {actual} time(s) in visual.sandbox.{body.target}, "
                f"expected_count={body.expected_count}"
            ),
        )
    new_visual = dict(c.visual)
    new_visual[body.target] = current.replace(body.find, body.replace)
    c.visual = new_visual
    await session.flush()
    env = await emit_event(
        session,
        "cell.updated",
        project_id=c.project_id,
        cell_id=c.id,
        payload={"fields": ["visual"], "patch": {"target": body.target, "count": actual}},
        source=_source(request),
    )
    await session.commit()
    schedule_publish(env)
    fresh = await load_cell_full(session, cid)
    assert fresh is not None
    return cell_to_read(fresh, fresh.verdict)


@router.post("/cells/{cid}/visual-sandbox/append", response_model=CellRead)
async def append_visual_sandbox(
    cid: uuid.UUID,
    body: AppendSandboxBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CellRead:
    """Append a chunk to a cell's visual.sandbox.{html,js,css}.

    Workaround for the MCP tool-call channel clamping inputs at ~50 KB — the
    agent builds large sandboxes in pieces. `seq` MUST equal the current count
    of chunks already appended for that target (so the first append for a
    target uses seq=0). The counter lives in `c.visual["_chunks"]` and is
    cleared on `finalize=True`, which also flips status→"open" so the finished
    cell re-enters the review queue — the same invariant every other content
    write obeys (see `create_cell`/`update_cell`): agent writes never
    self-report a review state. (Historically finalize set status="ready", a
    value the web UI never learned to render; it white-screened the whole
    project. See migration 0004 and the `statusMeta` fallback in the web app.)
    """
    c = await session.get(Cell, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="cell not found")
    if c.locked:
        raise HTTPException(status_code=409, detail="cell is locked")

    if c.visual is None:
        new_visual: dict = {"kind": "sandbox", "html": "", "js": "", "css": "", "_chunks": {}}
    elif isinstance(c.visual, dict) and c.visual.get("kind") == "sandbox":
        new_visual = dict(c.visual)
        new_visual.setdefault("html", "")
        new_visual.setdefault("js", "")
        new_visual.setdefault("css", "")
        new_visual.setdefault("_chunks", {})
        # ensure _chunks is a dict (defensive against external writes)
        if not isinstance(new_visual["_chunks"], dict):
            new_visual["_chunks"] = {}
        else:
            new_visual["_chunks"] = dict(new_visual["_chunks"])
    else:
        raise HTTPException(
            status_code=422,
            detail="cell has a non-sandbox visual; cannot append sandbox chunks",
        )

    expected_seq = int(new_visual["_chunks"].get(body.target, 0))
    if body.seq != expected_seq:
        raise HTTPException(
            status_code=422,
            detail=(
                f"seq mismatch for target {body.target}: got seq={body.seq}, "
                f"expected seq={expected_seq} (chunks already appended)"
            ),
        )

    current = new_visual.get(body.target, "")
    if not isinstance(current, str):
        raise HTTPException(status_code=422, detail=f"visual.sandbox.{body.target} is not a string")
    new_visual[body.target] = current + body.chunk
    new_visual["_chunks"][body.target] = expected_seq + 1

    if body.finalize:
        new_visual.pop("_chunks", None)
        # A finalized sandbox is a content write like any other: route it back
        # to "open" (needs review), never the deprecated agent-self-reported
        # "ready". This keeps status/verdict in sync and the cell visible in
        # the review queue.
        c.status = CellStatus.open.value

    c.visual = new_visual
    await session.flush()
    env = await emit_event(
        session,
        "cell.updated",
        project_id=c.project_id,
        cell_id=c.id,
        payload={
            "fields": ["visual"] + (["status"] if body.finalize else []),
            "append": {"target": body.target, "seq": body.seq, "finalize": body.finalize},
        },
        source=_source(request),
    )
    await session.commit()
    schedule_publish(env)
    fresh = await load_cell_full(session, cid)
    assert fresh is not None
    return cell_to_read(fresh, fresh.verdict)


@router.delete("/cells/{cid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cell(cid: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session)) -> None:
    c = await session.get(Cell, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="cell not found")
    if c.locked:
        raise HTTPException(status_code=409, detail="cell is locked")
    pid = c.project_id
    await session.delete(c)
    await session.flush()
    cells = await _project_cells_ordered(session, pid)
    await _renumber(session, cells)
    env = await emit_event(
        session,
        "cell.deleted",
        project_id=pid,
        cell_id=cid,
        source=_source(request),
    )
    await session.commit()
    schedule_publish(env)


@router.post("/cells/{cid}/reorder", response_model=CellRead)
async def reorder_cell(
    cid: uuid.UUID,
    body: ReorderRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CellRead:
    c = await session.get(Cell, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="cell not found")
    cells = await _project_cells_ordered(session, c.project_id)
    idx = next(i for i, x in enumerate(cells) if x.id == cid)
    if body.direction is not None:
        if body.direction == "up" and idx > 0:
            cells[idx - 1], cells[idx] = cells[idx], cells[idx - 1]
        elif body.direction == "down" and idx < len(cells) - 1:
            cells[idx], cells[idx + 1] = cells[idx + 1], cells[idx]
        # at boundary: no-op
    else:
        assert body.position is not None
        target = max(0, min(body.position, len(cells) - 1))
        moved = cells.pop(idx)
        cells.insert(target, moved)
    await _renumber(session, cells)
    env = await emit_event(
        session,
        "cell.reordered",
        project_id=c.project_id,
        cell_id=c.id,
        payload={"position": c.position},
        source=_source(request),
    )
    await session.commit()
    schedule_publish(env)
    fresh = await load_cell_full(session, cid)
    assert fresh is not None
    return cell_to_read(fresh, fresh.verdict)
