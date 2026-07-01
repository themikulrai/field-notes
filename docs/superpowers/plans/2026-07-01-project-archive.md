# Project Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user archive a project (soft-hide from the tab strip, keep all data) and manage archived projects in a modal window where they can unarchive or permanently delete.

**Architecture:** Add a boolean `archived` column to `Project`. The existing `PATCH /projects/{pid}` toggles it; `GET /projects` gains an `archived=active|archived|all` filter (default `active`). Frontend: the tab × archives instead of deletes, the "projects" folder label becomes a button opening an `ArchiveModal`, and the store gains archive/unarchive/loadArchived actions.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic (Postgres prod / SQLite test), Pydantic schema package, React + Zustand + Vitest frontend.

## Global Constraints

- Cross-dialect ORM only — no JSONB/pg-only features. Boolean column uses `server_default="false"`.
- API tests: `pytest` from repo root; async tests use the `client` fixture in `apps/api/tests/conftest.py`.
- Web tests: run via `apps/web/node_modules/.bin/vitest` (npx is absent).
- Commit author: `git -c user.email="152346781+themikulrai@users.noreply.github.com" -c user.name="themikulrai"`.
- Work happens in worktree `.claude/worktrees/feat-project-archive` on branch `worktree-feat-project-archive`. All paths below are relative to that worktree root.

## File Structure

- `apps/api/field_notes_api/models.py` — add `Project.archived`.
- `apps/api/alembic/versions/0006_project_archived.py` — new migration.
- `packages/schema/field_notes_schema/__init__.py` — `ProjectRead.archived`, `ProjectUpdate.archived`.
- `apps/api/field_notes_api/services.py` — pass `archived` through `project_to_read`.
- `apps/api/field_notes_api/routers/projects.py` — `archived` query param on `list_projects`.
- `apps/web/src/lib/types.ts` — `Project.archived`.
- `apps/web/src/lib/api.ts` — `listProjects(archived?)`.
- `apps/web/src/lib/store.ts` — `archivedProjects` slice + `archiveProject`/`unarchiveProject`/`loadArchivedProjects`.
- `apps/web/src/components/ProjectTabStrip.tsx` — × archives; folder button.
- `apps/web/src/components/ArchiveModal.tsx` — new modal (+ test).
- `apps/web/src/App.tsx` — wire modal, archive action, empty-active screen keeps strip.
- `apps/web/src/styles/app.css` — modal + folder-button styles.

---

### Task 1: Backend `archived` column, migration, schema

**Files:**
- Modify: `apps/api/field_notes_api/models.py` (Project class)
- Create: `apps/api/alembic/versions/0006_project_archived.py`
- Modify: `packages/schema/field_notes_schema/__init__.py` (ProjectRead, ProjectUpdate)
- Modify: `apps/api/field_notes_api/services.py` (project_to_read)
- Test: `apps/api/tests/test_projects.py`

**Interfaces:**
- Produces: `Project.archived: bool` (ORM), `ProjectRead.archived: bool`, `ProjectUpdate.archived: bool | None`. `project_to_read` sets `archived=p.archived`.

- [ ] **Step 1: Write the failing test**

Add to `apps/api/tests/test_projects.py`:

```python
async def test_archived_defaults_false_and_patch_toggles(client) -> None:
    r = await client.post("/projects", json={"name": "arch"})
    pid = r.json()["id"]
    assert r.json()["archived"] is False

    r = await client.patch(f"/projects/{pid}", json={"archived": True})
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is True

    r = await client.patch(f"/projects/{pid}", json={"archived": False})
    assert r.json()["archived"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_projects.py::test_archived_defaults_false_and_patch_toggles -v`
Expected: FAIL — `KeyError: 'archived'` (field absent from ProjectRead).

- [ ] **Step 3: Add the ORM column**

In `apps/api/field_notes_api/models.py`, in `class Project`, after the `position` column add:

```python
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
```

(`Boolean` is already imported.)

- [ ] **Step 4: Add the schema fields**

In `packages/schema/field_notes_schema/__init__.py`:

In `class ProjectRead(ProjectCreate)` add:
```python
    archived: bool = False
```
In `class ProjectUpdate(BaseModel)` add:
```python
    archived: bool | None = None
```

- [ ] **Step 5: Thread it through `project_to_read`**

