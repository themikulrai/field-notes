"""Projects CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from field_notes_schema import ProjectCreate, ProjectRead, ProjectUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key
from ..db import get_session
from ..models import Project
from ..services import emit_event, project_to_read, schedule_publish

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_api_key)])


def _source(request: Request) -> str:
    return request.headers.get("X-Field-Notes-Source", "http")


@router.get("", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ProjectRead]:
    result = await session.execute(select(Project).order_by(Project.created_at))
    return [project_to_read(p) for p in result.scalars().all()]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    p = Project(id=uuid.uuid4(), name=body.name, subtitle=body.subtitle, repo=body.repo)
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
    return project_to_read(p)


@router.get("/{pid}", response_model=ProjectRead)
async def get_project(pid: uuid.UUID, session: AsyncSession = Depends(get_session)) -> ProjectRead:
    p = await session.get(Project, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project_to_read(p)


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
    return project_to_read(p)


@router.delete("/{pid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(pid: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session)) -> None:
    p = await session.get(Project, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    await session.delete(p)
    env = await emit_event(session, "project.deleted", project_id=pid, source=_source(request))
    await session.commit()
    schedule_publish(env)


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
