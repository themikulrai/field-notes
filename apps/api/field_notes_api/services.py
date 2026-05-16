"""Helpers shared by routers: event emission, cell↔Pydantic mapping."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime
from typing import Any

from field_notes_schema import (
    CellRead,
    EventEnvelope,
    ProjectRead,
    Verdict,
    VerdictState,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .events_bus import bus
from .models import Cell, Event, Project, VerdictRow


async def emit_event(
    session: AsyncSession,
    kind: str,
    *,
    project_id: uuid.UUID | None = None,
    cell_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    source: str = "http",
) -> EventEnvelope:
    """Insert an audit row + schedule a fire-and-forget broadcast on the bus.

    The bus.publish is dispatched as a background asyncio task AFTER session.commit
    so subscribers never see events for a write that ended up rolled back.
    """
    payload = dict(payload or {})
    payload.setdefault("source", source)
    row = Event(
        id=uuid.uuid4(),
        at=datetime.now(UTC),
        kind=kind,
        project_id=project_id,
        cell_id=cell_id,
        payload=payload,
    )
    session.add(row)
    await session.flush()
    env = EventEnvelope(
        id=row.id,
        at=row.at,
        kind=kind,
        project_id=project_id,
        cell_id=cell_id,
        payload=payload,
    )
    return env


def schedule_publish(env: EventEnvelope) -> None:
    """Fire-and-forget bus.publish; safe to call from any async context."""
    # No running loop -> sync test context; the publish is harmless to skip.
    with contextlib.suppress(RuntimeError):
        asyncio.create_task(bus.publish(env))


async def load_cell_full(session: AsyncSession, cid: uuid.UUID) -> Cell | None:
    """Fetch a cell with its verdict relationship eager-loaded.

    Use this in response paths after a commit — `session.refresh` with partial
    attribute names leaves other columns expired (e.g. `updated_at` which has
    `onupdate=func.now()`), and accessing them later from an async session
    triggers a sync load and a MissingGreenlet error.
    """
    result = await session.execute(select(Cell).where(Cell.id == cid).options(selectinload(Cell.verdict)))
    return result.scalars().first()


async def load_project_full(session: AsyncSession, pid: uuid.UUID) -> Project | None:
    result = await session.execute(select(Project).where(Project.id == pid))
    return result.scalars().first()


def project_to_read(p: Project) -> ProjectRead:
    return ProjectRead(
        id=p.id,
        name=p.name,
        subtitle=p.subtitle,
        repo=p.repo,
        created_at=p.created_at,
        updated_at=p.updated_at,
        ui_filter=p.ui_filter,
    )


def cell_to_read(c: Cell, v: VerdictRow | None = None) -> CellRead:
    verdict = Verdict(state=VerdictState(v.state), note=v.note, by=v.by, at=v.at) if v is not None else None
    return CellRead(
        id=c.id,
        project_id=c.project_id,
        kind=c.kind,
        position=c.position,
        created_at=c.created_at,
        updated_at=c.updated_at,
        title=c.title,
        agent_id=c.agent_id,
        status=c.status,
        conclusion=c.conclusion,
        metrics=c.metrics,
        visual=c.visual,
        video=c.video,
        deep=c.deep,
        verdict=verdict,
        locked=c.locked,
        body=c.body,
    )
