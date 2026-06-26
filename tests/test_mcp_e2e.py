"""End-to-end agent-vs-human boundary test.

This is the bedrock contract: the agent uses MCP tools; the human uses the
API directly (or the web). The agent CANNOT set verdicts or lock cells; only
READ them via get_cell / get_feedback. Locked cells reject agent writes with
a structured `locked_cell` error.

The whole flow runs in-process — FastAPI app on an ASGITransport, MCP tools
calling through a FieldNotesClient pointed at that transport, no real socket.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

# Match the API test conftest's env contract. setdefault is intentional: when
# the test runs alongside the API suite, FIELD_NOTES_KEY is already exported as
# "test-key" by apps/api/tests/conftest.py and we must use the same value here.
os.environ.setdefault("FIELD_NOTES_KEY", "e2e-key")
os.environ.setdefault("FIELD_NOTES_SSE_KEEPALIVE_SECONDS", "0.5")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402
from field_notes_api.config import get_settings  # noqa: E402

get_settings.cache_clear()

from field_notes_api.db import set_engine_for_testing  # noqa: E402
from field_notes_api.main import app  # noqa: E402
from field_notes_api.models import Base  # noqa: E402
from field_notes_mcp import tools as T  # noqa: E402
from field_notes_mcp.client import FieldNotesClient  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# Bind to whatever key was already exported (set by API conftest or our setdefault above).
API_KEY = os.environ["FIELD_NOTES_KEY"]


@pytest_asyncio.fixture
async def engine() -> AsyncIterator:
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    set_engine_for_testing(eng)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def mcp_client(engine) -> AsyncIterator[FieldNotesClient]:
    transport = httpx.ASGITransport(app=app)
    client = FieldNotesClient(
        base_url="http://testserver",
        api_key=API_KEY,
        transport=transport,
    )
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def human_client(engine) -> AsyncIterator[httpx.AsyncClient]:
    """Simulates the human poking the API directly (or via the web)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-Field-Notes-Key": API_KEY, "X-Field-Notes-Source": "human"},
    ) as c:
        yield c


async def test_agent_vs_human_boundary(mcp_client, human_client) -> None:
    # --- 1) Agent creates a project via MCP tool ---
    proj = await T.t_create_project(mcp_client, T.CreateProjectInput(name="bedrock"))
    pid = uuid.UUID(proj["id"])
    assert proj["name"] == "bedrock"

    projects = await T.t_list_projects(mcp_client)
    assert len(projects) == 1
    assert projects[0]["id"] == str(pid)

    # --- 2) Agent creates a cell via MCP tool ---
    cell = await T.t_create_cell(
        mcp_client,
        T.CreateCellInput(
            project_id=pid,
            kind="agent",
            title="Test 1",
            conclusion="this passed",
            deep={"hparams": {"seed": "0"}},
        ),
    )
    cid = uuid.UUID(cell["id"])
    assert cell["status"] is None or cell["status"] == "open"

    # --- 3) HUMAN sets the verdict directly via the API (NOT via MCP) ---
    r = await human_client.post(f"/cells/{cid}/verdict", json={"state": "accept", "note": "good"})
    assert r.status_code == 200, r.text
    assert r.json()["verdict"]["state"] == "accept"

    # --- 4) Agent reads the feedback ---
    feedback = await T.t_get_feedback(mcp_client, T.GetFeedbackInput(project_id=pid))
    assert len(feedback) == 1
    fb = feedback[0]
    assert fb["cell_id"] == str(cid)
    assert fb["verdict_state"] == "accept"
    assert fb["note"] == "good"
    assert fb["locked"] is False
    assert fb["status"] == "verified"

    # --- 5) HUMAN locks the cell (also human-only) ---
    r = await human_client.post(f"/cells/{cid}/lock")
    assert r.status_code == 200
    assert r.json()["locked"] is True

    # --- 6) Agent tries to update the locked cell -> structured locked_cell error ---
    upd = await T.t_update_cell(mcp_client, T.UpdateCellInput(cell_id=cid, patch=T.CellPatch(title="agent overwrite attempt")))
    assert upd.get("error") == "locked_cell"
    assert upd["cell_id"] == str(cid)
    assert "locked" in upd["message"].lower()

    # --- 7) Agent tries to delete the locked cell -> structured locked_cell error ---
    deleted = await T.t_delete_cell(mcp_client, T._CellId(cell_id=cid))
    assert deleted.get("error") == "locked_cell"

    # --- 8) Agent CAN still list locked cells (read is fine) ---
    locked_cells = await T.t_list_cells(mcp_client, T.ListCellsInput(project_id=pid, locked=True))
    assert len(locked_cells) == 1
    assert locked_cells[0]["id"] == str(cid)

    # --- 9) Verify the human's view: title is unchanged after the agent's blocked write ---
    got = await T.t_get_cell(mcp_client, T._CellId(cell_id=cid))
    assert got["title"] == "Test 1", "title must not have been mutated by the blocked write"
    assert got["locked"] is True

    # --- 10) Bonus: agent uses set_filter; audit log captures it as MCP-sourced ---
    out = await T.t_set_filter(mcp_client, T.SetFilterInput(project_id=pid, filter="open"))
    assert out["ui_filter"] == "open"

    events = await T.t_tail_events(mcp_client, T.TailEventsInput(project_id=pid, limit=20))
    kinds = {e["kind"] for e in events}
    assert "ui.filter_changed" in kinds
    # The MCP source must be attributed.
    ui_ev = next(e for e in events if e["kind"] == "ui.filter_changed")
    assert ui_ev["payload"].get("source") == "mcp"
    assert ui_ev["payload"].get("filter") == "open"

    # The cell.locked event came from the human, not MCP.
    lock_ev = next(e for e in events if e["kind"] == "cell.locked")
    assert lock_ev["payload"].get("source") == "human"


async def test_agent_cannot_reach_verdict_or_lock_via_client(mcp_client) -> None:
    """Even at the bare client level, there's no verdict / lock surface."""
    assert not hasattr(mcp_client, "set_verdict")
    assert not hasattr(mcp_client, "lock_cell")
    assert not hasattr(mcp_client, "unlock_cell")
