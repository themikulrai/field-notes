"""Runtime settings loaded from env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    field_notes_key: str = Field(default="changeme")
    database_url: str = Field(default="sqlite+aiosqlite:///:memory:")

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_pg_url(cls, v: str) -> str:
        # Heroku injects `postgres://...`; SQLAlchemy 2 wants `postgresql://`
        # and we need the asyncpg driver at runtime.
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v
    field_notes_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    # SSE keepalive interval. Overridable in tests so we don't wait 25s for a keepalive assertion.
    field_notes_sse_keepalive_seconds: float = 25.0
    # Local single-process self-host: when true, the API key + SSE token checks
    # become no-ops. Set automatically by `field-notes serve` on a loopback bind
    # with no key. Default stays False so Heroku/networked deploys stay locked.
    field_notes_auth_disabled: bool = Field(default=False)
    # Where the local install keeps its SQLite DB + managed media (resolved by
    # the serve CLI; unused by the networked deploy).
    field_notes_data_dir: str | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    return Settings()
