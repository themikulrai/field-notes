"""Local single-process auth bypass.

When FIELD_NOTES_AUTH_DISABLED is set (the `field-notes serve` loopback path),
both the header auth and the SSE-token auth become no-ops so the owner isn't
locked out of their own notebook and the MCP can connect with no key. The
default (unset) must stay fully enforced for networked/Heroku deploys.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from field_notes_api import auth
from field_notes_api.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- header auth ----------------------------------------------------------


async def test_header_auth_bypassed_when_disabled(monkeypatch):
    monkeypatch.setenv("FIELD_NOTES_AUTH_DISABLED", "1")
    get_settings.cache_clear()
    # No key supplied, yet must not raise.
    await auth.require_api_key(x_field_notes_key=None)


async def test_header_auth_enforced_by_default(monkeypatch):
    monkeypatch.delenv("FIELD_NOTES_AUTH_DISABLED", raising=False)
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        await auth.require_api_key(x_field_notes_key=None)
    assert exc.value.status_code == 401


# --- SSE query/token auth -------------------------------------------------


async def test_sse_auth_bypassed_when_disabled(monkeypatch):
    monkeypatch.setenv("FIELD_NOTES_AUTH_DISABLED", "1")
    get_settings.cache_clear()
    # Neither token nor key, yet must not raise.
    await auth.require_api_key_query(key=None, token=None)


async def test_sse_auth_enforced_by_default(monkeypatch):
    monkeypatch.delenv("FIELD_NOTES_AUTH_DISABLED", raising=False)
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        await auth.require_api_key_query(key=None, token=None)
    assert exc.value.status_code == 401
