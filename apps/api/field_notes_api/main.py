"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import cells, events, projects, verdicts

settings = get_settings()

app = FastAPI(title="Field Notes API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.field_notes_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    """Liveness probe used by docker-compose and Fly.io. Always public."""
    return {"ok": True}


app.include_router(projects.router)
app.include_router(cells.router)
app.include_router(verdicts.router)
app.include_router(events.router)
