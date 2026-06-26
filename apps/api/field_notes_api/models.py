"""SQLAlchemy 2.x async ORM models.

Cross-dialect by design: we use the portable `Uuid`, `DateTime(timezone=True)`,
and `JSON` types so the same models run against Postgres (production) and SQLite
(test fallback when Docker is unavailable). No `JSONB` operators or pg-only
features anywhere in the ORM layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "ui_filter IS NULL OR ui_filter IN ('all','in_progress','open','verified','rejected')",
            name="ck_projects_ui_filter",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ui_filter: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Manual left-to-right tab order (drag to reorder). Dense 0..N-1 at rest;
    # create_project appends at the end, /projects/{pid}/reorder renumbers.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    cells: Mapped[list[Cell]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Cell.position"
    )


class Cell(Base):
    __tablename__ = "cells"
    __table_args__ = (
        UniqueConstraint("project_id", "position", name="uq_cells_project_position"),
        CheckConstraint("kind IN ('agent','markdown','empty')", name="ck_cells_kind"),
        CheckConstraint(
            "status IS NULL OR status IN ('in_progress','open','verified','rejected','ready')",
            name="ck_cells_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    visual: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    video: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deep: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="cells")
    verdict: Mapped[VerdictRow | None] = relationship(
        back_populates="cell", cascade="all, delete-orphan", uselist=False
    )


class VerdictRow(Base):
    __tablename__ = "verdicts"
    __table_args__ = (CheckConstraint("state IN ('accept','reject')", name="ck_verdicts_state"),)

    cell_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cells.id", ondelete="CASCADE"), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    by: Mapped[str] = mapped_column(Text, nullable=False, default="you")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    cell: Mapped[Cell] = relationship(back_populates="verdict")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_project_at", "project_id", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    cell_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
