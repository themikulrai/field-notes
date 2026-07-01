"""Projects CRUD."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from field_notes_schema import ProjectCreate, ProjectRead, ProjectUpdate, ReorderRequest, UiFilterSet
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key
from ..db import get_session
from ..models import Project
from ..services import (
    emit_event,
    project_counts_for,
    project_counts_map,
    project_to_read,
    schedule_publish,
)

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_api_key)])


def _source(request: Request) -> str:
    return request.headers.get("X-Field-Notes-Source", "http")


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    archived: Literal["active", "archived", "all"] = Query("active"),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectRead]:
    # Manual tab order first; created_at only as a stable tiebreaker.
    stmt = select(Project).order_by(Project.position, Project.created_at)
    if archived == "active":
        stmt = stmt.where(Project.archived.is_(False))
    elif archived == "archived":
        stmt = stmt.where(Project.archived.is_(True))
    result = await session.execute(stmt)
    projects = list(result.scalars().all())
    counts = await project_counts_map(session, [p.id for p in projects])
    return [project_to_read(p, counts.get(p.id)) for p in projects]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    # Append at the end of the manual order. max+1 (not count) so a gap left by a
    # deleted project never collides with an existing position.
    max_pos = (await session.execute(select(func.max(Project.position)))).scalar()
    next_pos = 0 if max_pos is None else max_pos + 1
    p = Project(id=uuid.uuid4(), name=body.name, subtitle=body.subtitle, repo=body.repo, position=next_pos)
    session.add(p)
    await session.flush()
    env = await emit_event(
        session,
        "project.created",
        project_id=p.id,
        payload={"name": p.name},
        source=_source(request),
    )
    await session.commit()
    await session.refresh(p)
    schedule_publish(env)
    return project_to_read(p, await project_counts_for(session, p.id))


@router.get("/{pid}", response_model=ProjectRead)
async def get_project(pid: uuid.UUID, session: AsyncSession = Depends(get_session)) -> ProjectRead:
    p = await session.get(Project, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project_to_read(p, await project_counts_for(session, p.id))


@router.patch("/{pid}", response_model=ProjectRead)
async def update_project(
    pid: uuid.UUID,
    body: ProjectUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    p = await session.get(Project, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)
    await session.flush()
    env = await emit_event(
        session,
        "project.updated",
        project_id=p.id,
        payload={"fields": list(data.keys())},
        source=_source(request),
    )
    await session.commit()
    await session.refresh(p)
    schedule_publish(env)
    return project_to_read(p, await project_counts_for(session, p.id))


@router.delete("/{pid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(pid: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session)) -> None:
    p = await session.get(Project, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    await session.delete(p)
    env = await emit_event(session, "project.deleted", project_id=pid, source=_source(request))
    await session.commit()
    schedule_publish(env)


@router.post("/{pid}/reorder", response_model=ProjectRead)
async def reorder_project(
    pid: uuid.UUID,
    body: ReorderRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    """Move a project in the manual tab order. Provide exactly one of `direction`
    ('up'|'down') or `position` (0-indexed). Renumbers all projects densely and
    broadcasts `project.reordered` (the web store reloads projects on project.*).
    """
    result = await session.execute(select(Project).order_by(Project.position, Project.created_at))
    projects = list(result.scalars().all())
    idx = next((i for i, p in enumerate(projects) if p.id == pid), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="project not found")
    if body.direction is not None:
        if body.direction == "up" and idx > 0:
            projects[idx - 1], projects[idx] = projects[idx], projects[idx - 1]
        elif body.direction == "down" and idx < len(projects) - 1:
            projects[idx], projects[idx + 1] = projects[idx + 1], projects[idx]
        # at a boundary: no-op
    else:
        assert body.position is not None
        target = max(0, min(body.position, len(projects) - 1))
        moved = projects.pop(idx)
        projects.insert(target, moved)
    # Renumber dense 0..N-1; projects have no unique-position constraint, so a
    # direct assignment is safe (no negative-parking dance needed).
    for i, p in enumerate(projects):
        if p.position != i:
            p.position = i
    await session.flush()
    moved_p = await session.get(Project, pid)
    assert moved_p is not None
    env = await emit_event(
        session,
        "project.reordered",
        project_id=pid,
        payload={"position": moved_p.position},
        source=_source(request),
    )
    await session.commit()
    await session.refresh(moved_p)
    schedule_publish(env)
    return project_to_read(moved_p, await project_counts_for(session, pid))


@router.get("/{pid}/cells", response_model=list)
async def list_cells(pid: uuid.UUID, session: AsyncSession = Depends(get_session)) -> list:
    from sqlalchemy.orm import selectinload

    from ..models import Cell
    from ..services import cell_to_read

    p = await session.get(Project, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    result = await session.execute(
        select(Cell).where(Cell.project_id == pid).order_by(Cell.position).options(selectinload(Cell.verdict))
    )
    cells = result.scalars().all()
    return [cell_to_read(c, c.verdict) for c in cells]


@router.post("/{pid}/ui-filter", response_model=ProjectRead)
async def set_ui_filter(
    pid: uuid.UUID,
    body: UiFilterSet,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    """Persist the project's UI filter and broadcast `ui.filter_changed`.

    The web Zustand store listens for this event over SSE and updates its
    filter pill. The MCP `set_filter` tool calls this endpoint.
    """
    p = await session.get(Project, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    p.ui_filter = body.filter
    await session.flush()
    env = await emit_event(
        session,
        "ui.filter_changed",
        project_id=p.id,
        payload={"filter": body.filter},
        source=_source(request),
    )
    await session.commit()
    await session.refresh(p)
    schedule_publish(env)
    return project_to_read(p, await project_counts_for(session, p.id))
