"""Shared Pydantic models for Field Notes (API <-> MCP <-> Web).

Defines the canonical data model: Project, Cell (agent | markdown | empty),
Verdict, Visual (data | vega | svg | sandbox), and request/response DTOs plus
the SSE EventEnvelope. Web TS types are generated from these in Chunk 3.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

__version__ = "0.1.0"


class CellStatus(str, Enum):
    in_progress = "in_progress"
    open = "open"
    verified = "verified"
    rejected = "rejected"


class CellKind(str, Enum):
    agent = "agent"
    markdown = "markdown"
    empty = "empty"


class VerdictState(str, Enum):
    accept = "accept"
    reject = "reject"


class Verdict(BaseModel):
    state: VerdictState
    note: str = ""
    by: str = "you"
    at: datetime


class MetricItem(BaseModel):
    k: str
    v: str
    d: str | None = None


class VisualData(BaseModel):
    kind: Literal["data"] = "data"
    chart: Literal["line", "sweep", "bar"]
    series: list[dict]


class VisualVega(BaseModel):
    kind: Literal["vega"] = "vega"
    spec: dict


class VisualSvg(BaseModel):
    kind: Literal["svg"] = "svg"
    source: str


class VisualSandbox(BaseModel):
    kind: Literal["sandbox"] = "sandbox"
    html: str = ""
    js: str = ""
    css: str = ""


Visual = Annotated[
    VisualData | VisualVega | VisualSvg | VisualSandbox,
    Field(discriminator="kind"),
]


class VideoSlot(BaseModel):
    label: str
    duration: str
    url: str | None = None


class DeepBlock(BaseModel):
    hparams: dict[str, str] = Field(default_factory=dict)
    files: list[str] = Field(default_factory=list)
    runs: list[dict] = Field(default_factory=list)
    logs: str = ""


UiFilter = Literal["all", "in_progress", "open", "verified", "rejected"]


class ProjectCreate(BaseModel):
    name: str
    subtitle: str | None = None
    repo: str | None = None


class ProjectRead(ProjectCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    ui_filter: UiFilter | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    subtitle: str | None = None
    repo: str | None = None
    ui_filter: UiFilter | None = None


class UiFilterSet(BaseModel):
    filter: UiFilter


class CellCreate(BaseModel):
    kind: CellKind
    after_cell_id: UUID | None = None
    title: str | None = None
    agent_id: str | None = None
    status: CellStatus | None = None
    conclusion: str | None = None
    metrics: list[MetricItem] | None = None
    visual: Visual | None = None
    video: VideoSlot | None = None
    deep: DeepBlock | None = None
    body: str | None = None


class CellUpdate(BaseModel):
    """Writable by agents via MCP. Verdict and locked are intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    agent_id: str | None = None
    status: CellStatus | None = None
    conclusion: str | None = None
    metrics: list[MetricItem] | None = None
    visual: Visual | None = None
    video: VideoSlot | None = None
    deep: DeepBlock | None = None
    body: str | None = None


class CellRead(BaseModel):
    id: UUID
    project_id: UUID
    kind: CellKind
    position: int
    created_at: datetime
    updated_at: datetime
    title: str | None = None
    agent_id: str | None = None
    status: CellStatus | None = None
    conclusion: str | None = None
    metrics: list[MetricItem] | None = None
    visual: Visual | None = None
    video: VideoSlot | None = None
    deep: DeepBlock | None = None
    verdict: Verdict | None = None
    locked: bool = False
    body: str | None = None


class VerdictSet(BaseModel):
    state: VerdictState
    note: str = ""


class ReorderRequest(BaseModel):
    direction: Literal["up", "down"] | None = None
    position: int | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> ReorderRequest:
        if (self.direction is None) == (self.position is None):
            raise ValueError("provide exactly one of direction|position")
        return self


class EventEnvelope(BaseModel):
    id: UUID
    at: datetime
    kind: str
    project_id: UUID | None = None
    cell_id: UUID | None = None
    payload: dict = Field(default_factory=dict)


__all__ = [
    "CellCreate",
    "CellKind",
    "CellRead",
    "CellStatus",
    "CellUpdate",
    "DeepBlock",
    "EventEnvelope",
    "MetricItem",
    "ProjectCreate",
    "ProjectRead",
    "ProjectUpdate",
    "ReorderRequest",
    "UiFilter",
    "UiFilterSet",
    "Verdict",
    "VerdictSet",
    "VerdictState",
    "VideoSlot",
    "Visual",
    "VisualData",
    "VisualSandbox",
    "VisualSvg",
    "VisualVega",
]
