# Multi-stage build: stage 1 builds the Vite React app, stage 2 builds the API
# and copies the static bundle in. The API serves it from /repo/apps/web/dist
# via StaticFiles (see field_notes_api/main.py).

# ---------- Stage 1: build the frontend ----------
FROM node:20-alpine AS web-builder
WORKDIR /web
COPY apps/web/package*.json ./
# npm install (not npm ci): esbuild's per-platform optional deps confuse
# `npm ci` strict mode — the lockfile lists only a few platform binaries
# while the build host needs linux-x64 which gets re-resolved here.
RUN npm install --no-audit --no-fund
COPY apps/web/ ./
# Empty VITE_API_URL means "same origin" — the api.ts fallback uses
# window.location.origin at runtime. CORS becomes a non-issue.
ENV VITE_API_URL=
RUN npm run build

# ---------- Stage 2: build the API ----------
FROM python:3.11-slim AS runtime
RUN pip install --no-cache-dir uv==0.5.* \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /repo

# ---------- LiftBarrier eval/input videos (served at /media) ----------
# Hosted on a HuggingFace dataset (kept out of git to avoid bloating history)
# and baked into the image here so they survive Heroku dyno restarts — the dyno
# filesystem is ephemeral, so anything not in the image is lost on reboot. The
# later `COPY apps/api/` overlays source on top without deleting this media dir.
# Placed early for layer caching: only re-downloads if this URL changes.
ARG LIFTBARRIER_MEDIA_URL=https://huggingface.co/datasets/mikulrai/field-notes-liftbarrier-media/resolve/main/liftbarrier_media.tar.gz
RUN mkdir -p /repo/apps/api/media \
    && curl -fsSL "$LIFTBARRIER_MEDIA_URL" | tar -xz -C /repo/apps/api/media
ENV FIELD_NOTES_MEDIA_DIR=/repo/apps/api/media

COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
COPY apps/api/ ./apps/api/
RUN uv sync --no-dev --package field-notes-api
COPY --from=web-builder /web/dist ./apps/web/dist
ENV PYTHONPATH=/repo
ENV FIELD_NOTES_STATIC_DIR=/repo/apps/web/dist
EXPOSE 8000
HEALTHCHECK --interval=10s CMD curl -fsS http://localhost:${PORT:-8000}/healthz || exit 1
CMD ["sh", "-c", "uv run --package field-notes-api uvicorn field_notes_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
