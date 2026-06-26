"""Foundation for the local single-process self-host path.

Covers SQLite durability pragmas (WAL + foreign keys + busy_timeout), the new
local config flags, and env-driven host/port for the bare API entrypoint.
"""

from __future__ import annotations

from field_notes_api.config import Settings
from field_notes_api.db import _build_engine
from sqlalchemy import text

# --- SQLite pragmas -------------------------------------------------------


async def test_file_sqlite_enables_wal_fk_and_busy_timeout(tmp_path):
    """A file-backed SQLite engine must run in WAL with FK enforcement on and a
    non-trivial busy_timeout, so concurrent MCP writes don't instantly lock and
    ON DELETE CASCADE actually cascades locally."""
    db = tmp_path / "fn.db"
    eng = _build_engine(f"sqlite+aiosqlite:///{db}")
    try:
        async with eng.connect() as conn:
            journal = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
            fk = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
            busy = (await conn.execute(text("PRAGMA busy_timeout"))).scalar()
        assert str(journal).lower() == "wal"
        assert int(fk) == 1
        assert int(busy) >= 1000
    finally:
        await eng.dispose()


async def test_memory_sqlite_enforces_fk(tmp_path):
    """In-memory SQLite (tests) can't use WAL, but FK enforcement must still be
    on so cascade behaviour matches production."""
    eng = _build_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with eng.connect() as conn:
            fk = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
        assert int(fk) == 1
    finally:
        await eng.dispose()


# --- Local config flags ---------------------------------------------------


def test_auth_disabled_defaults_false(monkeypatch):
    monkeypatch.delenv("FIELD_NOTES_AUTH_DISABLED", raising=False)
    assert Settings().field_notes_auth_disabled is False


def test_auth_disabled_parses_from_env(monkeypatch):
    monkeypatch.setenv("FIELD_NOTES_AUTH_DISABLED", "1")
    assert Settings().field_notes_auth_disabled is True


# --- Env-driven host/port for the bare API entrypoint ---------------------


def test_main_reads_host_and_port_from_env(monkeypatch):
    """`field-notes-api` honours FIELD_NOTES_HOST + $PORT (Heroku) instead of
    hardcoding 0.0.0.0:8000."""
    import field_notes_api.__main__ as entry

    captured: dict = {}

    def fake_run(_app, *args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setenv("FIELD_NOTES_HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9123")
    entry.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9123