In `apps/api/field_notes_api/services.py`, in `project_to_read`, add `archived=p.archived,` to the `ProjectRead(...)` construction (e.g. after `position=p.position,`).

- [ ] **Step 6: Write the migration**

Create `apps/api/alembic/versions/0006_project_archived.py`:

```python
"""add archived flag to projects (soft-hide from the tab strip)

Revision ID: 0006_project_archived
Revises: 0005_project_position
Create Date: 2026-07-01

Adds a non-null boolean `archived` column (default false) so projects can be
hidden from the tab strip without deleting their data. Portable server_default
keeps it working on Postgres (prod) and SQLite (test fallback).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_project_archived"
down_revision = "0005_project_position"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("projects", "archived")
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd apps/api && python -m pytest tests/test_projects.py::test_archived_defaults_false_and_patch_toggles -v`
Expected: PASS. (The test DB is created from ORM metadata via conftest, so the column exists without running alembic.)

- [ ] **Step 8: Commit**

```bash
git add apps/api/field_notes_api/models.py apps/api/field_notes_api/services.py \
        apps/api/alembic/versions/0006_project_archived.py \
        packages/schema/field_notes_schema/__init__.py apps/api/tests/test_projects.py
git commit -m "feat(api): add archived flag to projects"
```

---

### Task 2: `GET /projects?archived=` filter

**Files:**
- Modify: `apps/api/field_notes_api/routers/projects.py` (`list_projects`)
- Test: `apps/api/tests/test_projects.py`

**Interfaces:**
- Consumes: `Project.archived` from Task 1.
- Produces: `GET /projects?archived=active|archived|all` (default `active`); invalid value → 422.

- [ ] **Step 1: Write the failing test**

Add to `apps/api/tests/test_projects.py`:

```python
async def test_list_projects_archived_filter(client) -> None:
    a = (await client.post("/projects", json={"name": "active-one"})).json()["id"]
    b = (await client.post("/projects", json={"name": "arch-one"})).json()["id"]
    await client.patch(f"/projects/{b}", json={"archived": True})

    # default: only active
    ids = [p["id"] for p in (await client.get("/projects")).json()]
    assert a in ids and b not in ids

    # archived only
    r = await client.get("/projects", params={"archived": "archived"})
    ids = [p["id"] for p in r.json()]
    assert b in ids and a not in ids

    # all
    r = await client.get("/projects", params={"archived": "all"})
    ids = [p["id"] for p in r.json()]
    assert a in ids and b in ids

    # invalid -> 422
    r = await client.get("/projects", params={"archived": "bogus"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_projects.py::test_list_projects_archived_filter -v`
Expected: FAIL — default `GET /projects` returns the archived project too (no filter yet).

- [ ] **Step 3: Add the query param and filter**

In `apps/api/field_notes_api/routers/projects.py`:

Add `Query` to the fastapi import line:
```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
```
Add `Literal` import at top:
```python
from typing import Literal
```
Replace the `list_projects` function with:

```python
@router.get("", response_model=list[ProjectRead])
async def list_projects(
    archived: Literal["active", "archived", "all"] = Query("active"),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectRead]:
    # Manual tab order first; created_at only as a stable tiebreaker.
    stmt = select(Project).order_by(Project.position, Project.created_at)
    if archived == "active":
        stmt = stmt.where(Project.archived.is_(False))
    elif archived == "archived":
        stmt = stmt.where(Project.archived.is_(True))
    result = await session.execute(stmt)
    projects = list(result.scalars().all())
    counts = await project_counts_map(session, [p.id for p in projects])
    return [project_to_read(p, counts.get(p.id)) for p in projects]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && python -m pytest tests/test_projects.py -v`
Expected: PASS (all project tests, including the existing ones).

- [ ] **Step 5: Commit**

```bash
git add apps/api/field_notes_api/routers/projects.py apps/api/tests/test_projects.py
git commit -m "feat(api): filter GET /projects by archived state"
```

---

### Task 3: Frontend types, api client, store actions

**Files:**
- Modify: `apps/web/src/lib/types.ts` (Project)
- Modify: `apps/web/src/lib/api.ts` (listProjects)
- Modify: `apps/web/src/lib/store.ts` (state + actions)
- Test: `apps/web/src/lib/store.test.ts`

