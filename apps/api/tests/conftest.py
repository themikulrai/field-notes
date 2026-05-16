"""Shared test fixtures.

We default to in-memory SQLite via aiosqlite. The same models work on PG, but
this machine doesn't have a reachable docker daemon and the spec says SQLite
fallback is the supported path when Docker is unavailable.

If `TEST_DATABASE_URL` is set we honour it (so the same suite runs in CI against
a real Postgres). Otherwise we use `sqlite+aiosqlite:///:memory:` with a
StaticPool so every connection sees the same DB.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

# Force tests to use a known key + tiny SSE keepalive before any app import.
os.environ.setdefault("FIELD_NOTES_KEY", "test-key")
os.environ.setdefault("FIELD_NOTES_SSE_KEEPALIVE_SECONDS", "0.5")

# Test database URL: SQLite by default, overridable.
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ["DATABASE_URL"] = TEST_DB_URL

# Reset Settings cache so the env we just set is what gets read.
from field_notes_api.config import get_settings  # noqa: E402

get_settings.cache_clear()

from field_notes_api.db import set_engine_for_testing  # noqa: E402
from field_notes_api.main import app  # noqa: E402
from field_notes_api.models import Base  # noqa: E402

API_KEY = os.environ["FIELD_NOTES_KEY"]


@pytest_asyncio.fixture
async def engine() -> AsyncIterator:
    """Fresh engine per test for isolation."""
    if TEST_DB_URL.startswith("sqlite"):
        eng = create_async_engine(
            TEST_DB_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
    else:
        eng = create_async_engine(TEST_DB_URL, future=True)

    set_engine_for_testing(eng)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def client(engine) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        c.headers["X-Field-Notes-Key"] = API_KEY
        yield c


@pytest.fixture
def api_key() -> str:
    return API_KEY
