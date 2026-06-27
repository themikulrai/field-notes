"""Data transition: PK/FK-preserving DB copy + media tarball URL parsing.

The DB copy is exercised SQLite→SQLite; the same code path runs Postgres→SQLite
(asyncpg→aiosqlite) and is verified manually against the live Heroku DB.
"""

from __future__ import annotations

import os
import sqlite3
import uuid

import pytest
from field_notes_api import cli, transfer
from field_notes_api.db import _build_engine
from field_notes_api.models import Cell, Event, Project, VerdictRow


@pytest.fixture(autouse=True)
def _env_sandbox():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


async def _seed(url: str, pid: uuid.UUID, cid: uuid.UUID) -> None:
    eng = _build_engine(url)
    async with eng.begin() as c:
        await c.execute(Project.__table__.insert(), [{"id": pid, "name": "Proj", "position": 0}])
        await c.execute(
            Cell.__table__.insert(),
            [{"id": cid, "project_id": pid, "kind": "agent", "position": 0, "metrics": [{"k": "x", "v": 1}]}],
        )
        await c.execute(VerdictRow.__table__.insert(), [{"cell_id": cid, "state": "accept", "note": "ok", "by": "you"}])
        await c.execute(Event.__table__.insert(), [{"id": uuid.uuid4(), "kind": "created", "project_id": pid}])
    await eng.dispose()


# --- DB copy --------------------------------------------------------------


async def test_import_db_preserves_pks_fks_and_json(tmp_path):
    src_url = f"sqlite+aiosqlite:///{tmp_path / 'src.db'}"
    dst_url = f"sqlite+aiosqlite:///{tmp_path / 'dst.db'}"
    cli.run_migrations(src_url)
    cli.run_migrations(dst_url)

    pid, cid = uuid.uuid4(), uuid.uuid4()
    await _seed(src_url, pid, cid)

    counts = await transfer.import_db(src_url, dst_url)
    assert counts["projects"] == 1 and counts["cells"] == 1 and counts["verdicts"] == 1 and counts["events"] == 1

    deng = _build_engine(dst_url)
    async with deng.connect() as c:
        proj = (await c.execute(Project.__table__.select())).one()
        cell = (await c.execute(Cell.__table__.select())).one()
    await deng.dispose()
    assert proj.id == pid and proj.name == "Proj"  # PK preserved
    assert cell.id == cid and cell.project_id == pid  # FK link preserved
    assert cell.metrics == [{"k": "x", "v": 1}]  # JSON round-trips


async def test_import_db_rejects_revision_mismatch(tmp_path):
    src_url = f"sqlite+aiosqlite:///{tmp_path / 'src.db'}"
    dst_path = tmp_path / "dst.db"
    dst_url = f"sqlite+aiosqlite:///{dst_path}"
    cli.run_migrations(src_url)
    cli.run_migrations(dst_url)

    con = sqlite3.connect(dst_path)
    con.execute("UPDATE alembic_version SET version_num='OLD'")
    con.commit()
    con.close()

    with pytest.raises(RuntimeError, match="revision"):
        await transfer.import_db(src_url, dst_url)


async def test_import_db_guards_nonempty_dest(tmp_path):
    src_url = f"sqlite+aiosqlite:///{tmp_path / 'src.db'}"
    dst_url = f"sqlite+aiosqlite:///{tmp_path / 'dst.db'}"
    cli.run_migrations(src_url)
    cli.run_migrations(dst_url)
    pid, cid = uuid.uuid4(), uuid.uuid4()
    await _seed(src_url, pid, cid)
    await _seed(dst_url, uuid.uuid4(), uuid.uuid4())  # dest already has data

    with pytest.raises(RuntimeError, match="not empty"):
        await transfer.import_db(src_url, dst_url)

    counts = await transfer.import_db(src_url, dst_url, overwrite=True)
    assert counts["projects"] == 1  # overwrite replaces, not appends


# --- remote Postgres needs TLS (Heroku/RDS) -------------------------------


def test_needs_ssl_true_for_remote_postgres():
    assert transfer._needs_ssl("postgresql+asyncpg://u:p@abc.rds.amazonaws.com:5432/db") is True


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@localhost:5432/db",
        "postgresql+asyncpg://u:p@127.0.0.1:5432/db",
        "sqlite+aiosqlite:///x.db",
    ],
)
def test_needs_ssl_false_for_local_or_sqlite(url):
    assert transfer._needs_ssl(url) is False


def test_engine_for_remote_postgres_sets_ssl(monkeypatch):
    captured = {}

    def fake_create(url, **kw):
        captured["url"] = str(url)
        captured["connect_args"] = kw.get("connect_args")
        return "engine"

    monkeypatch.setattr(transfer, "create_async_engine", fake_create)
    transfer._engine_for("postgres://u:p@host.rds.amazonaws.com:5432/db")
    assert captured["connect_args"] == {"ssl": "require"}
    assert captured["url"].startswith("postgresql+asyncpg://")


# --- media tarball URL parsing --------------------------------------------


def test_parse_media_urls_from_dockerfile():
    text = (
        "ARG LIFTBARRIER_MEDIA_URL=https://huggingface.co/datasets/x/resolve/main/liftbarrier_media.tar.gz\n"
        'RUN curl -fsSL "$LIFTBARRIER_MEDIA_URL" | tar -xz -C /repo/apps/api/media\n'
        "ARG MEMER_MEDIA_URL=https://huggingface.co/datasets/x/resolve/main/memer_media.tar.gz\n"
    )
    urls = transfer.parse_media_urls(text)
    assert urls == [
        "https://huggingface.co/datasets/x/resolve/main/liftbarrier_media.tar.gz",
        "https://huggingface.co/datasets/x/resolve/main/memer_media.tar.gz",
    ]


# --- CLI wiring -----------------------------------------------------------


def test_cli_import_db_into_local_data_dir(tmp_path):
    import asyncio

    src_url = f"sqlite+aiosqlite:///{tmp_path / 'src.db'}"
    cli.run_migrations(src_url)
    asyncio.run(_seed(src_url, uuid.uuid4(), uuid.uuid4()))

    data_dir = tmp_path / "local"
    rc = cli.main(["import-db", "--source", src_url, "--data-dir", str(data_dir)])
    assert rc == 0

    con = sqlite3.connect(data_dir / "field-notes.db")
    try:
        assert con.execute("SELECT count(*) FROM projects").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM cells").fetchone()[0] == 1
    finally:
        con.close()
