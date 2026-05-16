"""StaticFiles mount sanity tests.

The production layout (Fly.io, docker-compose) builds the React app and
copies it into the API image; the API serves it at "/" via StaticFiles. The
mount must come AFTER all routers or it swallows /projects, /cells, etc.

This test reloads the app module with FIELD_NOTES_STATIC_DIR pointing at a
temp directory and verifies:

* a request to "/" returns the static index.html
* a request to "/projects" still hits the API (returns 401 / 200 depending on
  auth, NOT the index.html)
* /healthz remains reachable
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_static(tmp_path: Path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>field-notes</title>")
    (static / "assets").mkdir()
    (static / "assets" / "app.js").write_text("console.log('app')")

    prev = os.environ.get("FIELD_NOTES_STATIC_DIR")
    os.environ["FIELD_NOTES_STATIC_DIR"] = str(static)
    try:
        # Reload main so the StaticFiles mount is re-evaluated.
        sys.modules.pop("field_notes_api.main", None)
        main_mod = importlib.import_module("field_notes_api.main")
        yield main_mod.app
    finally:
        if prev is None:
            os.environ.pop("FIELD_NOTES_STATIC_DIR", None)
        else:
            os.environ["FIELD_NOTES_STATIC_DIR"] = prev
        sys.modules.pop("field_notes_api.main", None)
        # Re-import the module with default settings so other tests are not
        # left looking at a module bound to a deleted tmp path.
        importlib.import_module("field_notes_api.main")


def test_static_mount_serves_index_at_root(app_with_static) -> None:
    client = TestClient(app_with_static)
    r = client.get("/")
    assert r.status_code == 200, r.text
    assert "<title>field-notes</title>" in r.text


def test_static_mount_serves_assets(app_with_static) -> None:
    client = TestClient(app_with_static)
    r = client.get("/assets/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_static_mount_does_not_swallow_api_routes(app_with_static) -> None:
    """/projects must reach the API router (returns 401 with no key) — not
    the StaticFiles SPA fallback (which would return index.html 200)."""
    client = TestClient(app_with_static)
    r = client.get("/projects")
    # No auth header → 401 (or 422 if header parsing differs). Anything but a
    # 200 with HTML body confirms the API routes win the prefix race.
    assert r.status_code in (401, 403, 422), r.text
    assert "<title>" not in r.text


def test_healthz_still_reachable_with_static_mount(app_with_static) -> None:
    client = TestClient(app_with_static)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
