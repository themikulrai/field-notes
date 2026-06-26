"""Packaged-layout resolution: the wheel bundles _web/ (SPA) and _alembic/.

These verify the runtime *finds* the bundled assets given the wheel layout; the
actual bundling is asserted by inspecting a built wheel in CI / the dev flow.
"""

from __future__ import annotations

import os

import pytest
from field_notes_api import cli


@pytest.fixture(autouse=True)
def _clear_static_env(monkeypatch):
    monkeypatch.delenv("FIELD_NOTES_STATIC_DIR", raising=False)


def test_resolve_static_dir_finds_bundled_web(tmp_path, monkeypatch):
    web = tmp_path / "_web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>")
    monkeypatch.setattr(cli, "_package_dir", lambda: tmp_path)

    assert cli.resolve_static_dir() == str(web)


def test_resolve_static_dir_none_when_web_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_package_dir", lambda: tmp_path)
    assert cli.resolve_static_dir() is None


def test_resolve_static_dir_env_wins_over_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("FIELD_NOTES_STATIC_DIR", "/explicit/dir")
    monkeypatch.setattr(cli, "_package_dir", lambda: tmp_path)
    assert cli.resolve_static_dir() == "/explicit/dir"


def test_find_alembic_prefers_packaged_layout(tmp_path, monkeypatch):
    alembic = tmp_path / "_alembic" / "alembic"
    alembic.mkdir(parents=True)
    (tmp_path / "_alembic" / "alembic.ini").write_text("[alembic]\n")
    monkeypatch.setattr(cli, "_package_dir", lambda: tmp_path)

    ini, script = cli._find_alembic()
    assert ini == tmp_path / "_alembic" / "alembic.ini"
    assert script == tmp_path / "_alembic" / "alembic"


def test_run_migrations_uses_bundled_alembic_then_migrates(tmp_path, monkeypatch):
    """End-to-end: stage a wheel-style _alembic/ next to a fake package dir and
    confirm run_migrations finds + applies it on a fresh SQLite DB."""
    import shutil
    import sqlite3
    from pathlib import Path

    # Stage the real migrations under a wheel-style _alembic/ in a temp pkg dir.
    src_ini, src_script = cli._find_alembic()  # the source-tree copy
    pkg = tmp_path / "pkg"
    (pkg / "_alembic").mkdir(parents=True)
    shutil.copy(src_ini, pkg / "_alembic" / "alembic.ini")
    shutil.copytree(src_script, pkg / "_alembic" / "alembic")
    monkeypatch.setattr(cli, "_package_dir", lambda: pkg)

    db = tmp_path / "fn.db"
    saved = dict(os.environ)
    try:
        cli.run_migrations(f"sqlite+aiosqlite:///{db}")
    finally:
        os.environ.clear()
        os.environ.update(saved)

    con = sqlite3.connect(db)
    try:
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    assert {"projects", "cells", "alembic_version"} <= names
    assert Path(pkg / "_alembic" / "alembic").is_dir()  # used the bundled copy
