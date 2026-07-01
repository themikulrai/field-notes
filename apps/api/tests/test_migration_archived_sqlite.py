"""Regression test for the 0006 archived-flag migration on SQLite.

The bug: `server_default="false"` stored the literal STRING 'false' in SQLite
(no native boolean), so `WHERE archived IS 0` matched nothing and every existing
project vanished from the default project list. The ORM-metadata-built test DB
never hit this because new rows use the Python `default=False` (-> integer 0);
only the migration's server_default backfill on pre-existing rows was affected.

This test drives the REAL migration on a seeded SQLite file to lock the fix in.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def _cfg(db_path: Path, monkeypatch) -> Config:
    api_dir = Path(__file__).resolve().parents[1]  # apps/api
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    cfg = Config(str(api_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_dir / "alembic"))
    return cfg


def test_0006_archived_backfills_integer_zero_not_string(tmp_path, monkeypatch) -> None:
    db = tmp_path / "seeded.db"
    cfg = _cfg(db, monkeypatch)

    # Bring the schema up to just before the archived column, then seed a row
    # exactly like a real pre-existing project.
    command.upgrade(cfg, "0005_project_position")
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO projects (id, name, position, created_at, updated_at) "
        "VALUES ('11111111-1111-1111-1111-111111111111', 'Existing', 0, "
        "datetime('now'), datetime('now'))"
    )
    con.commit()
    con.close()

    # Apply the archived migration.
    command.upgrade(cfg, "head")

    con = sqlite3.connect(db)
    value, typ = con.execute("SELECT archived, typeof(archived) FROM projects").fetchone()
    # The stored default must be a real integer 0, never the string 'false'.
    assert typ == "integer", f"archived stored as {typ}={value!r} (string 'false' is the bug)"
    assert value == 0

    # And the active-projects filter (`archived IS 0`) must still see the row.
    visible = con.execute("SELECT COUNT(*) FROM projects WHERE archived IS 0").fetchone()[0]
    con.close()
    assert visible == 1, "existing project vanished from the active filter after migration"
