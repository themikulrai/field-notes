// Zustand store. Optimistic updates: mutate local state immediately, fire API
// call, reconcile with server truth on resolve. SSE events from the same
// client are deduped by checking event id against a recent-watermark Set.

import { create } from "zustand";
import * as api from "./api";
import type {
  Cell,
  CellCreate,
  CellKind,
  CellStatus,
  CellUpdate,
  Project,
  Verdict,
  VerdictState,
} from "./types";

type Filter = "all" | CellStatus;

const COLLAPSE_KEY = "field-notes-collapsed";
const COLLAPSED_CELLS_KEY = "field-notes-collapsed-cells";

function loadCollapsed(): Record<string, Record<string, boolean>> {
  try {
    const raw = typeof localStorage !== "undefined" ? localStorage.getItem(COLLAPSE_KEY) : null;
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, Record<string, boolean>>;
    // One-shot migration: keys used to be `${cell.id}#${idx}`; strip the suffix.
    // Existing entries are otherwise orphaned and sections appear expanded.
    let migrated = false;
    for (const pid of Object.keys(parsed)) {
      const proj = parsed[pid];
      for (const oldKey of Object.keys(proj)) {
        const hash = oldKey.indexOf("#");
        if (hash > 0) {
          const newKey = oldKey.slice(0, hash);
          // Don't clobber an existing new-shape entry; OR the booleans.
          proj[newKey] = proj[newKey] || proj[oldKey];
          delete proj[oldKey];
          migrated = true;
        }
      }
    }
    if (migrated) {
      try {
        localStorage.setItem(COLLAPSE_KEY, JSON.stringify(parsed));
      } catch {
        /* ignore */
      }
    }
    return parsed;
  } catch {
    /* ignore */
  }
  return {};
}

function saveCollapsed(c: Record<string, Record<string, boolean>>) {
  try {
    localStorage.setItem(COLLAPSE_KEY, JSON.stringify(c));
  } catch {
    /* ignore */
  }
}

