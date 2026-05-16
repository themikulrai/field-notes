"""Async HTTP client wrapping the Field Notes REST API.

One thin method per route. All requests carry `X-Field-Notes-Key` and
`X-Field-Notes-Source: mcp` so audit-log entries are attributable to the agent.

The client speaks Pydantic on both ends: request bodies are `model_dump` of
schema objects, response JSON is parsed back into the same schema models. The
MCP tools layer then re-serialises with `model_dump(mode="json")` before
handing to the SDK (which wants plain JSON-compatible dicts).
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from field_notes_schema import (
    CellCreate,
    CellRead,
    CellUpdate,
    EventEnvelope,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ReorderRequest,
    UiFilterSet,
)


class FieldNotesAPIError(Exception):
    """Raised on non-2xx responses. Wraps status + body for the MCP error path."""

    def __init__(self, status: int, detail: str, *, code: str = "api_error") -> None:
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail
        self.code = code


class LockedCellError(FieldNotesAPIError):
    """409 on a locked cell — the agent's signal to back off."""

    def __init__(self, detail: str, cell_id: uuid.UUID | str) -> None:
        super().__init__(409, detail, code="locked_cell")
        self.cell_id = str(cell_id)


class FieldNotesClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "X-Field-Notes-Key": api_key,
                "X-Field-Notes-Source": "mcp",
            },
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> FieldNotesClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # --- raw helpers ---------------------------------------------------

    @staticmethod
    def _detail(resp: httpx.Response) -> str:
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            return resp.text
        if isinstance(data, dict) and "detail" in data:
            return str(data["detail"])
        return str(data)

    def _raise_for(self, resp: httpx.Response, *, cell_id: uuid.UUID | str | None = None) -> None:
        if resp.is_success:
            return
        detail = self._detail(resp)
        if resp.status_code == 409 and cell_id is not None:
            raise LockedCellError(detail, cell_id)
        raise FieldNotesAPIError(resp.status_code, detail)

    # --- projects ------------------------------------------------------

    async def list_projects(self) -> list[ProjectRead]:
        r = await self._http.get("/projects")
        self._raise_for(r)
        return [ProjectRead.model_validate(p) for p in r.json()]

    async def get_project(self, pid: uuid.UUID) -> ProjectRead:
        r = await self._http.get(f"/projects/{pid}")
        self._raise_for(r)
        return ProjectRead.model_validate(r.json())

    async def create_project(self, body: ProjectCreate) -> ProjectRead:
        r = await self._http.post("/projects", json=body.model_dump(mode="json"))
        self._raise_for(r)
        return ProjectRead.model_validate(r.json())

    async def update_project(self, pid: uuid.UUID, body: ProjectUpdate) -> ProjectRead:
        r = await self._http.patch(f"/projects/{pid}", json=body.model_dump(mode="json", exclude_unset=True))
        self._raise_for(r)
        return ProjectRead.model_validate(r.json())

    async def delete_project(self, pid: uuid.UUID) -> None:
        r = await self._http.delete(f"/projects/{pid}")
        self._raise_for(r)

    async def set_ui_filter(self, pid: uuid.UUID, body: UiFilterSet) -> ProjectRead:
        r = await self._http.post(f"/projects/{pid}/ui-filter", json=body.model_dump(mode="json"))
        self._raise_for(r)
        return ProjectRead.model_validate(r.json())

    # --- cells ---------------------------------------------------------

    async def list_cells(self, pid: uuid.UUID) -> list[CellRead]:
        r = await self._http.get(f"/projects/{pid}/cells")
        self._raise_for(r)
        return [CellRead.model_validate(c) for c in r.json()]

    async def get_cell(self, cid: uuid.UUID) -> CellRead:
        r = await self._http.get(f"/cells/{cid}")
        self._raise_for(r)
        return CellRead.model_validate(r.json())

    async def create_cell(self, pid: uuid.UUID, body: CellCreate) -> CellRead:
        r = await self._http.post(
            f"/projects/{pid}/cells",
            json=body.model_dump(mode="json", exclude_none=True),
        )
        self._raise_for(r)
        return CellRead.model_validate(r.json())

    async def update_cell(self, cid: uuid.UUID, body: CellUpdate) -> CellRead:
        r = await self._http.patch(
            f"/cells/{cid}",
            json=body.model_dump(mode="json", exclude_unset=True),
        )
        # 409 here means the cell is locked — propagate as a typed error so the
        # tool layer can convert it to a structured MCP error.
        self._raise_for(r, cell_id=cid)
        return CellRead.model_validate(r.json())

    async def delete_cell(self, cid: uuid.UUID) -> None:
        r = await self._http.delete(f"/cells/{cid}")
        self._raise_for(r, cell_id=cid)

    async def reorder_cell(self, cid: uuid.UUID, body: ReorderRequest) -> CellRead:
        r = await self._http.post(
            f"/cells/{cid}/reorder",
            json=body.model_dump(mode="json", exclude_none=True),
        )
        self._raise_for(r, cell_id=cid)
        return CellRead.model_validate(r.json())

    # --- events --------------------------------------------------------

    async def recent_events(self, project: uuid.UUID | None = None, limit: int = 50) -> list[EventEnvelope]:
        params: dict[str, Any] = {"limit": limit}
        if project is not None:
            params["project"] = str(project)
        r = await self._http.get("/events/recent", params=params)
        self._raise_for(r)
        return [EventEnvelope.model_validate(e) for e in r.json()]
