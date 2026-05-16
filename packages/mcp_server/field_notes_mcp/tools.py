"""MCP tool surface — the agent's writable view of Field Notes.

Design notes
------------
* This is the **agent's** view. The human's authority — `set_verdict`,
  `lock_cell`, `unlock_cell` — is deliberately absent. A guardrail test
  (`tests/test_no_verdict_writes.py`) enforces this.
* Each tool takes an explicit Pydantic input model so FastMCP can generate
  accurate JSON Schema for the agent.
* Tools return JSON-compatible dicts (Pydantic objects via `model_dump(mode="json")`).
* `update_cell` and `delete_cell` translate 409 into a structured error dict
  `{"error": "locked_cell", "message": "..."}` so the agent can recover.

Transport-agnostic: `register_tools(mcp, get_client)` is called by both stdio
and HTTP entrypoints, where `get_client` is a zero-arg callable returning the
shared FieldNotesClient. Using a callable (not a captured instance) lets tests
swap the client mid-process if they need to.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID

from field_notes_schema import (
    CellCreate,
    CellKind,
    CellStatus,
    CellUpdate,
    DeepBlock,
    MetricItem,
    ProjectCreate,
    ProjectUpdate,
    ReorderRequest,
    UiFilter,
    UiFilterSet,
    VideoSlot,
    Visual,
)
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .client import FieldNotesClient, LockedCellError

# --- public list of tool names — used by the guardrail test ----------
TOOL_NAMES: list[str] = [
    "list_projects",
    "get_project",
    "create_project",
    "update_project",
    "delete_project",
    "list_cells",
    "get_cell",
    "create_cell",
    "update_cell",
    "reorder_cell",
    "delete_cell",
    "set_filter",
    "get_feedback",
    "tail_events",
]

# Tools that MUST NOT exist on the agent's surface. Guardrail test asserts these
# are not present in the registered FastMCP tool registry.
HUMAN_ONLY_TOOLS: list[str] = ["set_verdict", "lock_cell", "unlock_cell"]


# ----------------- input models -----------------


class _ProjectId(BaseModel):
    project_id: UUID


class _CellId(BaseModel):
    cell_id: UUID


class CreateProjectInput(BaseModel):
    name: str
    subtitle: str | None = None
    repo: str | None = None


class UpdateProjectInput(BaseModel):
    project_id: UUID
    name: str | None = None
    subtitle: str | None = None
    repo: str | None = None


class ListCellsInput(BaseModel):
    project_id: UUID
    status: CellStatus | None = None
    kind: CellKind | None = None
    locked: bool | None = None


class CreateCellInput(BaseModel):
    """All CellCreate fields explicitly mirrored so FastMCP can emit a flat schema."""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID
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


class UpdateCellInput(BaseModel):
    """Mirrors CellUpdate — verdict and locked are NOT here by design."""

    model_config = ConfigDict(extra="forbid")

    cell_id: UUID
    title: str | None = None
    agent_id: str | None = None
    status: CellStatus | None = None
    conclusion: str | None = None
    metrics: list[MetricItem] | None = None
    visual: Visual | None = None
    video: VideoSlot | None = None
    deep: DeepBlock | None = None
    body: str | None = None


class ReorderCellInput(BaseModel):
    cell_id: UUID
    direction: Literal["up", "down"] | None = None
    position: int | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> ReorderCellInput:
        if (self.direction is None) == (self.position is None):
            raise ValueError("provide exactly one of direction|position")
        return self


class SetFilterInput(BaseModel):
    project_id: UUID
    filter: UiFilter


class GetFeedbackInput(BaseModel):
    project_id: UUID | None = None


class TailEventsInput(BaseModel):
    project_id: UUID | None = None
    limit: int = Field(default=50, ge=1, le=500)


# ----------------- error shape -----------------


def _locked_cell_error(err: LockedCellError) -> dict[str, str]:
    return {
        "error": "locked_cell",
        "cell_id": err.cell_id,
        "message": (
            f"Cell {err.cell_id} is locked by the human. Modifications are blocked. "
            "Use get_cell to read the current state."
        ),
    }


# ----------------- tool bodies (transport-agnostic) -----------------


async def t_list_projects(client: FieldNotesClient) -> list[dict[str, Any]]:
    projects = await client.list_projects()
    return [p.model_dump(mode="json") for p in projects]


async def t_get_project(client: FieldNotesClient, params: _ProjectId) -> dict[str, Any]:
    p = await client.get_project(params.project_id)
    return p.model_dump(mode="json")


async def t_create_project(client: FieldNotesClient, params: CreateProjectInput) -> dict[str, Any]:
    p = await client.create_project(ProjectCreate(**params.model_dump()))
    return p.model_dump(mode="json")


async def t_update_project(client: FieldNotesClient, params: UpdateProjectInput) -> dict[str, Any]:
    payload = params.model_dump(exclude_unset=True)
    payload.pop("project_id", None)
    p = await client.update_project(params.project_id, ProjectUpdate(**payload))
    return p.model_dump(mode="json")


async def t_delete_project(client: FieldNotesClient, params: _ProjectId) -> dict[str, str]:
    await client.delete_project(params.project_id)
    return {"deleted": str(params.project_id)}


async def t_list_cells(client: FieldNotesClient, params: ListCellsInput) -> list[dict[str, Any]]:
    cells = await client.list_cells(params.project_id)
    out = cells
    if params.status is not None:
        out = [c for c in out if c.status == params.status]
    if params.kind is not None:
        out = [c for c in out if c.kind == params.kind]
    if params.locked is not None:
        out = [c for c in out if c.locked == params.locked]
    return [c.model_dump(mode="json") for c in out]


async def t_get_cell(client: FieldNotesClient, params: _CellId) -> dict[str, Any]:
    c = await client.get_cell(params.cell_id)
    return c.model_dump(mode="json")


async def t_create_cell(client: FieldNotesClient, params: CreateCellInput) -> dict[str, Any]:
    payload = params.model_dump(exclude_unset=True)
    payload.pop("project_id", None)
    c = await client.create_cell(params.project_id, CellCreate(**payload))
    return c.model_dump(mode="json")


async def t_update_cell(client: FieldNotesClient, params: UpdateCellInput) -> dict[str, Any]:
    payload = params.model_dump(exclude_unset=True)
    payload.pop("cell_id", None)
    try:
        c = await client.update_cell(params.cell_id, CellUpdate(**payload))
    except LockedCellError as err:
        return _locked_cell_error(err)
    return c.model_dump(mode="json")


async def t_reorder_cell(client: FieldNotesClient, params: ReorderCellInput) -> dict[str, Any]:
    body = ReorderRequest(direction=params.direction, position=params.position)
    try:
        c = await client.reorder_cell(params.cell_id, body)
    except LockedCellError as err:
        return _locked_cell_error(err)
    return c.model_dump(mode="json")


async def t_delete_cell(client: FieldNotesClient, params: _CellId) -> dict[str, str]:
    try:
        await client.delete_cell(params.cell_id)
    except LockedCellError as err:
        return _locked_cell_error(err)
    return {"deleted": str(params.cell_id)}


async def t_set_filter(client: FieldNotesClient, params: SetFilterInput) -> dict[str, Any]:
    p = await client.set_ui_filter(params.project_id, UiFilterSet(filter=params.filter))
    return p.model_dump(mode="json")


async def t_get_feedback(client: FieldNotesClient, params: GetFeedbackInput) -> list[dict[str, Any]]:
    """Surface only cells with a verdict — that's what 'feedback' means.

    Cells without a verdict have nothing for the agent to react to yet.
    """
    if params.project_id is not None:
        cells = await client.list_cells(params.project_id)
    else:
        cells = []
        for p in await client.list_projects():
            cells.extend(await client.list_cells(p.id))
    out: list[dict[str, Any]] = []
    for c in cells:
        if c.verdict is None:
            continue
        out.append(
            {
                "cell_id": str(c.id),
                "project_id": str(c.project_id),
                "title": c.title,
                "status": c.status.value if c.status is not None else None,
                "verdict_state": c.verdict.state.value,
                "note": c.verdict.note,
                "locked": c.locked,
                "updated_at": c.updated_at.isoformat(),
            }
        )
    return out


async def t_tail_events(client: FieldNotesClient, params: TailEventsInput) -> list[dict[str, Any]]:
    events = await client.recent_events(project=params.project_id, limit=params.limit)
    return [e.model_dump(mode="json") for e in events]


# ----------------- FastMCP registration -----------------


def register_tools(mcp: FastMCP, get_client: Callable[[], FieldNotesClient]) -> None:
    """Wire the transport-agnostic tool bodies onto a FastMCP server.

    `get_client` is a zero-arg callable returning the shared FieldNotesClient.
    Using a callable rather than capturing the instance directly lets tests
    swap the client in flight.
    """

    @mcp.tool(description="List all projects.")
    async def list_projects() -> list[dict[str, Any]]:
        return await t_list_projects(get_client())

    @mcp.tool(description="Get one project by id.")
    async def get_project(project_id: UUID) -> dict[str, Any]:
        return await t_get_project(get_client(), _ProjectId(project_id=project_id))

    @mcp.tool(description="Create a new project.")
    async def create_project(
        name: str,
        subtitle: str | None = None,
        repo: str | None = None,
    ) -> dict[str, Any]:
        return await t_create_project(
            get_client(),
            CreateProjectInput(name=name, subtitle=subtitle, repo=repo),
        )

    @mcp.tool(description="Update a project's metadata (name/subtitle/repo).")
    async def update_project(
        project_id: UUID,
        name: str | None = None,
        subtitle: str | None = None,
        repo: str | None = None,
    ) -> dict[str, Any]:
        params = UpdateProjectInput.model_construct(project_id=project_id, name=name, subtitle=subtitle, repo=repo)
        # Build a real validated instance, preserving "set"-ness so we PATCH only what was passed.
        fields: dict[str, Any] = {"project_id": project_id}
        if name is not None:
            fields["name"] = name
        if subtitle is not None:
            fields["subtitle"] = subtitle
        if repo is not None:
            fields["repo"] = repo
        params = UpdateProjectInput(**fields)
        return await t_update_project(get_client(), params)

    @mcp.tool(description="Delete a project (cascades to its cells). Irreversible.")
    async def delete_project(project_id: UUID) -> dict[str, str]:
        return await t_delete_project(get_client(), _ProjectId(project_id=project_id))

    @mcp.tool(description="List cells in a project. Optional client-side filters.")
    async def list_cells(
        project_id: UUID,
        status: CellStatus | None = None,
        kind: CellKind | None = None,
        locked: bool | None = None,
    ) -> list[dict[str, Any]]:
        return await t_list_cells(
            get_client(),
            ListCellsInput(project_id=project_id, status=status, kind=kind, locked=locked),
        )

    @mcp.tool(description="Get one cell by id (includes verdict + locked state).")
    async def get_cell(cell_id: UUID) -> dict[str, Any]:
        return await t_get_cell(get_client(), _CellId(cell_id=cell_id))

    @mcp.tool(
        description=(
            "Create a cell in a project. kind=agent|markdown|empty. "
            "Markdown cells take `body` only; agent cells take title/conclusion/metrics/visual/video/deep; "
            "empty cells take no payload."
        )
    )
    async def create_cell(
        project_id: UUID,
        kind: CellKind,
        after_cell_id: UUID | None = None,
        title: str | None = None,
        agent_id: str | None = None,
        status: CellStatus | None = None,
        conclusion: str | None = None,
        metrics: list[MetricItem] | None = None,
        visual: Visual | None = None,
        video: VideoSlot | None = None,
        deep: DeepBlock | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        params = CreateCellInput(
            project_id=project_id,
            kind=kind,
            after_cell_id=after_cell_id,
            title=title,
            agent_id=agent_id,
            status=status,
            conclusion=conclusion,
            metrics=metrics,
            visual=visual,
            video=video,
            deep=deep,
            body=body,
        )
        return await t_create_cell(get_client(), params)

    @mcp.tool(
        description=(
            "Update a cell's writable fields. Verdict and locked are NOT writable here — "
            "those are the human's authority. Returns {error: 'locked_cell', ...} if the cell is locked."
        )
    )
    async def update_cell(
        cell_id: UUID,
        title: str | None = None,
        agent_id: str | None = None,
        status: CellStatus | None = None,
        conclusion: str | None = None,
        metrics: list[MetricItem] | None = None,
        visual: Visual | None = None,
        video: VideoSlot | None = None,
        deep: DeepBlock | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {"cell_id": cell_id}
        for k, v in {
            "title": title,
            "agent_id": agent_id,
            "status": status,
            "conclusion": conclusion,
            "metrics": metrics,
            "visual": visual,
            "video": video,
            "deep": deep,
            "body": body,
        }.items():
            if v is not None:
                fields[k] = v
        return await t_update_cell(get_client(), UpdateCellInput(**fields))

    @mcp.tool(
        description=("Reorder a cell. Provide exactly one of `direction` ('up'|'down') or `position` (0-indexed).")
    )
    async def reorder_cell(
        cell_id: UUID,
        direction: Literal["up", "down"] | None = None,
        position: int | None = None,
    ) -> dict[str, Any]:
        return await t_reorder_cell(
            get_client(),
            ReorderCellInput(cell_id=cell_id, direction=direction, position=position),
        )

    @mcp.tool(description="Delete a cell. Returns {error: 'locked_cell', ...} if the cell is locked.")
    async def delete_cell(cell_id: UUID) -> dict[str, str]:
        return await t_delete_cell(get_client(), _CellId(cell_id=cell_id))

    @mcp.tool(
        description=(
            "Set the project's UI filter pill (broadcast over SSE so the human's web view updates). "
            "filter ∈ all|in_progress|open|verified|rejected."
        )
    )
    async def set_filter(project_id: UUID, filter: UiFilter) -> dict[str, Any]:
        return await t_set_filter(get_client(), SetFilterInput(project_id=project_id, filter=filter))

    @mcp.tool(
        description=(
            "Get the human's feedback: cells with a verdict (accept/reject), optional locked flag, and "
            "note. Filters out cells without a verdict (no feedback to react to yet). Pass project_id "
            "to scope, omit for cross-project."
        )
    )
    async def get_feedback(project_id: UUID | None = None) -> list[dict[str, Any]]:
        return await t_get_feedback(get_client(), GetFeedbackInput(project_id=project_id))

    @mcp.tool(description=("Tail the audit log: the latest N events newest-first. Scope to a project with project_id."))
    async def tail_events(project_id: UUID | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return await t_tail_events(get_client(), TailEventsInput(project_id=project_id, limit=limit))
