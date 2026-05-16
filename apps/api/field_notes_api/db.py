"""Async SQLAlchemy engine + session factory.

Engine + sessionmaker are lazily constructed off `Settings.database_url`. We
keep them module-level singletons but allow tests to swap them via
`set_engine_for_testing` so each test gets a fresh in-memory SQLite.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _build_engine(url: str) -> AsyncEngine:
    # SQLite in-memory requires StaticPool so all connections see the same DB.
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        return create_async_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
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