**Interfaces:**
- Consumes: API from Tasks 1–2.
- Produces (store): `archivedProjects: Project[]`, `archiveProject(pid: string): Promise<void>`, `unarchiveProject(pid: string): Promise<void>`, `loadArchivedProjects(): Promise<void>`. `deleteProject` also removes from `archivedProjects`.
- Produces (api): `listProjects(archived?: "active" | "archived" | "all"): Promise<Project[]>`.

- [ ] **Step 1: Add `archived` to the Project type**

In `apps/web/src/lib/types.ts`, in the `Project` interface add:
```typescript
  archived?: boolean;
```

- [ ] **Step 2: Extend `listProjects` in api.ts**

In `apps/web/src/lib/api.ts` replace the `listProjects` function with:
```typescript
export function listProjects(
  archived: "active" | "archived" | "all" = "active",
): Promise<Project[]> {
  const q = archived === "active" ? "" : `?archived=${archived}`;
  return request<Project[]>(`/projects${q}`);
}
```

- [ ] **Step 3: Write the failing store test**

Add to `apps/web/src/lib/store.test.ts` (follow the existing mock-api pattern in that file; the snippet below assumes `api` is mocked — mirror how other tests there stub `api.updateProject`/`api.listProjects`):

```typescript
it("archiveProject removes it from projects and PATCHes archived:true", async () => {
  const { useStore } = await freshStore(); // use whatever helper the file already uses
  const patch = vi.spyOn(api, "updateProject").mockResolvedValue({} as any);
  useStore.setState({
    projects: [
      { id: "p1", name: "one" } as any,
      { id: "p2", name: "two" } as any,
    ],
    activeProjectId: "p1",
  });

  await useStore.getState().archiveProject("p1");

  expect(useStore.getState().projects.map((p) => p.id)).toEqual(["p2"]);
  expect(useStore.getState().activeProjectId).toBe("p2");
  expect(patch).toHaveBeenCalledWith("p1", { archived: true });
});
```

> If `store.test.ts` uses a different setup helper, adapt the harness lines but keep the three assertions. Check the top of the file for the existing `vi.mock("./api")` block and reuse it.

- [ ] **Step 4: Run test to verify it fails**

Run: `apps/web/node_modules/.bin/vitest run src/lib/store.test.ts -t "archiveProject"`
Expected: FAIL — `archiveProject is not a function`.

- [ ] **Step 5: Add state + actions to the store**

In `apps/web/src/lib/store.ts`:

Add to the state interface (near `projects: Project[];`):
```typescript
  archivedProjects: Project[];
  archiveProject: (pid: string) => Promise<void>;
  unarchiveProject: (pid: string) => Promise<void>;
  loadArchivedProjects: () => Promise<void>;
```
Add to the initial state (near `activeProjectId: null,`):
```typescript
  archivedProjects: [],
```
Add the action implementations (place near `deleteProject`):
```typescript
  archiveProject: async (pid) => {
    const prev = get().projects;
    const prevActive = get().activeProjectId;
    const remaining = prev.filter((p) => p.id !== pid);
    const nextActive = prevActive === pid ? (remaining[0]?.id ?? null) : prevActive;
    set({ projects: remaining, activeProjectId: nextActive });
    try {
      await api.updateProject(pid, { archived: true });
    } catch (e) {
      set({ projects: prev, activeProjectId: prevActive, error: (e as Error).message });
    }
  },

  unarchiveProject: async (pid) => {
    try {
      await api.updateProject(pid, { archived: false });
      const [active, archived] = await Promise.all([
        api.listProjects("active"),
        api.listProjects("archived"),
      ]);
      set({ projects: active, archivedProjects: archived });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  loadArchivedProjects: async () => {
    try {
      const ps = await api.listProjects("archived");
      set({ archivedProjects: ps });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },
```
Update `deleteProject` to also drop from `archivedProjects`. Replace its optimistic `set` line so both lists are pruned:
```typescript
  deleteProject: async (pid) => {
    const prev = get().projects;
    const prevArchived = get().archivedProjects;
    const prevActive = get().activeProjectId;
    const remaining = prev.filter((p) => p.id !== pid);
    const nextActive = prevActive === pid ? (remaining[0]?.id ?? null) : prevActive;
    set({
      projects: remaining,
      archivedProjects: prevArchived.filter((p) => p.id !== pid),
      activeProjectId: nextActive,
    });
    try {
      await api.deleteProject(pid);
    } catch (e) {
      set({
        projects: prev,
        archivedProjects: prevArchived,
        activeProjectId: prevActive,
        error: (e as Error).message,
      });
    }
  },
```

