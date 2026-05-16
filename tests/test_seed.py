"""End-to-end test for ``tools/seed.py``.

We exercise the seed script the same way an agent would — over the public REST
API — but skip the network entirely by attaching ``httpx.AsyncClient`` to an
in-process FastAPI app via ``ASGITransport``. This is the same pattern the
backend test suite uses, so we get a clean DB each run and don't depend on a
running Postgres.

Asserts:

* 4 projects exist after a fresh seed
* The first project's cells appear in the expected order
* The locked cell (``c-006`` → "VLA fine-tuning — data mix v3") is actually
  ``locked=True`` with an ``accept`` verdict
* The in-progress cell is ``status="in_progress"``
* A second call to ``seed()`` is idempotent (no duplicate projects, no error)
"""

from __future__ import annotations

import os

# Match the API conftest's env contract before importing the app, so settings
# are read from the right env vars (the apps/api/tests/conftest.py also exports
# these as side effects of import but we can't rely on import order across
# pytest collection roots).
os.environ.setdefault("FIELD_NOTES_KEY", "test-key")
os.environ.setdefault("FIELD_NOTES_SSE_KEEPALIVE_SECONDS", "0.5")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from collections.abc import AsyncIterator  # noqa: E402

import pytest_asyncio  # noqa: E402
from field_notes_api.config import get_settings  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

get_settings.cache_clear()

from field_notes_api.db import set_engine_for_testing  # noqa: E402
from field_notes_api.main import app  # noqa: E402
from field_notes_api.models import Base  # noqa: E402

from tools.seed import seed  # noqa: E402

API_KEY = os.environ["FIELD_NOTES_KEY"]


@pytest_asyncio.fixture
async def fresh_db() -> AsyncIterator[None]:
    """Fresh in-memory SQLite engine bound into the app for one test."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    set_engine_for_testing(eng)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


async def test_seed_creates_all_projects_and_locks_correctly(fresh_db: None) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.headers["X-Field-Notes-Key"] = API_KEY

        summary = await seed(client)
        assert summary["created_count"] == 4, summary
        assert summary["skipped_count"] == 0, summary

        r = await client.get("/projects")
        r.raise_for_status()
        projects = r.json()
        names = [p["name"] for p in projects]
        assert names == [
            "orca · manipulation",
            "pi0.5 · VLA fine-tune",
            "sim2real · bench v2",
            "data infra · v2",
        ], names

        # orca · manipulation: cells appear in the prototype's order.
        orca = projects[0]
        r = await client.get(f"/projects/{orca['id']}/cells")
        r.raise_for_status()
        orca_cells = r.json()
        # 9 cells total: md-intro, c-001..c-004, md-section-failures, c-005,
        # md-section-historical, c-006.
        assert len(orca_cells) == 9, [c.get("title") or c.get("body", "")[:40] for c in orca_cells]
        assert orca_cells[0]["kind"] == "markdown"
        assert orca_cells[0]["body"].startswith("# Week 19")
        assert orca_cells[1]["title"].startswith("pi0.5 TSC WS task")
        # Position invariant: dense 0..N-1.
        assert [c["position"] for c in orca_cells] == list(range(9))

        # Locked cell: c-006 is the last cell, must have accept verdict + locked.
        locked = orca_cells[-1]
        assert locked["title"].startswith("VLA fine-tuning — data mix v3"), locked["title"]
        assert locked["locked"] is True, locked
        assert locked["verdict"] is not None
        assert locked["verdict"]["state"] == "accept"
        assert locked["status"] == "verified"

        # In-progress cell: c-003 (camera calibration) should be in_progress.
        in_progress = next(c for c in orca_cells if (c.get("title") or "").startswith("Camera calibration drift"))
        assert in_progress["status"] == "in_progress", in_progress
        assert in_progress["verdict"] is None

        # Rejected cell: c-002 has reject verdict + status="rejected".
        rejected = next(c for c in orca_cells if (c.get("title") or "").startswith("Reward shaping ablation"))
        assert rejected["status"] == "rejected"
        assert rejected["verdict"]["state"] == "reject"

        # Visual: c-001 has line chart, c-004 has sweep chart.
        run4 = next(c for c in orca_cells if (c.get("title") or "").startswith("pi0.5 TSC WS task"))
        assert run4["visual"] is not None
        assert run4["visual"]["chart"] == "line"
        assert len(run4["visual"]["series"]) == 8

        sweep_cell = next(c for c in orca_cells if (c.get("title") or "").startswith("Domain randomization sweep"))
        assert sweep_cell["visual"] is not None
        assert sweep_cell["visual"]["chart"] == "sweep"
        assert len(sweep_cell["visual"]["series"]) == 5

        # Idempotency: re-running seed() must not create duplicates and must not crash.
        summary2 = await seed(client)
        assert summary2["created_count"] == 0
        assert summary2["skipped_count"] == 4

        r = await client.get("/projects")
        r.raise_for_status()
        again = r.json()
        assert len(again) == 4
