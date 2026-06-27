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
    AppendSandboxBody,
    CellCreate,
    CellKind,
    CellStatus,
    CellUpdate,
    DeepBlock,
    MetricItem,
    PatchVisualSandboxRequest,
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
    "patch_visual_sandbox",
    "append_visual_sandbox",
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


class ProjectPatch(BaseModel):
    """Writable fields on a project. All optional — send only what you want to change."""

    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    subtitle: str | None = None
    repo: str | None = None


class UpdateProjectInput(BaseModel):
    # Nested `patch` shape (vs flat optionals) so the tool schema has TWO required
    # non-nullable fields. Opus 4.7 reliably emits input={} for tools whose schema
    # is "1 required + N anyOf[T,null] default=null optionals" — the nested form
    # forces the model to fill both fields and stops the empty-call failure mode.
    #
    # Forgiving lift: agents (esp. Opus) often emit flat args like
    # {project_id, name: "..."} despite the nested schema. The before-validator
    # lifts known ProjectPatch fields at top level into a `patch` wrapper.
    # Unknown top-level keys still raise via extra='forbid' below.
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    patch: ProjectPatch

    @model_validator(mode="before")
    @classmethod
    def _lift_flat_patch_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        patch_fields = set(ProjectPatch.model_fields.keys())
        flat_present = {k: v for k, v in data.items() if k in patch_fields}
        if not flat_present:
            return data
        if "patch" in data:
            raise ValueError("ambiguous update: provide either nested `patch={...}` OR flat fields, not both")
        rest = {k: v for k, v in data.items() if k not in patch_fields}
        rest["patch"] = flat_present
        return rest


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


class CellPatch(BaseModel):
    """Writable cell fields. All optional — send only what you want to change."""

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


class UpdateCellInput(BaseModel):
    """Mirrors CellUpdate — verdict and locked are NOT here by design.

    See UpdateProjectInput for why `patch` is nested instead of flat.
    """

    model_config = ConfigDict(extra="forbid")
    cell_id: UUID
    patch: CellPatch

    @model_validator(mode="before")
    @classmethod
    def _lift_flat_patch_fields(cls, data: Any) -> Any:
        # See UpdateProjectInput._lift_flat_patch_fields — same forgiving lift
        # so flat agent calls like {cell_id, conclusion: "..."} are accepted.
        if not isinstance(data, dict):
            return data
        patch_fields = set(CellPatch.model_fields.keys())
        flat_present = {k: v for k, v in data.items() if k in patch_fields}
        if not flat_present:
            return data
        if "patch" in data:
            raise ValueError("ambiguous update: provide either nested `patch={...}` OR flat fields, not both")
        rest = {k: v for k, v in data.items() if k not in patch_fields}
        rest["patch"] = flat_present
        return rest


class PatchVisualSandboxInput(BaseModel):
    cell_id: UUID
    target: Literal["html", "js", "css"]
    find: str = Field(min_length=1)
    replace: str
    expected_count: int = Field(default=1, ge=1)


class AppendVisualSandboxInput(BaseModel):
    cell_id: UUID
    target: Literal["html", "js", "css"]
    chunk: str
    seq: int = Field(ge=0)
    finalize: bool = False


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
    patch_data = params.patch.model_dump(exclude_unset=True)
    p = await client.update_project(params.project_id, ProjectUpdate(**patch_data))
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
    patch_data = params.patch.model_dump(exclude_unset=True)
    try:
        c = await client.update_cell(params.cell_id, CellUpdate(**patch_data))
    except LockedCellError as err:
        return _locked_cell_error(err)
    return c.model_dump(mode="json")


async def t_patch_visual_sandbox(client: FieldNotesClient, params: PatchVisualSandboxInput) -> dict[str, Any]:
    body = PatchVisualSandboxRequest(
        target=params.target,
        find=params.find,
        replace=params.replace,
        expected_count=params.expected_count,
    )
    try:
        c = await client.patch_visual_sandbox(params.cell_id, body)
    except LockedCellError as err:
        return _locked_cell_error(err)
    return c.model_dump(mode="json")