- [ ] **Step 6: Run test to verify it passes**

Run: `apps/web/node_modules/.bin/vitest run src/lib/store.test.ts`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/types.ts apps/web/src/lib/api.ts apps/web/src/lib/store.ts apps/web/src/lib/store.test.ts
git commit -m "feat(web): store actions for archive/unarchive/delete"
```

---

### Task 4: Tab × archives; folder becomes an archive button

**Files:**
- Modify: `apps/web/src/components/ProjectTabStrip.tsx`
- Modify: `apps/web/src/components/ProjectTabStrip.test.tsx`
- Modify: `apps/web/src/styles/app.css` (folder button affordance)

**Interfaces:**
- Consumes: nothing new.
- Produces: `StripProps` gains `onArchive: (pid: string) => void` (replaces `onClose`) and `onOpenArchive: () => void`. The per-tab × calls `onArchive`. The folder is a `<button className="ptab-folder">` calling `onOpenArchive`.

- [ ] **Step 1: Update the failing test**

In `apps/web/src/components/ProjectTabStrip.test.tsx`, rename close-related assertions to archive, and add a folder-button test. Representative additions:

```tsx
it("clicking a tab's × calls onArchive, not delete", () => {
  const onArchive = vi.fn();
  render(
    <ProjectTabStrip
      projects={[{ id: "p1", name: "one" } as any, { id: "p2", name: "two" } as any]}
      activeId="p1"
      onSelect={() => {}}
      onArchive={onArchive}
      onOpenArchive={() => {}}
      onAdd={() => {}}
      onReorder={() => {}}
    />,
  );
  fireEvent.click(screen.getByLabelText("archive one"));
  expect(onArchive).toHaveBeenCalledWith("p1");
});

it("clicking the projects folder opens the archive window", () => {
  const onOpenArchive = vi.fn();
  render(
    <ProjectTabStrip
      projects={[{ id: "p1", name: "one" } as any]}
      activeId="p1"
      onSelect={() => {}}
      onArchive={() => {}}
      onOpenArchive={onOpenArchive}
      onAdd={() => {}}
      onReorder={() => {}}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /archived projects/i }));
  expect(onOpenArchive).toHaveBeenCalled();
});
```

> If the existing file has close-tab tests referencing `onClose`, update those to `onArchive` too (the prop no longer exists).

- [ ] **Step 2: Run test to verify it fails**

Run: `apps/web/node_modules/.bin/vitest run src/components/ProjectTabStrip.test.tsx`
Expected: FAIL — `onArchive`/`onOpenArchive` undefined, no folder button role.

- [ ] **Step 3: Update the component**

In `apps/web/src/components/ProjectTabStrip.tsx`:

Change `StripProps`:
```typescript
interface StripProps {
  projects: Project[];
  activeId: string | null;
  onSelect: (pid: string) => void;
  onArchive: (pid: string) => void;
  onOpenArchive: () => void;
  onAdd: () => void;
  onReorder: (pid: string, toIndex: number) => void;
}
```

In the `ProjectTab` component, rename the `onClose` prop to `onArchive` and update the button. Replace the close-button block with:
```tsx
      {active && (
        <button
          className="ptab-close"
          aria-label={`archive ${project.name}`}
          onClick={(e) => {
            e.stopPropagation();
            onArchive();
          }}
          title="archive project"
        >
          <svg viewBox="0 0 12 12" width="10" height="10">
            <path d="M1.5 3.5h9M2.5 3.5v6.5h7V3.5M4.8 6h2.4"
                  stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"
                  fill="none" />
          </svg>
        </button>
      )}
```
(Drop the `canClose` prop and its `projects.length > 1` gating entirely — archiving the last tab is allowed.)

In `ProjectTabStrip`, change the folder markup from a `<div>` to a `<button>`:
```tsx
      <button
        className="ptab-folder"
        onClick={onOpenArchive}
        aria-label="archived projects"
        title="archived projects"
      >
        <svg viewBox="0 0 18 14" width="18" height="15">
          <path
            d="M1 3.5c0-.8.7-1.5 1.5-1.5h3.7c.5 0 1 .2 1.3.6L8.7 4H15.5c.8 0 1.5.7 1.5 1.5v6c0 .8-.7 1.5-1.5 1.5h-13C1.7 13 1 12.3 1 11.5v-8z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
          />
        </svg>
        <span className="mono">projects</span>
      </button>
