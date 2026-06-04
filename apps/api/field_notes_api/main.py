"""FastAPI application entrypoint."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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


# Static SPA mount — must come AFTER all API routes or it swallows them. In
# production (Fly / docker-compose) the Vite build is copied to
# /repo/apps/web/dist and FIELD_NOTES_STATIC_DIR points there. In local dev
# (uvicorn from a checkout) the env var is unset and the mount is skipped, so
# the frontend runs against `npm run dev` on port 5173 and CORS does its thing.
# Media mount — LiftBarrier eval/input videos at /media/<dir>/videos/<file>.mp4.
# Must come BEFORE the SPA "/" mount below or that catch-all swallows it. In
# prod the Dockerfile fetches these from a HF dataset into FIELD_NOTES_MEDIA_DIR;
# the var is unset in local dev, so the mount is simply skipped. StaticFiles
# supports HTTP Range requests, which the <video> players need for seeking.
_media_dir = os.getenv("FIELD_NOTES_MEDIA_DIR")
if _media_dir and Path(_media_dir).is_dir():
    app.mount("/media", StaticFiles(directory=_media_dir), name="media")

_static_dir = os.getenv("FIELD_NOTES_STATIC_DIR")
if _static_dir and Path(_static_dir).is_dir():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
