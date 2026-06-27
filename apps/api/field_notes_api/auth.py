"""Shared-secret auth: `X-Field-Notes-Key` header (or `?key=` for SSE).

For SSE we now prefer short-lived HMAC tokens minted at `POST /sse-token`,
because Heroku's router logs full request URLs and raw `?key=` leaks the
shared secret into log retention. Raw `?key=` still works for one release
with a deprecation warning.
"""

from __future__ import annotations

import base64
import hmac
import json
import logging
import time
from hashlib import sha256

from fastapi import Header, HTTPException, Query, status

from .config import get_settings

logger = logging.getLogger(__name__)

# Token TTL in seconds; surfaced for the /sse-token response and for tests.
SSE_TOKEN_TTL_SECONDS = 60

# Module-level dedup so the deprecation log doesn't spam per request.
_warned_raw_key = False


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _hmac_key() -> bytes:
    """Use FIELD_NOTES_KEY as the HMAC secret. Single-secret deployment keeps
    this simple; the API key is already privileged enough to mint tokens."""
    return get_settings().field_notes_key.encode("utf-8")


def mint_sse_token(ttl_seconds: int = SSE_TOKEN_TTL_SECONDS) -> tuple[str, int]:
    """Return (token, exp_unix_seconds). Token = b64url(payload).b64url(sig)."""
    exp = int(time.time()) + ttl_seconds
    payload = json.dumps({"exp": exp}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_hmac_key(), payload, sha256).digest()
    return f"{_b64url_encode(payload)}.{_b64url_encode(sig)}", exp


def _verify_sse_token(token: str) -> bool:
    """Constant-time HMAC + expiry check. Never logs the token."""
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _b64url_decode(payload_b64)
        sig = _b64url_decode(sig_b64)
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return False
    expected = hmac.new(_hmac_key(), payload, sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        body = json.loads(payload.decode("utf-8"))
        exp = int(body["exp"])
    except (ValueError, KeyError, TypeError):
        return False
    return exp >= int(time.time())


async def require_api_key(x_field_notes_key: str | None = Header(default=None)) -> None:
    """Header-based auth dependency for normal JSON endpoints."""
    settings = get_settings()
    if settings.field_notes_auth_disabled:
        return
    if not x_field_notes_key or not hmac.compare_digest(x_field_notes_key, settings.field_notes_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid api key",
        )


async def require_api_key_query(
    key: str | None = Query(default=None),
    token: str | None = Query(default=None),
) -> None:
    """Query-param variant — used by /events because EventSource can't send headers.

    Accepts either:
      - `?token=...`: HMAC-signed short-lived token from POST /sse-token (preferred)
      - `?key=...`:   raw shared secret (DEPRECATED — leaks via Heroku router logs)
    """
    if get_settings().field_notes_auth_disabled:
        return
    if token:
        if _verify_sse_token(token):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired sse token",
        )
    if key:
        expected = get_settings().field_notes_key
        if hmac.compare_digest(key, expected):
            global _warned_raw_key
            if not _warned_raw_key:
                logger.warning(
                    "DEPRECATED: /events ?key= used; switch to POST /sse-token + ?token=."
                )
                _warned_raw_key = True
            return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing or invalid api key",
    )
