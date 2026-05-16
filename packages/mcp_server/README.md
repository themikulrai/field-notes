# field-notes-mcp

The **agent's view** of Field Notes. An MCP server that lets an AI agent (Claude
Code, Claude Desktop, anything speaking MCP) propose research conclusions
through cells, and observe what the human accepts, rejects, or locks.

The agent's whole point is to react to the human's feedback — so this surface
is asymmetric: the agent can write cells, but **only the human can write
verdicts or lock cells**. That asymmetry is enforced both by the tool registry
(no verdict / lock tools) and by a guardrail test
(`tests/test_no_verdict_writes.py`).

## Tools

Read:
- `list_projects()` — list every project.
- `get_project(project_id)` — one project by id.
- `list_cells(project_id, status?, kind?, locked?)` — cells in a project with optional client-side filters.
- `get_cell(cell_id)` — one cell, includes its verdict + locked state.
- `get_feedback(project_id?)` — the primary feedback loop. Returns only cells with a verdict, with `{cell_id, title, status, verdict_state, note, locked, updated_at}`. Omit `project_id` for cross-project.
- `tail_events(project_id?, limit=50)` — last N audit-log events, newest first.

Write:
- `create_project(name, subtitle?, repo?)`
- `update_project(project_id, name?, subtitle?, repo?)`
- `delete_project(project_id)` — cascade-deletes cells.
- `create_cell(project_id, kind, after_cell_id?, ...)` — full `CellCreate` shape.
- `update_cell(cell_id, ...)` — only writable fields. Returns `{error: "locked_cell", message: "...", cell_id}` if the cell is locked.
- `reorder_cell(cell_id, direction|position)` — exactly one of the two.
- `delete_cell(cell_id)` — same locked-cell semantics as update.
- `set_filter(project_id, filter)` — updates the project's UI filter pill (broadcast over SSE so the web view follows along). `filter ∈ all|in_progress|open|verified|rejected`.

**Deliberately omitted** (human-only authority):
- `set_verdict`
- `lock_cell`
- `unlock_cell`

The agent can READ these via `get_cell` / `get_feedback`, but cannot write
them. Adding any of those tools triggers a test failure
(`test_no_verdict_writes.py`).

## Two transports

Both transports share `tools.py` — same registry, same client, just different
plumbing.

### stdio

```bash
python -m field_notes_mcp
```

Env required:
- `FIELD_NOTES_KEY` (required) — shared secret matching the API.
- `FIELD_NOTES_API_URL` (default `http://localhost:8000`).

### HTTP / SSE

```bash
python -m field_notes_mcp.http_server --host 0.0.0.0 --port 7800
```

Additional env:
- `FIELD_NOTES_MCP_HTTP_HOST` (default `127.0.0.1`)
- `FIELD_NOTES_MCP_HTTP_PORT` (default `7800`)

## Claude Code registration

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "field-notes": {
      "command": "uv",
      "args": ["run", "--package", "field-notes-mcp", "python", "-m", "field_notes_mcp"],
      "env": {
        "FIELD_NOTES_API_URL": "http://localhost:8000",
        "FIELD_NOTES_KEY": "changeme"
      }
    }
  }
}
```

## How errors surface

Locked-cell writes return a structured error dict so the agent can recover
without reading exception strings:

```json
{
  "error": "locked_cell",
  "cell_id": "f7b1...",
  "message": "Cell f7b1... is locked by the human. Modifications are blocked. Use get_cell to read the current state."
}
```

Other API errors propagate as MCP tool-call errors via `FieldNotesAPIError`
(status + detail).

## Audit attribution

Every API call from this MCP server carries
`X-Field-Notes-Source: mcp`, which the backend records in
`events.payload.source`. That lets the web UI and humans distinguish what the
agent did from what they did.

## Tests

```bash
uv run pytest packages/mcp_server/tests/      # unit + smoke
uv run pytest tests/test_mcp_e2e.py           # end-to-end boundary test
```

The e2e test is the bedrock: it spins up the FastAPI app in-process, runs the
agent's full flow through MCP tools, has the human (direct API call) set a
verdict + lock the cell, and verifies the agent's writes bounce off with the
structured `locked_cell` error.
