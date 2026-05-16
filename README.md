# Field Notes

ML research notebook with MCP-driven agents. Cells (agent, markdown, empty) live inside projects;
humans verify/reject/lock; agents push results via the MCP server and observe what the human did.

## Quick start (laptop dev)

```
cp .env.example .env
docker-compose up
```

- Web:  http://localhost:5173
- API:  http://localhost:8000/healthz
- DB:   postgres on localhost:5432

## Layout

- `apps/web/` — Vite + React + TS frontend
- `apps/api/` — FastAPI + Postgres backend
- `packages/schema/` — Pydantic models shared by API and MCP
- `packages/mcp_server/` — MCP server (stdio + HTTP/SSE)
- `deploy/` — Fly.io configs
- `tools/seed.py` — imports prototype mock data into the DB

## Tests

```
uv sync
uv run pytest -q
```

## Auth

All requests require `X-Field-Notes-Key`. Set `FIELD_NOTES_KEY` in `.env` (also accepted as `?key=` query param on `/events` for browser EventSource).
