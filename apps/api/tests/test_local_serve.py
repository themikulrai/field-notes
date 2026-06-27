"""`field-notes serve` CLI: env resolution, in-process migrations, wiring.

Side-effecting steps (uvicorn, browser) are monkeypatched; the pure env/auth
logic and the real Alembic-on-SQLite migration are exercised directly.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from field_notes_api import cli
from field_notes_api.config import get_settings


@pytest.fixture(autouse=True)
def _env_sandbox():
    """Snapshot + restore os.environ since serve() mutates it in place."""
    saved = dict(os.environ)
    get_settings.cache_clear()
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


# --- loopback detection ---------------------------------------------------


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_is_loopback_true(host):
    assert cli._is_loopback(host) is True


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5", "example.com"])
def test_is_loopback_false(host):
    assert cli._is_loopback(host) is False


# --- env resolution -------------------------------------------------------


def test_build_serve_env_loopback_no_key_disables_auth(tmp_path):
    env = cli.build_serve_env(data_dir=tmp_path, host="127.0.0.1", key=None)
    assert env["FIELD_NOTES_AUTH_DISABLED"] == "1"
    assert "FIELD_NOTES_KEY" not in env
    assert str(tmp_path / "field-notes.db") in env["DATABASE_URL"]
    assert env["DATABASE_URL"].startswith("sqlite+aiosqlite://")
    assert env["FIELD_NOTES_MEDIA_DIR"] == str(tmp_path / "media")
    assert env["FIELD_NOTES_DATA_DIR"] == str(tmp_path)


def test_build_serve_env_with_key_keeps_auth_enabled(tmp_path):
    env = cli.build_serve_env(data_dir=tmp_path, host="127.0.0.1", key="s3cret")
    assert env.get("FIELD_NOTES_AUTH_DISABLED") != "1"
    assert env["FIELD_NOTES_KEY"] == "s3cret"


def test_build_serve_env_public_bind_without_key_refuses(tmp_path):
    with pytest.raises(ValueError, match="without a key"):
        cli.build_serve_env(data_dir=tmp_path, host="0.0.0.0", key=None)


def test_build_serve_env_respects_existing_database_url(tmp_path):
    env = cli.build_serve_env(
        data_dir=tmp_path,
        host="127.0.0.1",
        key=None,
        existing={"DATABASE_URL": "postgresql+asyncpg://u@h/db"},
    )
    assert "DATABASE_URL" not in env  # power-user override preserved


# --- in-process migration (Risk #4: aiosqlite must become a sync driver) --


def test_run_migrations_creates_schema_on_file_sqlite(tmp_path):
    db = tmp_path / "fn.db"
    cli.run_migrations(f"sqlite+aiosqlite:///{db}")
    con = sqlite3.connect(db)
    try:
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    assert {"projects", "cells", "verdicts", "events", "alembic_version"} <= names


# --- serve wiring ---------------------------------------------------------


def test_serve_wires_uvicorn_loopback_and_skips_browser(tmp_path, monkeypatch):
    # Start from a clean shell: conftest globally pins DATABASE_URL to :memory:,
    # which serve's "respect existing override" would otherwise inherit.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("FIELD_NOTES_AUTH_DISABLED", raising=False)
    calls: dict = {}
    monkeypatch.setattr(cli, "run_migrations", lambda url: calls.__setitem__("migrated", url))
    monkeypatch.setattr("uvicorn.run", lambda _app, **kw: calls.update(kw))
    monkeypatch.setattr("webbrowser.open", lambda url: calls.__setitem__("browser", url))

    cli.main(["serve", "--data-dir", str(tmp_path), "--no-browser", "--port", "8123"])

    assert Path(calls["migrated"].split("///")[-1]).name == "field-notes.db"
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 8123
    assert "browser" not in calls
    assert os.environ["FIELD_NOTES_AUTH_DISABLED"] == "1"
    # data dir + media dir created on disk
    assert (tmp_path / "media").is_dir()
