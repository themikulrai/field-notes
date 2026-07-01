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
    # DEPRECATED. `ready` was once set by append_visual_sandbox(finalize=True)
    # to signal a finalized chunked build, but no code ever consumed it and the
    # web UI never rendered it (it white-screened the project — see migration
    # 0004). finalize now sets "open" like every other content write. The value
    # is retained only so the DB CHECK constraint stays valid and any legacy
    # rows remain loadable; nothing emits it. Do not use for new code.
    ready = "ready"


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
    # MIME type for the <source> element (e.g. "video/mp4"). The web defaults to
    # "video/mp4" when absent; included here so the Python schema matches the TS
    # type and round-trips it.
    mime: str | None = None


class DeepBlock(BaseModel):
    hparams: dict[str, str] = Field(default_factory=dict)
    files: list[str] = Field(default_factory=list)
    runs: list[dict] = Field(default_factory=list)
    logs: str = ""
    # Explicit "not applicable" escape: set na=True on agent cells that genuinely
    # have no hyperparameters/runs (e.g. a pure analysis or summary), so the
    # mandatory-deep check passes without inventing fake content.
    na: bool = False


UiFilter = Literal["all", "in_progress", "open", "verified", "rejected"]


class ProjectCreate(BaseModel):
    name: str
    subtitle: str | None = None
    repo: str | None = None


class ProjectCounts(BaseModel):
    in_progress: int = 0
    open: int = 0
    verified: int = 0
    rejected: int = 0


class ProjectRead(ProjectCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    ui_filter: UiFilter | None = None
    position: int = 0
    archived: bool = False
    counts: ProjectCounts = Field(default_factory=ProjectCounts)


class ProjectUpdate(BaseModel):
    name: str | None = None
    subtitle: str | None = None
    repo: str | None = None
    ui_filter: UiFilter | None = None
    archived: bool | None = None


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


class PatchVisualSandboxRequest(BaseModel):
    target: Literal["html", "js", "css"]
    find: str = Field(min_length=1)
    replace: str
    # Pre-check that `find` appears exactly this many times. Defaults to 1 so the
    # agent must consciously opt-in to multi-replace by setting expected_count
    # (or the value it just saw in get_cell). Mismatch → 422 with actual count.
    expected_count: int = Field(default=1, ge=1)


class AppendSandboxBody(BaseModel):
    """Append a small chunk to a cell's visual.sandbox.{html,js,css}.

    Exists because the MCP tool-call channel clamps inputs at ~50 KB, so large
    sandboxes have to be built up in small pieces. `seq` is an ordering guard:
    it must equal the number of chunks already appended for that target (so the
    first append uses seq=0). On `finalize=True`, the cell transitions to
    status="ready" and the per-target chunk counters are cleared.
    """

    target: Literal["html", "js", "css"]
    chunk: str
    seq: int = Field(ge=0)
    finalize: bool = False


class EventEnvelope(BaseModel):
    id: UUID
    at: datetime
    kind: str
    project_id: UUID | None = None
    cell_id: UUID | None = None
    payload: dict = Field(default_factory=dict)


__all__ = [
    "AppendSandboxBody",
    "CellCreate",
    "CellKind",
    "CellRead",
    "CellStatus",
    "CellUpdate",
    "DeepBlock",
    "EventEnvelope",
    "MetricItem",
    "PatchVisualSandboxRequest",
    "ProjectCounts",
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
