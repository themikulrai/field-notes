"""Smoke test for the /healthz liveness endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from field_notes_api.main import app


def test_healthz_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
