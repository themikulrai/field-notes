"""Shared-secret auth: `X-Field-Notes-Key` header (or `?key=` for SSE)."""

from __future__ import annotations

from fastapi import Header, HTTPException, Query, status

from .config import get_settings


async def require_api_key(x_field_notes_key: str | None = Header(default=None)) -> None:
    """Header-based auth dependency for normal JSON endpoints."""
    expected = get_settings().field_notes_key
    if not x_field_notes_key or x_field_notes_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid api key",
        )


async def require_api_key_query(key: str | None = Query(default=None)) -> None:
    """Query-param variant — used by /events because EventSource can't send headers."""
    expected = get_settings().field_notes_key
    if not key or key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid api key",
        )