```
Update each `<ProjectTab>` render: remove `canClose={...}`, and pass `onArchive={() => onArchive(p.id)}` instead of `onClose={() => onClose(p.id)}`. Also remove `canClose` from `ProjectTab`'s prop destructuring/type.

- [ ] **Step 4: Add folder-button styles**

In `apps/web/src/styles/app.css`, find the existing `.ptab-folder` rule. Add button-reset + affordance (keep its existing layout properties):
```css
.ptab-folder {
  background: none;
  border: none;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.ptab-folder:hover {
  color: var(--accent, #4a9eff);
}
.ptab-folder svg {
  transition: transform 0.1s ease;
}
.ptab-folder:hover svg {
  transform: scale(1.08);
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `apps/web/node_modules/.bin/vitest run src/components/ProjectTabStrip.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/ProjectTabStrip.tsx apps/web/src/components/ProjectTabStrip.test.tsx apps/web/src/styles/app.css
git commit -m "feat(web): tab close archives; folder opens archive window"
```

---

### Task 5: ArchiveModal component

**Files:**
- Create: `apps/web/src/components/ArchiveModal.tsx`
- Create: `apps/web/src/components/ArchiveModal.test.tsx`
- Modify: `apps/web/src/styles/app.css` (modal styles)

**Interfaces:**
- Consumes: `Project` type.
- Produces: `ArchiveModal` with props `{ projects: Project[]; onUnarchive: (pid: string) => void; onDelete: (pid: string) => void; onClose: () => void }`. Renders a dialog with one row per project (name + Unarchive + Delete forever), empty state, Esc/backdrop close.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ArchiveModal.test.tsx`:
```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ArchiveModal } from "./ArchiveModal";

const proj = (id: string, name: string) => ({ id, name }) as any;

describe("ArchiveModal", () => {
  it("lists archived projects and fires unarchive/delete", () => {
    const onUnarchive = vi.fn();
    const onDelete = vi.fn();
    render(
      <ArchiveModal
        projects={[proj("p1", "alpha")]}
        onUnarchive={onUnarchive}
        onDelete={onDelete}
        onClose={() => {}}
      />,
    );
    expect(screen.getByText("alpha")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /unarchive alpha/i }));
    expect(onUnarchive).toHaveBeenCalledWith("p1");

    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: /delete alpha/i }));
    expect(onDelete).toHaveBeenCalledWith("p1");
  });

  it("shows an empty state when nothing is archived", () => {
    render(
      <ArchiveModal projects={[]} onUnarchive={() => {}} onDelete={() => {}} onClose={() => {}} />,
    );
    expect(screen.getByText(/no archived projects/i)).toBeInTheDocument();
  });

  it("closes on Escape and backdrop click", () => {
    const onClose = vi.fn();
    render(
      <ArchiveModal projects={[]} onUnarchive={() => {}} onDelete={() => {}} onClose={onClose} />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId("archive-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `apps/web/node_modules/.bin/vitest run src/components/ArchiveModal.test.tsx`
Expected: FAIL — module `./ArchiveModal` not found.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ArchiveModal.tsx`:
```tsx
import { useEffect } from "react";
import type { Project } from "../lib/types";

interface ArchiveModalProps {
  projects: Project[];
  onUnarchive: (pid: string) => void;
  onDelete: (pid: string) => void;
  onClose: () => void;
}

export function ArchiveModal({ projects, onUnarchive, onDelete, onClose }: ArchiveModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="archive-backdrop"
      data-testid="archive-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="archive-modal"
        role="dialog"
        aria-modal="true"
        aria-label="archived projects"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="archive-modal-head">
          <span className="mono">archived projects</span>
          <button className="archive-modal-x" aria-label="close" onClick={onClose}>
            <svg viewBox="0 0 12 12" width="12" height="12">
              <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
        </header>

        {projects.length === 0 ? (
          <div className="archive-empty mono">No archived projects.</div>
        ) : (
          <ul className="archive-list">
            {projects.map((p) => (
              <li key={p.id} className="archive-row">
                <div className="archive-row-info">
                  <div className="archive-row-name">{p.name}</div>
                  {p.subtitle && <div className="archive-row-sub dim">{p.subtitle}</div>}
                </div>
                <div className="archive-row-actions">
                  <button
                    className="archive-unarchive"
                    aria-label={`unarchive ${p.name}`}
                    onClick={() => onUnarchive(p.id)}
                  >
                    unarchive
                  </button>
                  <button
                    className="archive-delete"
                    aria-label={`delete ${p.name}`}
                    onClick={() => {
                      if (window.confirm(`Permanently delete "${p.name}" and all its cells?`)) {
                        onDelete(p.id);
                      }
                    }}
                  >
                    delete forever
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add modal styles**

Append to `apps/web/src/styles/app.css`:
```css
.archive-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.archive-modal {
  background: var(--panel, #1c1c1e);
  border: 1px solid var(--border, #333);
  border-radius: 8px;
  min-width: 420px;
  max-width: 560px;
  max-height: 70vh;
  overflow: auto;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}
.archive-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border, #333);
}
.archive-modal-x {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
}
.archive-empty {
  padding: 32px 16px;
  text-align: center;
  opacity: 0.6;
}
.archive-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.archive-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border, #2a2a2a);
}
.archive-row-actions {
  display: flex;
  gap: 8px;
}
.archive-unarchive,
.archive-delete {
  background: none;
  border: 1px solid var(--border, #444);
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.archive-delete {
  color: #ff6b6b;
  border-color: #5a2a2a;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `apps/web/node_modules/.bin/vitest run src/components/ArchiveModal.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/ArchiveModal.tsx apps/web/src/components/ArchiveModal.test.tsx apps/web/src/styles/app.css
git commit -m "feat(web): ArchiveModal window for archived projects"
```

---

### Task 6: Wire it all in App.tsx (+ empty-active screen keeps strip)

**Files:**
- Modify: `apps/web/src/App.tsx`

**Interfaces:**
- Consumes: store `archiveProject`, `unarchiveProject`, `loadArchivedProjects`, `deleteProject`, `archivedProjects`; `ArchiveModal`; `ProjectTabStrip` (`onArchive`, `onOpenArchive`).

- [ ] **Step 1: Import the modal and select the new store bits**

In `apps/web/src/App.tsx`, add the import:
```typescript
import { ArchiveModal } from "./components/ArchiveModal";
```
Add store selectors (near the other `useStore` selectors):
```typescript
  const archivedProjects = useStore((s) => s.archivedProjects);
  const archiveProject = useStore((s) => s.archiveProject);
  const unarchiveProject = useStore((s) => s.unarchiveProject);
  const loadArchivedProjects = useStore((s) => s.loadArchivedProjects);
```
Add local UI state (near `const [tocHidden, setTocHidden] = useState(false);`):
```typescript
  const [archiveOpen, setArchiveOpen] = useState(false);
```
Add an open handler that refreshes the list first:
```typescript
  const openArchive = useCallback(() => {
    void loadArchivedProjects();
    setArchiveOpen(true);
  }, [loadArchivedProjects]);
```

- [ ] **Step 2: Render the modal (shared by both branches)**

Define a reusable element before the `if (!activeProject)` return:
```tsx
  const archiveModal = archiveOpen ? (
    <ArchiveModal
      projects={archivedProjects}
      onUnarchive={(pid) => void unarchiveProject(pid)}
      onDelete={(pid) => void deleteProject(pid)}
      onClose={() => setArchiveOpen(false)}
    />
  ) : null;
```

- [ ] **Step 3: Replace the empty-projects branch so it keeps the strip**

Replace the whole `if (!activeProject) { return (...) }` block with:
```tsx
  if (!activeProject) {
    return (
      <div className="page">
        <ErrorBanner />
        <header className="top">
          <ProjectTabStrip
            projects={projects}
            activeId={activeId}
            onSelect={(pid) => setActiveProject(pid)}
            onArchive={(pid) => void archiveProject(pid)}
            onOpenArchive={openArchive}
            onReorder={(pid, toIndex) => void reorderProject(pid, toIndex)}
            onAdd={() => {
              const name = window.prompt("Project name") || "untitled";
              void createProject(name);
            }}
          />
        </header>
        <div className="empty-create-page">
          <div className="mono">
            {projects.length === 0 && archivedProjects.length === 0
              ? "No projects yet."
              : "No active projects — open the archive (folder) or create one."}
          </div>
          <button
            type="button"
            onClick={() => {
              const name = window.prompt("Project name") || "untitled";
              void createProject(name);
            }}
          >
            create a project
          </button>
        </div>
        {archiveModal}
      </div>
    );
  }
```

> Note: `archivedProjects` may be empty on first paint here. That's fine — the copy still points at the folder, and clicking it calls `loadArchivedProjects`. To make the count accurate on load, Step 5 adds a mount-time fetch.

- [ ] **Step 4: Update the main `ProjectTabStrip` usage + render the modal**

In the main `return`, change the `ProjectTabStrip` props: replace `onClose={(pid) => void deleteProject(pid)}` with:
```tsx
          onArchive={(pid) => void archiveProject(pid)}
          onOpenArchive={openArchive}
```
And add `{archiveModal}` just before the closing `</div>` of `<div className="page">` (after `</footer>`).

- [ ] **Step 5: Load the archived list on mount**

So the empty-active copy is correct and the modal is warm, extend the mount effect. After the existing `useEffect(() => { void loadProjects(); }, [loadProjects]);` add:
```typescript
  useEffect(() => {
    void loadArchivedProjects();
  }, [loadArchivedProjects]);
```

- [ ] **Step 6: Run the full web suite**

Run: `apps/web/node_modules/.bin/vitest run`
Expected: PASS. If any existing test referenced the old `onClose` prop of `ProjectTabStrip`, update it to `onArchive` and add a stub `onOpenArchive={() => {}}`.

- [ ] **Step 7: Typecheck + lint**

Run: `cd apps/web && node_modules/.bin/tsc --noEmit` (if a `tsconfig` build check exists) and the repo's `ruff` for Python if the Makefile defines it (`make lint` or `ruff check .`).
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/App.tsx
git commit -m "feat(web): wire archive modal + keep strip on empty-active screen"
```

---

### Task 7: End-to-end sanity + full test run

**Files:** none (verification only)

- [ ] **Step 1: Run the whole backend suite**

Run: `cd apps/api && python -m pytest -q`
Expected: PASS.

- [ ] **Step 2: Run the whole web suite**

Run: `apps/web/node_modules/.bin/vitest run`
Expected: PASS.

- [ ] **Step 3: Verify the alembic migration applies against SQLite**

Run (from `apps/api`): `python -c "from alembic.config import Config; from alembic import command; c=Config('alembic.ini'); command.upgrade(c,'head')"` against a scratch SQLite URL, OR the project's existing migration-test if present. Confirm `0006_project_archived` is in `alembic history`.
Expected: upgrade to head succeeds, includes `0006`.

- [ ] **Step 4: Final commit / branch ready**

```bash
git log --oneline -8
```
Confirm the 6 feature commits are present and the tree is clean.

---

## Self-Review

**Spec coverage:**
- `archived` column + migration + schema → Task 1. ✅
- `GET /projects?archived=` filter → Task 2. ✅
- Tab × archives (no delete from strip), no `length>1` guard → Task 4. ✅
- Folder button opens modal → Task 4 + Task 6. ✅
- ArchiveModal (unarchive + delete-forever + empty + Esc/backdrop) → Task 5. ✅
- Store archive/unarchive/loadArchived/delete → Task 3. ✅
- Edge case #1 (archiving active switches; empty-active keeps strip) → Task 3 (`archiveProject` nextActive) + Task 6 (Step 3). ✅
- Edge case #2 (archived keep position; unarchive returns to slot) → server-side default (position untouched by PATCH archived); no code needed. ✅
- SSE reload on `project.updated` → existing store behavior, unchanged. ✅
- Tests (API + web) → Tasks 1,2,3,4,5 each add tests; Task 7 runs full suites. ✅

**Placeholder scan:** No TBD/TODO; every code step has full code. The one soft spot is the store-test harness (Task 3 Step 3) which says "mirror the file's existing mock pattern" — unavoidable without the file's exact mock block, but the three assertions are concrete.

**Type consistency:** `archiveProject`/`unarchiveProject`/`loadArchivedProjects`/`archivedProjects` names match across Tasks 3 and 6. `onArchive`/`onOpenArchive` match across Tasks 4 and 6. `ArchiveModal` props match across Tasks 5 and 6. `listProjects(archived?)` signature matches Task 3 (api) and its callers.
