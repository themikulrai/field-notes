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
# MemER lift_barrier rollout clips (workspace + wristcam dataset visualisers).
# Separate tarball so adding it doesn't re-transfer the 254MB LiftBarrier one.
ARG MEMER_MEDIA_URL=https://huggingface.co/datasets/mikulrai/field-notes-liftbarrier-media/resolve/main/memer_media.tar.gz
RUN curl -fsSL "$MEMER_MEDIA_URL" | tar -xz -C /repo/apps/api/media
# Multiview (tiled all-camera) LB wristcam re-eval videos. Extracted LAST so it
# overlays the global-only clips in the 4 wc dirs (pi/dp × cent/decent) with the
# tiled global+wrist versions; same filenames → grid cells need no path change.
ARG LIFTBARRIER_MV_MEDIA_URL=https://huggingface.co/datasets/mikulrai/field-notes-liftbarrier-media/resolve/main/liftbarrier_media_mv.tar.gz
RUN curl -fsSL "$LIFTBARRIER_MV_MEDIA_URL" | tar -xz -C /repo/apps/api/media
# overfit_ep0 tile videos — re-hosted off a dead trycloudflare tunnel (the
# original host expired, so the pos17/pos18 overfit clips wouldn't load).
# v2: + pi05_overfit_egocentric.mp4 (multiview 10k|49999 re-render).
ARG OVERFIT_MEDIA_URL=https://huggingface.co/datasets/mikulrai/field-notes-liftbarrier-media/resolve/main/overfit_media.tar.gz
RUN curl -fsSL "$OVERFIT_MEDIA_URL" | tar -xz -C /repo/apps/api/media
# MemER LB wristcam hierarchical-eval clips, tiled multi-view (global + both
# wrist) with the Boss subtask burned in — replaces the old global-only MemER
# rollout clips so pos27 etc. show what the robot actually saw.
ARG MEMER_MV_MEDIA_URL=https://huggingface.co/datasets/mikulrai/field-notes-liftbarrier-media/resolve/main/memer_lb_wc_mv_clips.tar.gz
RUN curl -fsSL "$MEMER_MV_MEDIA_URL" | tar -xz -C /repo/apps/api/media
# Stacking Cubes 3SC wristcam no-aug + zerostate clips, 2x2 multi-view (global +
# 3 wrist cams) — replaces the old single-global clips in the 3 SC eval cells.
ARG SC3_MV_MEDIA_URL=https://huggingface.co/datasets/mikulrai/field-notes-liftbarrier-media/resolve/main/sc3_wc_mv_clips.tar.gz
RUN curl -fsSL "$SC3_MV_MEDIA_URL" | tar -xz -C /repo/apps/api/media
# Input-viewer GT-demo + DP/Pi0.5 input comparison clips (PickMeat, StackCube,
# 2SC/3SC, LiftBarrier probe) — re-hosted off the dead `helps-adjusted-sharp-bind`
# trycloudflare quick-tunnel that broke the input-viewer cells across Lift Barrier,
# Pick Meat and Stacking Cubes. Re-encoded h264 crf30 +faststart (2.1GB raw ->
# ~0.7GB). Structure <task>/videos/<ep>.mp4 matches the cell JS path build unchanged.
ARG INPUTVIEWER_MEDIA_URL=https://huggingface.co/datasets/mikulrai/field-notes-liftbarrier-media/resolve/main/inputviewer_media.tar.gz
RUN curl -fsSL "$INPUTVIEWER_MEDIA_URL" | tar -xz -C /repo/apps/api/media
# Input-viewer STILL IMAGES (filmstrips/ PNGs for the LiftBarrier probe cell,
# thumbs/ JPG video posters for the StackCube/2SC/3SC viewers). The first
# inputviewer tarball was built with `find -name '*.mp4'`, which dropped every
# image file -> filmstrip <img> 404'd while videos worked. These overlay the
# <task>/{filmstrips,thumbs}/ subdirs alongside the existing videos/.
ARG INPUTVIEWER_IMAGES_URL=https://huggingface.co/datasets/mikulrai/field-notes-liftbarrier-media/resolve/main/inputviewer_images.tar.gz
RUN curl -fsSL "$INPUTVIEWER_IMAGES_URL" | tar -xz -C /repo/apps/api/media
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
