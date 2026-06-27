"""Transition an existing deployment into the local self-host without data loss.

`import_db` copies every row from a source DB (e.g. Heroku Postgres) into the
local SQLite, preserving primary keys, foreign keys and timestamps. Both sides
run the identical cross-dialect schema, so the copy is a straight table-by-table
transfer in FK-dependency order. It is non-destructive (source untouched) and
refuses to clobber a non-empty dest unless `overwrite=True`.

`fetch_media` pulls the baked media tarballs (URLs declared in the Dockerfile)
into the managed media root so `/media/...` references resolve locally.
"""

from __future__ import annotations

import re
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from sqlalchemy import func, select, text

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from .db import _build_engine
from .models import Base

_TARBALL_URL = re.compile(r"https://\S+?\.tar\.gz")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "", None}


def _to_async_url(url: str) -> str:
    """Normalise any DB URL to an async driver create_async_engine understands."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def _needs_ssl(async_url: str) -> bool:
    """Remote Postgres (Heroku/RDS) requires TLS; loopback/SQLite does not."""
    if not async_url.startswith("postgresql"):
        return False
    return make_url(async_url).host not in _LOCAL_HOSTS


def _engine_for(url: str):
    """Engine for a transfer endpoint. SQLite reuses the app's _build_engine
    (WAL/FK pragmas); remote Postgres adds asyncpg TLS (Heroku won't connect
    without it)."""
    async_url = _to_async_url(url)
    if async_url.startswith("sqlite"):
        return _build_engine(async_url)
    connect_args = {"ssl": "require"} if _needs_ssl(async_url) else {}
    return create_async_engine(async_url, future=True, pool_pre_ping=True, connect_args=connect_args)


async def _read_revision(conn) -> str | None:  # noqa: ANN001 — AsyncConnection
    try:
        return (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    except Exception:
        return None


async def import_db(source_url: str, dest_url: str, *, overwrite: bool = False) -> dict[str, int]:
    """Copy all rows source → dest. Returns {table: rows_copied}.

    Raises if the two DBs are at different Alembic revisions (column drift would
    silently drop data) or if dest is non-empty and overwrite is False.
    """
    src = _engine_for(source_url)
    dst = _engine_for(dest_url)
    try:
        async with src.connect() as sc:
            src_rev = await _read_revision(sc)
        async with dst.connect() as dc:
            dst_rev = await _read_revision(dc)
        if src_rev != dst_rev:
            raise RuntimeError(
                f"Alembic revision mismatch: source={src_rev} dest={dst_rev}. "
                "Migrate both to the same head before importing."
            )

        counts: dict[str, int] = {}
        tables = list(Base.metadata.sorted_tables)  # FK-dependency order: parents first
        async with src.connect() as sc, dst.begin() as dc:
            # Pre-flight + clear in reverse (child→parent) so FK constraints hold.
            for table in reversed(tables):
                existing = (await dc.execute(select(func.count()).select_from(table))).scalar()
                if existing:
                    if not overwrite:
                        raise RuntimeError(
                            f"dest table {table.name} is not empty ({existing} rows); "
                            "pass overwrite=True to replace"
                        )
                    await dc.execute(table.delete())
            # Copy forward (parent→child).
            for table in tables:
                rows = [dict(r._mapping) for r in (await sc.execute(table.select())).all()]
                if rows:
                    await dc.execute(table.insert(), rows)
                counts[table.name] = len(rows)
        return counts
    finally:
        await src.dispose()
        await dst.dispose()


def parse_media_urls(dockerfile_text: str) -> list[str]:
    """Return the media tarball URLs declared in the Dockerfile, de-duplicated
    in first-seen order."""
    seen: dict[str, None] = {}
    for url in _TARBALL_URL.findall(dockerfile_text):
        seen.setdefault(url, None)
    return list(seen)


def fetch_media(media_root: Path, urls: list[str]) -> list[str]:
    """Download + extract each tarball into media_root. Returns the URLs fetched.

    Uses tarfile's `data` filter to reject path-traversal / absolute members.
    """
    root = Path(media_root)
    root.mkdir(parents=True, exist_ok=True)
    fetched: list[str] = []
    for url in urls:
        with tempfile.NamedTemporaryFile(suffix=".tar.gz") as tmp:
            urllib.request.urlretrieve(url, tmp.name)  # noqa: S310 — fixed https HF URLs
            with tarfile.open(tmp.name, "r:gz") as tar:
                tar.extractall(root, filter="data")
        fetched.append(url)
    return fetched
