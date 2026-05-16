"""Runtime settings loaded from env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    field_notes_key: str = Field(default="changeme")
    database_url: str = Field(default="sqlite+aiosqlite:///:memory:")
    field_notes_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    # SSE keepalive interval. Overridable in tests so we don't wait 25s for a keepalive assertion.
    field_notes_sse_keepalive_seconds: float = 25.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