function loadCollapsedCells(): Record<string, Record<string, boolean>> {
  try {
    const raw = typeof localStorage !== "undefined" ? localStorage.getItem(COLLAPSED_CELLS_KEY) : null;
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return {};
}

function saveCollapsedCells(c: Record<string, Record<string, boolean>>) {
  try {
    localStorage.setItem(COLLAPSED_CELLS_KEY, JSON.stringify(c));
  } catch {
    /* ignore */
  }
}

interface StoreState {
  projects: Project[];
  activeProjectId: string | null;
  cellsByProject: Record<string, Cell[]>;
  filter: Filter;
  collapsedSections: Record<string, Record<string, boolean>>;
  collapsedCells: Record<string, Record<string, boolean>>;
  loading: boolean;
  error: string | null;

  loadProjects: () => Promise<void>;
  loadCells: (pid: string) => Promise<void>;
  setActiveProject: (pid: string | null) => void;
  setFilter: (f: Filter) => void;
  // Apply a filter received via SSE (ui.filter_changed). Identical to setFilter
  // but the name signals "no API write" — agents only set filters by hitting
  // the API directly; the event flows back to all subscribers including the
  // origin client, and we must not bounce it back.
  applyRemoteFilter: (f: Filter) => void;

  createProject: (name: string) => Promise<Project | null>;
  deleteProject: (pid: string) => Promise<void>;
  // Move a project to `toIndex` in the tab strip (optimistic, persisted).
  reorderProject: (pid: string, toIndex: number) => Promise<void>;

  setVerdict: (cid: string, state: VerdictState | null, note: string) => Promise<void>;
  lockCell: (cid: string) => Promise<void>;
  unlockCell: (cid: string) => Promise<void>;
  reorderCell: (cid: string, direction: "up" | "down") => Promise<void>;
  createCell: (pid: string, body: CellCreate) => Promise<void>;
  updateCell: (cid: string, body: CellUpdate) => Promise<void>;
  deleteCell: (cid: string) => Promise<void>;
  addMarkdownCell: (pid: string, atIndex: number) => Promise<void>;
  addEmptyCell: (pid: string, atIndex: number) => Promise<void>;
  addSectionCell: (pid: string, atIndex: number) => Promise<void>;
  // Anchor-based variants: pass the id of the cell to insert AFTER, or null
  // to insert at the top of the list. Used by the in-tree CellInserter so we
  // don't have to translate tree-space gap indices into flat-array indices.
  addMarkdownCellAfter: (pid: string, afterCellId: string | null) => Promise<void>;
  addEmptyCellAfter: (pid: string, afterCellId: string | null) => Promise<void>;
  addSectionCellAfter: (pid: string, afterCellId: string | null) => Promise<void>;

  toggleSection: (pid: string, key: string) => void;
  isSectionCollapsed: (pid: string, key: string) => boolean;
  toggleCell: (pid: string, cid: string) => void;
  isCellCollapsed: (pid: string, cid: string) => boolean;

  // Live-event hooks
  applyEvent: (env: {
    kind: string;
    project_id?: string | null;
    cell_id?: string | null;
    id: string;
    payload?: Record<string, unknown>;
  }) => Promise<void>;
  patchCell: (pid: string, cell: Cell) => void;
  removeCell: (pid: string, cid: string) => void;

  clearError: () => void;
}

// Silent refresh of projects (and their counts) without toggling `loading`.
// Used by SSE handlers to keep inactive-tab pip counts up to date.
function refreshProjectCounts(set: (partial: Partial<StoreState>) => void): void {
  api
    .listProjects()
    .then((ps) => set({ projects: ps }))
    .catch(() => {
      /* ignore — next event will retry */
    });
}

// Helper: find cell + project for a given cell id.
function findCellLocation(
  cellsByProject: Record<string, Cell[]>,
  cid: string,
): { pid: string; idx: number } | null {
  for (const pid of Object.keys(cellsByProject)) {
    const idx = cellsByProject[pid].findIndex((c) => c.id === cid);
    if (idx >= 0) return { pid, idx };
  }
  return null;
}

export const useStore = create<StoreState>((set, get) => ({
  projects: [],
  activeProjectId: null,
  cellsByProject: {},
  filter: "all",
  collapsedSections: loadCollapsed(),
  collapsedCells: loadCollapsedCells(),
  loading: false,
  error: null,

  clearError: () => set({ error: null }),

  loadProjects: async () => {
    set({ loading: true, error: null });
    try {
      const ps = await api.listProjects();
      set({ projects: ps, loading: false });
    } catch (e) {
      set({ loading: false, error: (e as Error).message });
    }
  },

  loadCells: async (pid) => {
    try {
      const cs = await api.listCells(pid);
      set((s) => {
        const next: Partial<StoreState> = { cellsByProject: { ...s.cellsByProject, [pid]: cs } };
        // Initialize the filter pill from the project's persisted ui_filter,
        // but only for the active project (don't clobber the filter while the
        // user is looking at a different tab).
        if (s.activeProjectId === pid) {
          const proj = s.projects.find((p) => p.id === pid);
          if (proj?.ui_filter) next.filter = proj.ui_filter as Filter;
        }
        return next;
      });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  setActiveProject: (pid) => {
    // When switching tabs, seed the filter from the project's persisted ui_filter
    // (set by MCP set_filter / direct API write) — fallback to "all".
    const proj = pid ? get().projects.find((p) => p.id === pid) : null;
    const f: Filter = (proj?.ui_filter as Filter | undefined) ?? "all";
    set({ activeProjectId: pid, filter: f });
  },
  setFilter: (f) => set({ filter: f }),
  applyRemoteFilter: (f) => set({ filter: f }),

  createProject: async (name) => {
    try {
      const p = await api.createProject({ name });
      set((s) => ({ projects: [...s.projects, p], activeProjectId: p.id, filter: "all" }));
      // Pre-seed empty cell list so the UI doesn't await another fetch.
      set((s) => ({ cellsByProject: { ...s.cellsByProject, [p.id]: [] } }));
      return p;
    } catch (e) {
      set({ error: (e as Error).message });
      return null;
    }
  },

  deleteProject: async (pid) => {
    const prev = get().projects;
    const prevActive = get().activeProjectId;
    const remaining = prev.filter((p) => p.id !== pid);
    const nextActive = prevActive === pid ? (remaining[0]?.id ?? null) : prevActive;
    set({ projects: remaining, activeProjectId: nextActive });
    try {
      await api.deleteProject(pid);
    } catch (e) {
      set({ projects: prev, activeProjectId: prevActive, error: (e as Error).message });
    }
  },

  reorderProject: async (pid, toIndex) => {
    const prev = get().projects;
    const from = prev.findIndex((p) => p.id === pid);
    if (from < 0) return;
    const clamped = Math.max(0, Math.min(toIndex, prev.length - 1));
    if (from === clamped) return;
    // Optimistic splice so the tab moves immediately.
    const next = [...prev];
    const [moved] = next.splice(from, 1);
    next.splice(clamped, 0, moved);
    set({ projects: next });
    try {
      await api.reorderProject(pid, { position: clamped });
      // Reconcile with canonical server positions (silent — no loading flicker).
      const ps = await api.listProjects();
      set({ projects: ps });
    } catch (e) {
      set({ projects: prev, error: (e as Error).message });
    }
  },

  setVerdict: async (cid, state, note) => {
    const loc = findCellLocation(get().cellsByProject, cid);
    if (!loc) return;
    const before = get().cellsByProject[loc.pid][loc.idx];
    // Optimistic: project new verdict + new status locally.
    const optimistic: Cell = {
      ...before,
      verdict: state
        ? ({ state, note, by: "you", at: new Date().toISOString() } as Verdict)
        : null,
      status: state ? (state === "accept" ? "verified" : "rejected") : "open",
    };
    set((s) => {
      const next = [...s.cellsByProject[loc.pid]];
      next[loc.idx] = optimistic;
      return { cellsByProject: { ...s.cellsByProject, [loc.pid]: next } };
    });
    try {
      const fresh = state
        ? await api.setVerdict(cid, { state, note })
        : await api.clearVerdict(cid);
      get().patchCell(loc.pid, fresh);
    } catch (e) {
      // Rollback
      set((s) => {
        const next = [...s.cellsByProject[loc.pid]];
        next[loc.idx] = before;
        return { cellsByProject: { ...s.cellsByProject, [loc.pid]: next }, error: (e as Error).message };
      });
    }
  },

  lockCell: async (cid) => {
    const loc = findCellLocation(get().cellsByProject, cid);
    if (!loc) return;
    try {
      const fresh = await api.lockCell(cid);
      get().patchCell(loc.pid, fresh);
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  unlockCell: async (cid) => {
    const loc = findCellLocation(get().cellsByProject, cid);
    if (!loc) return;
    try {
      const fresh = await api.unlockCell(cid);
      get().patchCell(loc.pid, fresh);
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  reorderCell: async (cid, direction) => {
    const loc = findCellLocation(get().cellsByProject, cid);
    if (!loc) return;
    const arr = get().cellsByProject[loc.pid];
    const target = direction === "up" ? loc.idx - 1 : loc.idx + 1;
    if (target < 0 || target >= arr.length) return;
    // Optimistic swap
    const next = [...arr];
    [next[loc.idx], next[target]] = [next[target], next[loc.idx]];
    set((s) => ({ cellsByProject: { ...s.cellsByProject, [loc.pid]: next } }));
    try {
      await api.reorderCell(cid, { direction });
      await get().loadCells(loc.pid); // canonical positions
    } catch (e) {
      set((s) => ({ cellsByProject: { ...s.cellsByProject, [loc.pid]: arr }, error: (e as Error).message }));
    }
  },

  createCell: async (pid, body) => {
    try {
      const c = await api.createCell(pid, body);
      // Splice the new cell in at the position the server placed it
      // (derived from after_cell_id in the request body), instead of
      // appending and refetching. Avoids a perceived-lag "appears at
      // bottom, then teleports" flicker while loadCells is in flight.
      set((s) => {
        const arr = s.cellsByProject[pid] || [];
        // SSE may have already added this cell via loadCells; don't double it.
        if (arr.some((x) => x.id === c.id)) {
          return s;
        }
        const anchorId = (body as { after_cell_id?: string | null }).after_cell_id ?? null;
        let insertAt: number;
        if (anchorId == null) {
          // null anchor → insert at the top of the list
          insertAt = 0;
        } else {
          const found = arr.findIndex((x) => x.id === anchorId);
          // Anchor missing (e.g. deleted between click and response):
          // defensively append to the end so the cell isn't lost.
          insertAt = found < 0 ? arr.length : found + 1;
        }
        const next = [...arr.slice(0, insertAt), c, ...arr.slice(insertAt)];
        return { cellsByProject: { ...s.cellsByProject, [pid]: next } };
      });
      // No loadCells refetch — the spliced position matches the server's
      // canonical order. SSE cell.created will arrive shortly and patchCell
      // (via applyEvent → loadCells) is idempotent for already-present ids.
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  updateCell: async (cid, body) => {
    const loc = findCellLocation(get().cellsByProject, cid);
    if (!loc) return;
    const before = get().cellsByProject[loc.pid][loc.idx];
    const optimistic = { ...before, ...body } as Cell;
    set((s) => {
      const next = [...s.cellsByProject[loc.pid]];
      next[loc.idx] = optimistic;
      return { cellsByProject: { ...s.cellsByProject, [loc.pid]: next } };
    });
    try {
      const fresh = await api.updateCell(cid, body);
      get().patchCell(loc.pid, fresh);
    } catch (e) {
      set((s) => {
        const next = [...s.cellsByProject[loc.pid]];
        next[loc.idx] = before;
        return { cellsByProject: { ...s.cellsByProject, [loc.pid]: next }, error: (e as Error).message };
      });
    }
  },

  deleteCell: async (cid) => {
    const loc = findCellLocation(get().cellsByProject, cid);
    if (!loc) return;
    const before = get().cellsByProject[loc.pid];
    set((s) => ({
      cellsByProject: { ...s.cellsByProject, [loc.pid]: before.filter((c) => c.id !== cid) },
    }));
    try {
      await api.deleteCell(cid);
    } catch (e) {
      set((s) => ({ cellsByProject: { ...s.cellsByProject, [loc.pid]: before }, error: (e as Error).message }));
    }
  },

  addMarkdownCell: async (pid, atIndex) => {
    const arr = get().cellsByProject[pid] || [];
    const after = atIndex > 0 ? arr[atIndex - 1]?.id ?? null : null;
    await get().createCell(pid, { kind: "markdown" as CellKind, after_cell_id: after, body: "" });
  },
  addEmptyCell: async (pid, atIndex) => {
    const arr = get().cellsByProject[pid] || [];
    const after = atIndex > 0 ? arr[atIndex - 1]?.id ?? null : null;
    await get().createCell(pid, { kind: "empty" as CellKind, after_cell_id: after });
  },
  addSectionCell: async (pid, atIndex) => {
    const arr = get().cellsByProject[pid] || [];
    const after = atIndex > 0 ? arr[atIndex - 1]?.id ?? null : null;
    // Body is "## " (trailing space) so inferSections treats it as a heading
    // even though the heading text is empty — SectionGroup starts in edit mode
    // when the heading text is effectively empty.
    await get().createCell(pid, { kind: "markdown" as CellKind, after_cell_id: after, body: "## " });
  },

  addMarkdownCellAfter: async (pid, afterCellId) => {
    await get().createCell(pid, { kind: "markdown" as CellKind, after_cell_id: afterCellId, body: "" });
  },
  addEmptyCellAfter: async (pid, afterCellId) => {
    await get().createCell(pid, { kind: "empty" as CellKind, after_cell_id: afterCellId });
  },
  addSectionCellAfter: async (pid, afterCellId) => {
    // Same "## " seed as addSectionCell; see comment there.
    await get().createCell(pid, { kind: "markdown" as CellKind, after_cell_id: afterCellId, body: "## " });
  },

  toggleSection: (pid, key) => {
    set((s) => {
      const cur = s.collapsedSections[pid] || {};
      const nextProj = { ...cur, [key]: !cur[key] };
      const next = { ...s.collapsedSections, [pid]: nextProj };
      saveCollapsed(next);
      return { collapsedSections: next };
    });
  },
  isSectionCollapsed: (pid, key) => {
    const cur = get().collapsedSections[pid];
    return !!cur?.[key];
  },

  toggleCell: (pid, cid) => {
    set((s) => {
      const cur = s.collapsedCells[pid] || {};
      const nextProj = { ...cur, [cid]: !cur[cid] };
      const next = { ...s.collapsedCells, [pid]: nextProj };
      saveCollapsedCells(next);
      return { collapsedCells: next };
    });
  },
  isCellCollapsed: (pid, cid) => {
    const cur = get().collapsedCells[pid];
    return !!cur?.[cid];
  },

  applyEvent: async (env) => {
    // Coarse-grained: re-fetch when content shape changes, patch when small.
    const pid = env.project_id || get().activeProjectId;
    if (!pid) return;
    if (env.kind === "ui.filter_changed") {
      // Only apply if it's for the active project; otherwise we'd flip the
      // filter pill on a tab the user isn't looking at.
      if (pid !== get().activeProjectId) return;
      const payload = env.payload as { filter?: string } | undefined;
      const f = payload?.filter as Filter | undefined;
      if (f === "all" || f === "in_progress" || f === "open" || f === "verified" || f === "rejected") {
        get().applyRemoteFilter(f);
      }
      return;
    }
    if (env.kind.startsWith("project.")) {
      await get().loadProjects();
      return;
    }
    if (env.kind === "cell.created" || env.kind === "cell.deleted") {
      await get().loadCells(pid);
      refreshProjectCounts(set);
      return;
    }
    if (env.cell_id && (env.kind === "cell.updated" || env.kind.startsWith("verdict.") || env.kind.startsWith("cell."))) {
      try {
        const fresh = await api.getCell(env.cell_id);
        get().patchCell(pid, fresh);
      } catch {
        await get().loadCells(pid);
      }
      refreshProjectCounts(set);
    }
  },

  patchCell: (pid, cell) => {
    set((s) => {
      const arr = s.cellsByProject[pid] || [];
      const idx = arr.findIndex((c) => c.id === cell.id);
      const next = idx >= 0 ? [...arr] : [...arr, cell];
      if (idx >= 0) next[idx] = cell;
      return { cellsByProject: { ...s.cellsByProject, [pid]: next } };
    });
  },

  removeCell: (pid, cid) => {
    set((s) => {
      const arr = s.cellsByProject[pid] || [];
      return { cellsByProject: { ...s.cellsByProject, [pid]: arr.filter((c) => c.id !== cid) } };
    });
  },
}));
