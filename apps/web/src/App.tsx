// Top-level layout: tabs + brand + stats + filter + cells list (with sections).
// Wires the store; the live-events hook re-fetches/patches state from SSE.

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useStore } from "./lib/store";
import { useLiveEvents } from "./lib/live";
import { getApiKey } from "./lib/api";
import { fmtAgo } from "./lib/format";
import { inferSections, lastCellId, type SectionNode } from "./lib/sections";

import { KeyGate } from "./components/KeyGate";
import { ErrorBanner } from "./components/ErrorBanner";
import { ProjectTabStrip } from "./components/ProjectTabStrip";
import { FilterBar } from "./components/FilterBar";
import { Cell } from "./components/Cell";
import { MarkdownCell } from "./components/MarkdownCell";
import { EmptyCell } from "./components/EmptyCell";
import { CellInserter } from "./components/CellInserter";
import { SectionGroup } from "./components/SectionGroup";
import { TableOfContents } from "./components/TableOfContents";
import { TocToggle } from "./components/TocToggle";
import type { Cell as CellData, CellStatus } from "./lib/types";

export default function App() {
  if (!getApiKey()) return <KeyGate />;
  return <Main />;
}

function Main() {
  const projects = useStore((s) => s.projects);
  const activeId = useStore((s) => s.activeProjectId);
  const cellsByProject = useStore((s) => s.cellsByProject);
  const filter = useStore((s) => s.filter);
  const collapsedSections = useStore((s) => s.collapsedSections);
  const [tocHidden, setTocHidden] = useState(false);

  const loadProjects = useStore((s) => s.loadProjects);
  const loadCells = useStore((s) => s.loadCells);
  const setActiveProject = useStore((s) => s.setActiveProject);
  const setFilter = useStore((s) => s.setFilter);
  const createProject = useStore((s) => s.createProject);
  const deleteProject = useStore((s) => s.deleteProject);

  const setVerdict = useStore((s) => s.setVerdict);
  const unlockCell = useStore((s) => s.unlockCell);
  const reorderCell = useStore((s) => s.reorderCell);
  const collapsedCells = useStore((s) => s.collapsedCells);
  const toggleCell = useStore((s) => s.toggleCell);
  const deleteCell = useStore((s) => s.deleteCell);
  const updateCell = useStore((s) => s.updateCell);
  const addMarkdownCell = useStore((s) => s.addMarkdownCell);
  const addEmptyCell = useStore((s) => s.addEmptyCell);
  const addSectionCell = useStore((s) => s.addSectionCell);
  const addMarkdownCellAfter = useStore((s) => s.addMarkdownCellAfter);
  const addEmptyCellAfter = useStore((s) => s.addEmptyCellAfter);
  const addSectionCellAfter = useStore((s) => s.addSectionCellAfter);
  const toggleSection = useStore((s) => s.toggleSection);

  // Load projects on mount
  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  // Default active project
  useEffect(() => {
    if (!activeId && projects.length > 0) setActiveProject(projects[0].id);
  }, [activeId, projects, setActiveProject]);

  // Load cells whenever active project changes
  useEffect(() => {
    if (activeId && !cellsByProject[activeId]) void loadCells(activeId);
  }, [activeId, cellsByProject, loadCells]);

  useLiveEvents();

  const activeProject = projects.find((p) => p.id === activeId);
  const cells = (activeId && cellsByProject[activeId]) || [];

  const counts = useMemo(() => {
    const c = {
      all: 0,
      in_progress: 0,
      open: 0,
      verified: 0,
      rejected: 0,
    } as Record<"all" | CellStatus, number>;
    for (const x of cells) {
      if (x.kind !== "agent") continue;
      c.all++;
      if (x.status) c[x.status]++;
    }
    return c;
  }, [cells]);

  // Filter: markdown cells always visible; empty cells visible only when "all".
  const visibleCells: CellData[] = useMemo(() => {
    if (filter === "all") return cells;
    return cells.filter((c) => c.kind === "markdown" || (c.kind === "agent" && c.status === filter));
  }, [cells, filter]);

  const sections = useMemo(() => inferSections(visibleCells), [visibleCells]);

  // Bug 5: the reorder up/down buttons must gate on TRUE flat-array
  // boundaries, not on the local position inside a SectionNode's siblings.
  // Otherwise the first child of a section has its "up" button disabled
  // even though the backend supports moving across section boundaries on
  // the flat array. We build a cell-id -> flat-index map from visibleCells
  // (the same array that feeds inferSections) and pass those indices to
  // child components for their disabled-state checks.
  const flatIndex = useMemo(() => {
    const m = new Map<string, number>();
    visibleCells.forEach((c, i) => m.set(c.id, i));
    return m;
  }, [visibleCells]);
  const flatTotal = visibleCells.length;

  // Hooks must run on every render in the same order — keep them above the
  // `if (!activeProject)` early-return below. `projectId` falls back to "" so
  // the closure is still stable; the no-project branch never renders any
  // CellInserter so the empty id is never used.
  const projectId = activeProject?.id ?? "";
  const insertAfter = useCallback(
    (afterId: string | null, key: string): JSX.Element => (
      <CellInserter
        key={key}
        onAddMarkdown={() => void addMarkdownCellAfter(projectId, afterId)}
        onAddEmpty={() => void addEmptyCellAfter(projectId, afterId)}
        onAddSection={() => void addSectionCellAfter(projectId, afterId)}
      />
    ),
    [projectId, addMarkdownCellAfter, addEmptyCellAfter, addSectionCellAfter],
  );

  const lastCellIdBySectionKey = useMemo(() => {
    const m = new Map<string, string>();
    const walk = (n: SectionNode) => {
      m.set(n.key, lastCellId(n));
      n.children?.forEach(walk);
    };
    sections.forEach(walk);
    return m;
  }, [sections]);

  if (!activeProject) {
    return (
      <div className="page">
        <ErrorBanner />
        <div className="empty-create-page">
          <div className="mono">No projects yet.</div>
          <button
            type="button"
            onClick={() => {
              const name = window.prompt("Project name") || "untitled";
              void createProject(name);
            }}
          >
            create your first project
          </button>
        </div>
      </div>
    );
  }

  const inProgress = counts.in_progress;
  const awaiting = counts.open;

  // index/total for the row-level up/down reorder buttons come from the
  // FLAT visibleCells array (see flatIndex above), not from each node's
  // local sibling position. This lets users move a cell out of a section.
  const renderNode = (node: SectionNode): JSX.Element => {
    if (node.kind === "section" && node.cell) {
      const sectionKey = node.key;
      const collapsed = !!collapsedSections[activeProject.id]?.[sectionKey];
      const childNodes = node.children || [];
      // Interleave a CellInserter ONLY between children. The parent loop
      // emits the inserter after the section (anchored to lastCellId(node)),
      // so duplicating it after the last child would stack two visually
      // adjacent "+" rows anchored to the same cell id (Bug A).
      //
      // Empty-section case (Bug B): drop the top-of-children inserter too —
      // it would otherwise anchor to the header cell id and duplicate the
      // outside after-section inserter. Clicking the after-section inserter
      // creates a cell with after_cell_id = headerId; the backend places it
      // as the section's first child, which is the correct UX.
      const interleavedChildren = childNodes.length === 0 ? null : (
        <>
          {insertAfter(node.cell.id, `ins-top-${node.cell.id}`)}
          {childNodes.map((child, i) => (
            <Fragment key={`${child.key}-wrap`}>
              {renderNode(child)}
              {i < childNodes.length - 1 &&
                insertAfter(
                  lastCellIdBySectionKey.get(child.key) ?? lastCellId(child),
                  `ins-after-${child.key}`,
                )}
            </Fragment>
          ))}
        </>
      );
      const sectionFlatIdx = flatIndex.get(node.cell.id) ?? 0;
      return (
        <SectionGroup
          key={sectionKey}
          level={(node.level ?? 2) as 1 | 2 | 3}
          heading={node.heading || ""}
          collapsed={collapsed}
          onToggle={() => toggleSection(activeProject.id, sectionKey)}
          cell={node.cell}
          index={sectionFlatIdx}
          total={flatTotal}
          onReorder={(cid, dir) => void reorderCell(cid, dir)}
          onDelete={(cid) => void deleteCell(cid)}
          onChange={(cid, body) => void updateCell(cid, { body })}
        >
          {interleavedChildren}
        </SectionGroup>
      );
    }
    if (node.kind === "markdown" && node.cell) {
      const fIdx = flatIndex.get(node.cell.id) ?? 0;
      return (
        <MarkdownCell
          key={node.key}
          cell={node.cell}
          index={fIdx}
          total={flatTotal}
          onReorder={(cid, dir) => void reorderCell(cid, dir)}
          onDelete={(cid) => void deleteCell(cid)}
          onChange={(cid, body) => void updateCell(cid, { body })}
        />
      );
    }
    if (node.kind === "cell" && node.cell) {
      const cell = node.cell;
      const fIdx = flatIndex.get(cell.id) ?? 0;
      if (cell.kind === "empty") {
        return (
          <EmptyCell
            key={node.key}
            cell={cell}
            index={fIdx}
            total={flatTotal}
            onReorder={(cid, dir) => void reorderCell(cid, dir)}
            onDelete={(cid) => void deleteCell(cid)}
          />
        );
      }
      return (
        <Cell
          key={node.key}
          cell={cell}
          index={fIdx}
          total={flatTotal}
          collapsed={!!(activeId && collapsedCells[activeId]?.[cell.id])}
          onToggleCollapse={() => activeId && toggleCell(activeId, cell.id)}
          onReorder={(cid, dir) => void reorderCell(cid, dir)}
          onVerdict={(cid, state, note) => void setVerdict(cid, state, note)}
          onUnlock={(cid) => void unlockCell(cid)}
          onDelete={(cid) => void deleteCell(cid)}
          onChange={(cid, patch) => void updateCell(cid, patch)}
        />
      );
    }
    return <></>;
  };

  return (
    <div className="page">
      <ErrorBanner />
      <header className="top">
        <ProjectTabStrip
          projects={projects}
          activeId={activeId}
          onSelect={(pid) => setActiveProject(pid)}
          onClose={(pid) => void deleteProject(pid)}
          onAdd={() => {
            const name = window.prompt("Project name") || "untitled";
            void createProject(name);
          }}
        />
        <div className="top-inner">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22">
                <rect x="3" y="3" width="18" height="18" rx="1" fill="none" stroke="currentColor" strokeWidth="1.6" />
                <line x1="3" y1="9" x2="21" y2="9" stroke="currentColor" strokeWidth="1" />
                <line x1="3" y1="15" x2="21" y2="15" stroke="currentColor" strokeWidth="1" />
                <line x1="9" y1="3" x2="9" y2="21" stroke="currentColor" strokeWidth="1" opacity="0.4" />
                <circle cx="6" cy="6" r="0.8" fill="currentColor" />
              </svg>
            </div>
            <div className="brand-text">
              <div className="brand-name">Field Notes</div>
              <div className="brand-sub mono">
                {activeProject.name}
                {activeProject.subtitle ? ` · ${activeProject.subtitle}` : ""}
              </div>
            </div>
          </div>
          <div className="top-stats">
            <div className="stat">
              <span className="stat-dot" style={{ background: "var(--c-amber)" }} />
              <span className="stat-num">{inProgress}</span>
              <span className="stat-lbl mono">agents working</span>
            </div>
            <div className="stat">
              <span className="stat-dot" style={{ background: "var(--c-blue)" }} />
              <span className="stat-num">{awaiting}</span>
              <span className="stat-lbl mono">awaiting you</span>
            </div>
            <div className="stat">
              <span className="stat-lbl mono dim">last sync</span>
              <span className="stat-num small mono">{fmtAgo(activeProject.updated_at)}</span>
            </div>
          </div>
        </div>
        <FilterBar
          filter={filter}
          counts={counts}
          onSetFilter={setFilter}
          onAddMarkdown={() => void addMarkdownCell(activeProject.id, 0)}
          onAddEmpty={() => void addEmptyCell(activeProject.id, 0)}
          onAddSection={() => void addSectionCell(activeProject.id, 0)}
        />
      </header>

      <div className={tocHidden ? "page-body toc-hidden" : "page-body"}>
        {!tocHidden && <TableOfContents sections={sections} />}
        <main className="cells">
          <TocToggle hidden={tocHidden} onToggle={() => setTocHidden((v) => !v)} />
          {visibleCells.length === 0 && (
            <div className="empty-state mono">
              no cells in <strong>{filter === "all" ? "this view" : filter}</strong> right now.
            </div>
          )}
          {insertAfter(null, "ins-top")}
          {sections.map((node) => (
            <Fragment key={node.key}>
              {renderNode(node)}
              {insertAfter(
                lastCellIdBySectionKey.get(node.key) ?? lastCellId(node),
                `ins-${node.key}`,
              )}
            </Fragment>
          ))}
        </main>
      </div>

      <footer className="foot mono">
        <span>field notes · local working copy</span>
        {activeProject.repo && <span className="dim">{activeProject.repo}</span>}
      </footer>
    </div>
  );
}