async def t_append_visual_sandbox(client: FieldNotesClient, params: AppendVisualSandboxInput) -> dict[str, Any]:
    body = AppendSandboxBody(
        target=params.target,
        chunk=params.chunk,
        seq=params.seq,
        finalize=params.finalize,
    )
    try:
        c = await client.append_visual_sandbox(params.cell_id, body)
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

    @mcp.tool(
        description=(
            "Update a project's metadata. Pass the writable fields nested under `patch`, "
            "e.g. patch={'subtitle': ''} to clear the subtitle. Both project_id and patch are required."
        )
    )
    async def update_project(project_id: UUID, patch: ProjectPatch) -> dict[str, Any]:
        return await t_update_project(get_client(), UpdateProjectInput(project_id=project_id, patch=patch))

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
            "Create a cell in a project. There are three things you can create, all via `kind`:\n"
            "  • a NOTE (your own prose / explanation) → kind=markdown with a text `body`.\n"
            "  • a SECTION heading (a collapsible group over the cells beneath it) → kind=markdown "
            "with a `body` that STARTS WITH '# ' or '## ' (e.g. body='## Results'). There is NO "
            "separate 'section' kind — a section is simply a markdown cell whose body is a heading.\n"
            "  • a RESULT → kind=agent (title/conclusion/metrics/visual/video/deep). Use this to "
            "report what a run/experiment produced.\n"
            "(kind=empty makes a bare placeholder and takes no payload.) "
            "Markdown cells take `body` only; agent cells never take `body`. "
            "`deep` is REQUIRED on agent cells — create_cell returns 422 if an agent cell has no "
            "deep block, because it is how the human audits the work. `deep` has four parts: "
            "`hparams` (the key config that defines the run, e.g. lr/batch/model), `files` (paths "
            "you created or modified), `runs` (wandb/job links, e.g. {'name':'...','url':'wandb://...'} "
            "or a plain URL), and `logs` (the salient stdout/metric lines). If there are genuinely "
            "none (e.g. a pure analysis/summary cell), set `deep.na=true`. Keep it SMALL so the "
            "human can read it fast: ≤24 hparams, ≤24 files, ≤12 runs, ≤1500 chars of logs "
            "(oversized → 422, summarize). `deep` does NOT apply to markdown/empty cells. "
            "Attach clips via `video` with a STABLE url — prefer a /media/... path (baked into the "
            "image); ephemeral tunnel URLs (trycloudflare/ngrok/etc.) are rejected (422) because they "
            "expire and blank the cell. "
            "For sandboxes larger than ~40 KB, create the cell without `visual` and use "
            "append_visual_sandbox to build it up in chunks — the tool-call channel clamps "
            "large inputs and can silently arrive empty."
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
            "Update a cell. Both `cell_id` and `patch` are required. Put the writable fields "
            "nested inside `patch`, e.g. patch={'conclusion': '', 'status': 'verified'}. "
            "Send ONLY the fields you want to change. `deep` stays REQUIRED on agent cells — an "
            "edit is rejected (422) unless the cell ends up with a deep block (or deep.na=true), so "
            "if you are editing a deep-less agent cell, include `deep` in this patch. Keep `deep` "
            "current as the work progresses — add the wandb run to `deep.runs` once it launches, "
            "append final metrics to `deep.logs` when done, and record any new `files`/`hparams` "
            "(within the same caps: ≤24 hparams, ≤24 files, ≤12 runs, ≤1500 chars logs). "
            "For sandbox-internal edits use "
            "patch_visual_sandbox instead — bundling a large visual here can exceed tool-call "
            "channel limits. Verdict/locked are human-only. Locked cells → {error:'locked_cell',...}."
        )
    )
    async def update_cell(cell_id: UUID, patch: CellPatch) -> dict[str, Any]:
        return await t_update_cell(get_client(), UpdateCellInput(cell_id=cell_id, patch=patch))

    @mcp.tool(
        description=(
            "Surgically edit a substring inside a cell's visual.sandbox.{html,js,css}. "
            "Use this INSTEAD of update_cell when the cell already has a large sandbox and "
            "you only want to change a small piece — sending the whole sandbox via update_cell "
            "can exceed tool-call channel limits and silently arrive empty. "
            "`find` must occur exactly `expected_count` times in target (default 1); mismatch is rejected. "
            "Returns {error: 'locked_cell', ...} if the cell is locked."
        )
    )
    async def patch_visual_sandbox(
        cell_id: UUID,
        target: Literal["html", "js", "css"],
        find: str,
        replace: str,
        expected_count: int = 1,
    ) -> dict[str, Any]:
        return await t_patch_visual_sandbox(
            get_client(),
            PatchVisualSandboxInput(
                cell_id=cell_id,
                target=target,
                find=find,
                replace=replace,
                expected_count=expected_count,
            ),
        )

    @mcp.tool(
        description=(
            "Append a small chunk to a cell's visual.sandbox.{html,js,css}. "
            "Use this to build large sandboxes in pieces — the tool-call channel clamps "
            "inputs around 50 KB, so anything bigger must be chunked here. "
            "`seq` MUST equal the number of chunks already appended for that target "
            "(start at 0 for the first chunk on a target). On `finalize=True` the cell's "
            "status transitions to 'ready' and the per-target chunk counters are cleared. "
            "Returns {error: 'locked_cell', ...} if the cell is locked."
        )
    )
    async def append_visual_sandbox(
        cell_id: UUID,
        target: Literal["html", "js", "css"],
        chunk: str,
        seq: int,
        finalize: bool = False,
    ) -> dict[str, Any]:
        return await t_append_visual_sandbox(
            get_client(),
            AppendVisualSandboxInput(
                cell_id=cell_id,
                target=target,
                chunk=chunk,
                seq=seq,
                finalize=finalize,
            ),
        )

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
