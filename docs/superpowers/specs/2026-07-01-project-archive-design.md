# Project Archive — Design

**Date:** 2026-07-01
**Status:** Approved, ready for planning

## Problem

Some projects are not being actively worked on. They clutter the project tab
strip but must remain retrievable later. We want to *archive* a project: hide it
from the tab strip without deleting its data, and provide a window to view
archived projects and bring them back (or permanently delete them).

Archive is a reversible soft-hide. Delete stays a hard, irreversible removal.

## Data model (backend)

Add one column to `Project` (`apps/api/field_notes_api/models.py`):

```python
archived: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False, server_default="false"
)
```

- `server_default="false"` keeps it cross-dialect (Postgres prod + SQLite test
  fallback). No pg-only features.
- Alembic migration `0006_project_archived.py`: `add_column` with
  `server_default="false"`, downgrade drops the column.

Schema (`packages/schema/field_notes_schema/__init__.py`):
- `ProjectRead`: add `archived: bool = False`.
- `ProjectUpdate`: add `archived: bool | None = None`.

No new endpoint is needed for archive/unarchive — the existing
`PATCH /projects/{pid}` already applies any field present in `ProjectUpdate`.

## API behavior

`GET /projects` gains a query param controlling which projects are returned:

```
GET /projects?archived=active    # default — only non-archived (the tabs)
GET /projects?archived=archived  # only archived (the modal)
GET /projects?archived=all       # everything
```

- Default `active` preserves existing behavior for the tab strip: archived
  projects never appear as tabs.
- The value is validated (one of `active|archived|all`); anything else → 422.
- Archive = `PATCH /projects/{pid}` body `{"archived": true}`.
- Unarchive = `PATCH /projects/{pid}` body `{"archived": false}`.
- Both already emit `project.updated` over SSE; the web store reloads projects
  on any `project.*` event, so other open clients stay in sync.
- Delete = existing `DELETE /projects/{pid}` (unchanged). Now only invoked from
  the archive modal.

Archived projects retain their `position`. Unarchiving drops them back into the
strip at their old slot; the existing dense-renumber on reorder keeps positions
sane. No separate ordering axis for archived projects.

## Frontend

### Tab strip (`ProjectTabStrip.tsx`)
- The tab **×** now calls `onArchive(pid)` instead of `onClose`/`deleteProject`.
  Rename the prop to `onArchive`; update the aria-label/title to "archive".
- Remove the `canClose = projects.length > 1` guard: archiving the last tab is
  safe and reversible, so it must be allowed.
- The **`.ptab-folder`** element ("projects" folder label) becomes a `<button>`:
  - Bigger folder icon.
  - Click → opens the archive modal (`onOpenArchive`).
  - Keyboard accessible (it is a real button; Enter/Space work for free).

### Archive modal (`ArchiveModal.tsx`, new)
- Centered overlay dialog over a dimmed backdrop.
- Close on Esc or backdrop click; focus-trap not required for v1 but the close
  button is focusable.
- Body: list of archived projects. Each row shows name, subtitle (if any), and
  the status count pips (reuse the existing count rendering pattern).
- Per-row actions:
  - **Unarchive** → `unarchiveProject(pid)`; row leaves the modal, project
    returns to the strip.
  - **Delete forever** → confirm (`window.confirm`), then `deleteProject(pid)`;
    row leaves the modal.
- Empty state: "No archived projects."

### Store (`store.ts`)
- New slice: `archivedProjects: Project[]`.
- `archiveProject(pid)`: optimistic — remove from `projects` (and switch active
  per edge-case #1 below), `PATCH {archived:true}`; on error, roll back.
- `unarchiveProject(pid)`: `PATCH {archived:false}`, then refresh both lists
  (project reappears in `projects`, leaves `archivedProjects`).
- `loadArchivedProjects()`: `GET /projects?archived=archived` → `archivedProjects`.
- `deleteProject(pid)`: kept; called from the modal. Also removes from
  `archivedProjects` if present.

### api.ts
- `listProjects(archived?: "active"|"archived"|"all")` → appends the query param.
- Reuse `updateProject` for archive/unarchive, `deleteProject` for delete. No
  other new API functions.

## Edge cases (decided)

1. **Archiving the active project** → active switches to the first remaining
   active project. If none remain, render a "No active projects — open the
   archive" screen that **still shows the tab strip** (folder button + `+`), so
   the archive stays reachable. (Today's empty-projects screen hides the strip;
   this design fixes that so the user can never get locked out of the archive.)
2. **Archived projects keep `position`**; unarchive returns them to their old
   slot (re-densified by the existing reorder logic). No separate archive order.

## Testing

### API (pytest, `apps/api/tests`)
- Migration `0006` upgrade adds the column with default false; downgrade drops it.
- New project has `archived == false`.
- `PATCH {archived:true}` sets it; `PATCH {archived:false}` clears it.
- `GET /projects` (default) excludes archived.
- `GET /projects?archived=archived` returns only archived.
- `GET /projects?archived=all` returns both.
- `GET /projects?archived=bogus` → 422.
- `DELETE` still removes a (archived) project entirely.

### Web (vitest, `apps/web/src`)
- Clicking a tab's × archives it: removed from strip, active switches, PATCH
  called with `{archived:true}`.
- Clicking the folder button opens the archive modal.
- Modal lists archived projects; unarchive returns a project to the strip;
  delete-forever removes it from the modal.
- Archiving the **last** active project → empty-active screen still renders the
  tab strip so the folder/archive is reachable.
- Esc / backdrop click closes the modal.

## Risks / things to watch

- **SSE reload churn:** archive/unarchive fire `project.updated`, which triggers
  a full projects reload in the store. Fine at current scale; noted.
- **Optimistic archive rollback:** if the PATCH fails, we must restore the
  project *and* the previous active id, mirroring the existing `deleteProject`
  rollback pattern.
- **`canClose` removal:** other tests may assert the last tab can't be closed;
  update them to the new archive semantics.
- **Modal + counts:** archived-project counts come from the same
  `project_counts_map`; the `archived=archived` list must still populate counts
  so the modal rows aren't blank.
