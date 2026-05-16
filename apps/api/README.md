# field-notes-api

FastAPI + Postgres backend.

## Run locally

```bash
# 1. start postgres
docker compose up -d postgres

# 2. apply migrations
cd apps/api
DATABASE_URL=postgresql+asyncpg://field_notes:field_notes@localhost:5432/field_notes \
  uv run alembic upgrade head

# 3. start the api
FIELD_NOTES_KEY=changeme \
DATABASE_URL=postgresql+asyncpg://field_notes:field_notes@localhost:5432/field_notes \
  uv run uvicorn field_notes_api.main:app --reload --port 8000
```

```bash
curl -H "X-Field-Notes-Key: changeme" http://localhost:8000/projects  # -> []
```

## Endpoints

- `GET  /healthz` -> `{"ok": true}` (public)
- `GET/POST /projects`, `GET/PATCH/DELETE /projects/{pid}`, `GET /projects/{pid}/cells`
- `POST /projects/{pid}/cells`, `GET/PATCH/DELETE /cells/{cid}`, `POST /cells/{cid}/reorder`
- `POST /cells/{cid}/verdict` (body or `null`), `POST /cells/{cid}/lock`, `POST /cells/{cid}/unlock`
- `GET /events` -> `text/event-stream`; auth via `?key=` (because EventSource cannot send headers)

All non-healthz/non-events endpoints require `X-Field-Notes-Key: <FIELD_NOTES_KEY>`.

## Tests

By default tests run against an in-memory SQLite (no Docker required). To run
against a real Postgres set `TEST_DATABASE_URL`.

```bash
uv run pytest -q             # 45 tests, ~3s on SQLite
```
