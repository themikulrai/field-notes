"""Async SQLAlchemy engine + session factory.

Engine + sessionmaker are lazily constructed off `Settings.database_url`. We
keep them module-level singletons but allow tests to swap them via
`set_engine_for_testing` so each test gets a fresh in-memory SQLite.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None

# Wait this long for a lock before raising "database is locked" (ms). Lets the
# local single-process server ride out brief write contention from concurrent
# MCP writes instead of erroring.
_SQLITE_BUSY_TIMEOUT_MS = 5000


def _is_memory_sqlite(url: str) -> bool:
    return ":memory:" in url or url.rstrip("/").endswith("sqlite+aiosqlite:")


def _register_sqlite_pragmas(engine: AsyncEngine, *, wal: bool) -> None:
    """Set per-connection SQLite pragmas.

    FK enforcement is OFF by default in SQLite, so the models' ON DELETE CASCADE
    (cell→verdict) would silently not cascade locally without this. WAL only
    applies to file-backed DBs (an in-memory DB can't use it).
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(dbapi_conn, _record):  # noqa: ANN001 — DBAPI types are untyped
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
            if wal:
                cur.execute("PRAGMA journal_mode=WAL")
        finally:
            cur.close()


def _build_engine(url: str) -> AsyncEngine:
    # SQLite in-memory requires StaticPool so all connections see the same DB.
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        engine = create_async_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        _register_sqlite_pragmas(engine, wal=not _is_memory_sqlite(url))
        return engine
    return create_async_engine(url, future=True, pool_pre_ping=True)


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        url = get_settings().database_url
        _engine = _build_engine(url)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


def set_engine_for_testing(engine: AsyncEngine) -> None:
    """Inject a fresh engine + sessionmaker. Tests use this for isolation."""
    global _engine, _sessionmaker
    _engine = engine
    _sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an AsyncSession scoped to the request."""
    sm = get_sessionmaker()
    async with sm() as session:
        yield session
