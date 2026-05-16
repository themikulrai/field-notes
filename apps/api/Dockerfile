# Multi-stage build: stage 1 builds the Vite React app, stage 2 builds the API
# and copies the static bundle in. The API serves it from /repo/apps/web/dist
# via StaticFiles (see field_notes_api/main.py).

# ---------- Stage 1: build the frontend ----------
FROM node:20-alpine AS web-builder
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci --no-audit --no-fund
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
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
COPY apps/api/ ./apps/api/
RUN uv sync --no-dev --package field-notes-api
COPY --from=web-builder /web/dist ./apps/web/dist
ENV PYTHONPATH=/repo
ENV FIELD_NOTES_STATIC_DIR=/repo/apps/web/dist
EXPOSE 8000
HEALTHCHECK --interval=10s CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["uv", "run", "--package", "field-notes-api", "uvicorn", "field_notes_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
