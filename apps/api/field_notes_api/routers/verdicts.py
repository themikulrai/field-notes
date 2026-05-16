"""Verdicts + lock/unlock."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from field_notes_schema import CellRead, CellStatus, VerdictSet, VerdictState
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key
from ..db import get_session
from ..models import VerdictRow
from ..services import cell_to_read, emit_event, load_cell_full, schedule_publish

router = APIRouter(tags=["verdicts"], dependencies=[Depends(require_api_key)])


def _source(request: Request) -> str:
    return request.headers.get("X-Field-Notes-Source", "http")


@router.post("/cells/{cid}/verdict", response_model=CellRead)
async def set_or_clear_verdict(
    cid: uuid.UUID,
    request: Request,
    body: VerdictSet | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
) -> CellRead:
    """body=null clears the verdict; otherwise sets it.

    Locked cells reject any verdict change with 409 — unlock first.
    """
    c = await load_cell_full(session, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="cell not found")
    if c.locked:
        raise HTTPException(status_code=409, detail="cell is locked")

    if body is None:
        if c.verdict is not None:
            v = c.verdict
            c.verdict = None  # break the relationship cache before delete
            await session.delete(v)
            await session.flush()
        if c.status in (CellStatus.verified.value, CellStatus.rejected.value):
            c.status = CellStatus.open.value
        env = await emit_event(
            session,
            "verdict.cleared",
            project_id=c.project_id,
            cell_id=c.id,
            source=_source(request),
        )
        await session.commit()
        schedule_publish(env)
        fresh = await load_cell_full(session, cid)
        assert fresh is not None
        return cell_to_read(fresh, fresh.verdict)

    if c.verdict is None:
        new_v = VerdictRow(
            cell_id=c.id,
            state=body.state.value,
            note=body.note,
            by="you",
            at=datetime.now(UTC),
        )
        # Assign via relationship so the cached Cell.verdict back-populates and
        # subsequent reads in this session see the new row.
        c.verdict = new_v
    else:
        c.verdict.state = body.state.value
        c.verdict.note = body.note
        c.verdict.at = datetime.now(UTC)
    c.status = CellStatus.verified.value if body.state == VerdictState.accept else CellStatus.rejected.value
    await session.flush()
    env = await emit_event(
        session,
        "verdict.set",
        project_id=c.project_id,
        cell_id=c.id,
        payload={"state": body.state.value},
        source=_source(request),
    )
    await session.commit()
    schedule_publish(env)
    fresh = await load_cell_full(session, cid)
    assert fresh is not None
    return cell_to_read(fresh, fresh.verdict)


@router.post("/cells/{cid}/lock", response_model=CellRead)
async def lock_cell(cid: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session)) -> CellRead:
    c = await load_cell_full(session, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="cell not found")
    if c.verdict is None or c.verdict.state != VerdictState.accept.value:
        raise HTTPException(status_code=409, detail="cell must have an accept verdict to be locked")
    c.locked = True
    await session.flush()
    env = await emit_event(
        session,
        "cell.locked",
        project_id=c.project_id,
        cell_id=c.id,
        source=_source(request),
    )
    await session.commit()
    schedule_publish(env)
    fresh = await load_cell_full(session, cid)
    assert fresh is not None
    return cell_to_read(fresh, fresh.verdict)


@router.post("/cells/{cid}/unlock", response_model=CellRead)
async def unlock_cell(cid: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session)) -> CellRead:
    c = await load_cell_full(session, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="cell not found")
    c.locked = False
    await session.flush()
    env = await emit_event(
        session,
        "cell.unlocked",
        project_id=c.project_id,
        cell_id=c.id,
        source=_source(request),
    )
    await session.commit()
    schedule_publish(env)
    fresh = await load_cell_full(session, cid)
    assert fresh is not None
    return cell_to_read(fresh, fresh.verdict)
