# field-notes-api

FastAPI + Postgres backend.

```
uv run uvicorn field_notes_api.main:app --reload --port 8000
```

Health: `GET /healthz` → `{"ok": true}`

Routers, models, auth, and the SSE events bus are placeholders filled in by Chunk 2.
