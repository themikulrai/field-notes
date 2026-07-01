# field-notes-api

FastAPI backend, file-backed SQLite (local single-process self-host).

## Run locally

```bash
# migrations + server in one step: `serve` runs `alembic upgrade head` on the
# SQLite DB under --data-dir, then starts uvicorn (auth disabled on loopback).
uv run field-notes serve --data-dir ~/.field-notes --port 8000
```

```bash
curl http://localhost:8000/projects  # -> []  (loopback = keyless)
```

## Endpoints

- `GET  /healthz` -> `{"ok": true}` (public)
- `GET/POST /projects`, `GET/PATCH/DELETE /projects/{pid}`, `GET /projects/{pid}/cells`
- `POST /projects/{pid}/cells`, `GET/PATCH/DELETE /cells/{cid}`, `POST /cells/{cid}/reorder`
- `POST /cells/{cid}/verdict` (body or `null`), `POST /cells/{cid}/lock`, `POST /cells/{cid}/unlock`
- `GET /events` -> `text/event-stream`; auth via `?key=` (because EventSource cannot send headers)

All non-healthz/non-events endpoints require `X-Field-Notes-Key: <FIELD_NOTES_KEY>`.

## Tests

Tests run against an in-memory SQLite.

```bash
uv run pytest -q
```
