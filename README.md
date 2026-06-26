# Field Notes

ML research notebook with MCP-driven agents. Cells (agent, markdown, empty) live
inside projects; humans verify / reject / lock; agents push results via the MCP
server and observe what the human did.

## Run it yourself (local, no setup)

One command — needs only [uv](https://docs.astral.sh/uv/). No Node, no Docker,
no database server:

```bash
uvx --from git+https://github.com/themikulrai/field-notes field-notes serve
```

This creates `~/.field-notes/` (a SQLite DB + a `media/` folder), runs the
migrations, and opens the notebook at <http://127.0.0.1:8000>. **Your data is
that one folder** — back it up by copying it. It binds to loopback with auth
disabled, so there's no key to manage; to expose it on a network pass
`--host 0.0.0.0 --key <secret>`.

Point an MCP host (Claude Code, etc.) at the local API. The `local` key is a
throwaway — the loopback server ignores it:

```json
{
  "mcpServers": {
    "field-notes": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/themikulrai/field-notes", "field-notes-mcp"],
      "env": { "FIELD_NOTES_API_URL": "http://127.0.0.1:8000", "FIELD_NOTES_KEY": "local" }
    }
  }
}
```

### Bring your existing notes (no data loss)

Migrate a hosted instance into your local copy. It's a **copy** — the source
DB is never written:

```bash
# 1. copy projects / cells / verdicts / events (preserves IDs + links)
field-notes import-db --source "postgres://…your DATABASE_URL…"
# 2. download the baked media tarballs so /media/... references resolve
field-notes fetch-media
# 3. report any media a cell references but the local copy is missing
field-notes verify-media
# 4. open it
field-notes serve
```

If you outgrow SQLite (heavy parallel agent writes), point at Postgres with the
same code: `DATABASE_URL=postgres://… field-notes serve`.

## Architecture

```
                      +----------------------------+
                      |    Web (Vite + React + TS) |
                      |    apps/web/               |
                      |    Zustand store + SSE     |
                      +-------------+--------------+
                                    | fetch + EventSource
                                    v
+----------------+   stdio   +------+-----------+   asyncpg   +------------+
|  Claude Code   +<--------->+   MCP server     +<----------->+ Postgres   |
|   (or any      |   HTTP/   |   packages/mcp_  |   +         |   16       |
|    MCP host)   |   SSE     |   server/        |   pydantic  |            |
+----------------+           +------+-----------+             +------+-----+
                                    | httpx (REST)                   ^
                                    v                                |
                              +-----+------------------+             |
                              |   FastAPI API          +-------------+
                              |   apps/api/            |   SQLAlchemy 2.x
                              |   + StaticFiles SPA    |
                              +------------------------+
```

* **`apps/web/`** — Vite + React + TS frontend. Zustand store mirrors API
  state, optimistic mutations, SSE-driven live updates.
* **`apps/api/`** — FastAPI + Postgres backend (SQLite fallback for tests).
  Cells / Projects / Verdicts / Lock + SSE events.
* **`packages/schema/`** — Pydantic models shared by API and MCP. The TS
  mirror in `apps/web/src/lib/types.ts` matches by convention.
* **`packages/mcp_server/`** — MCP server (stdio + HTTP/SSE). Read tools
  (`get_cell`, `get_feedback`, `recent_events`) + write tools (`create_cell`,
  `update_cell`, `set_filter`). Agents cannot set verdicts or lock cells —
  that's the human boundary.
* **`tools/seed.py`** — imports the prototype's mock data into the DB.
* **`deploy/`** — Fly.io single-process deploy config (API serves the SPA).

## Quick start (laptop dev)

```bash
cp .env.example .env
docker-compose up         # postgres + api on :8000, vite dev on :5173
make seed                 # populate the DB with the prototype's mock data
open http://localhost:5173?key=changeme
```

* Web:  `http://localhost:5173`
* API:  `http://localhost:8000/healthz`
* DB:   `postgres on localhost:5432`

The first time you load the web UI, paste the key from `.env` into the prompt
(or append `?key=changeme` to the URL). The key is then stored in
`localStorage`. To rotate, see the **Auth** section below.

### Mock data preview

`make seed` (or `uv run python -m tools.seed`) creates four projects with the
exact cells, conclusions, metrics, charts, verdicts, and locked cell from the
design preview — so what you see locally matches what was in the prototype.
The script is idempotent: re-running it does nothing if the projects already
exist.

Source of the mock data: the prototype's `SEED_CELLS`, `VLA_CELLS`,
`SIM2REAL_CELLS`, `DATA_CELLS`, `SEED_PROJECTS` constants.

## Tests

```bash
# Backend (89+ tests; pytest covers schema, API, MCP, seed, e2e):
uv sync
uv run pytest -q

# Frontend (vitest + jsdom):
cd apps/web && npm install && npm run test

# Type-check + build:
cd apps/web && npm run typecheck && npm run build

# Lint (Python only — ruff):
uv run ruff check . && uv run ruff format --check .
```

End-to-end browser smoke (Playwright, `apps/web/e2e/smoke.spec.ts`) is
`.skip`-d by default. To enable on a host with chromium available:

```bash
cd apps/web
npm install --save-dev @playwright/test
npx playwright install chromium
npm run build
npm run e2e                # remove the `.skip` in smoke.spec.ts first
```

## Auth

The API authenticates every request with the `X-Field-Notes-Key` header (the
browser also accepts `?key=...` on `/events` because `EventSource` can't set
headers). The key is read from the `FIELD_NOTES_KEY` env var.

* **Dev:** `.env` ships with `FIELD_NOTES_KEY=changeme` — fine for laptop work.
* **Prod:** `fly secrets set FIELD_NOTES_KEY=$(openssl rand -hex 32)` and
  redeploy. Old browser sessions will get 401 on next request; tell users to
  clear `localStorage["field-notes-key"]` and re-enter the new key.
* **Rotation:** just `fly secrets set` again. There's no key list — single
  secret, app-wide.

## Production deploy (Fly.io)

Single-process, single-machine: the FastAPI container serves the React build
from `/repo/apps/web/dist` via `StaticFiles`, so there's no separate web tier
and no CORS preflight in production.

```bash
# One-time setup
fly launch --no-deploy --copy-config deploy/fly.toml
fly postgres create --name field-notes-db --region sjc
fly postgres attach field-notes-db          # writes DATABASE_URL secret
fly secrets set FIELD_NOTES_KEY=$(openssl rand -hex 32)

# Deploy
fly deploy --config deploy/fly.toml --remote-only
```

`primary_region` in `deploy/fly.toml` is `sjc` (San Jose); change it if you're
not on the US west coast.

The deploy job in `.github/workflows/ci.yml` does the same `flyctl deploy` on
every push to `main` if the `FLY_API_TOKEN` repo secret is configured.

## MCP install (Claude Code)

Add to your MCP host's config (`~/.config/claude-code/mcp_servers.json` or
similar):

```json
{
  "field-notes": {
    "command": "uv",
    "args": ["run", "--package", "field-notes-mcp", "field-notes-mcp"],
    "cwd": "/path/to/field-notes",
    "env": {
      "FIELD_NOTES_API_URL": "http://localhost:8000",
      "FIELD_NOTES_KEY": "changeme"
    }
  }
}
```

For remote MCP (HTTP/SSE) over the deployed Fly app:

```bash
uv run --package field-notes-mcp field-notes-mcp-http --port 9000
# then point your MCP host at http://localhost:9000/mcp
```

See `packages/mcp_server/README.md` for the full tool list and the agent-vs-
human boundary contract.

## Layout

```
apps/api/                 FastAPI + SQLAlchemy + Alembic + StaticFiles SPA
apps/web/                 Vite + React + TS + Zustand
packages/schema/          Pydantic models (canonical data contract)
packages/mcp_server/      MCP stdio + HTTP/SSE server
tools/seed.py             Import prototype mock data
deploy/fly.toml           Fly.io app config (single-process)
.github/workflows/ci.yml  Backend + frontend tests; deploy gated on FLY_API_TOKEN
tests/                    Cross-cutting tests (seed e2e, mcp e2e)
```
