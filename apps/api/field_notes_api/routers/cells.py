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


async def _project_cells_ordered(session: AsyncSession, pid: uuid.UUID) -> list[Cell]:
    result = await session.execute(select(Cell).where(Cell.project_id == pid).order_by(Cell.position))
    return list(result.scalars().all())


async def _renumber(session: AsyncSession, cells: list[Cell]) -> None:
    """Stable renumber to 0..N-1 in current list order. Avoids unique-constraint
    collisions by first parking everything at large negative positions, then
    assigning final positions."""
    for i, c in enumerate(cells):
        c.position = -(i + 1) - 10_000_000
    await session.flush()
    for i, c in enumerate(cells):
        c.position = i
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

    cells = await _project_cells_ordered(session, pid)
    if body.after_cell_id is None:
        insert_at = len(cells)
    else:
        idx = next((i for i, c in enumerate(cells) if c.id == body.after_cell_id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail="after_cell_id not in project")
        insert_at = idx + 1

    # Default status for empty cells; agent status passes through.
    status_value: str | None
    if body.kind == CellKind.empty:
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
        elif k in ("visual", "video", "deep") and v is not None:
            setattr(c, k, v)
        elif k == "status" and v is not None:
            c.status = v.value if hasattr(v, "value") else v
        else:
            setattr(c, k, v)
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
