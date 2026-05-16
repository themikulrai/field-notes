"""Runtime configuration for the MCP server.

Reads env vars (no .env file by default — agents invoke us via `command/env`
in their MCP config). `FIELD_NOTES_KEY` is required; we fail fast with a
clear message rather than silently 401-ing on every API call.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    field_notes_api_url: str = Field(default="http://localhost:8000")
    # Required; no sensible default. We default to "" so pydantic-settings doesn't
    # synthesise one, and we check explicitly in `load()`.
    field_notes_key: str = Field(default="")
    field_notes_mcp_http_host: str = Field(default="127.0.0.1")
    field_notes_mcp_http_port: int = Field(default=7800)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_or_exit() -> Settings:
    """Resolve settings, exit(1) with a clear message if FIELD_NOTES_KEY is missing."""
    s = get_settings()
    if not s.field_notes_key:
        # Some agents swallow stderr — but stdio MCP eats stdout, so stderr is
        # all we have. Also exit 1 so the agent's launcher reports a failure.
        print(
            "field-notes-mcp: FIELD_NOTES_KEY env var is required (the shared secret "
            "configured on the Field Notes API).",
            file=sys.stderr,
        )
        # Hint: the API URL we'd try to talk to, in case it's wrong.
        print(f"  FIELD_NOTES_API_URL={s.field_notes_api_url}", file=sys.stderr)
        print(f"  env keys present: {sorted(k for k in os.environ if k.startswith('FIELD_NOTES'))}", file=sys.stderr)
        raise SystemExit(1)
    return s
