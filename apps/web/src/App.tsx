// Top-level layout: project tabs + slim title/filter row + cells list (sections).
// Wires the store; the live-events hook re-fetches/patches state from SSE.

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useStore } from "./lib/store";
import { useLiveEvents } from "./lib/live";
import { getApiKey } from "./lib/api";
import { inferSections, lastCellId, type SectionNode } from "./lib/sections";

import { KeyGate } from "./components/KeyGate";
import { ErrorBanner } from "./components/ErrorBanner";
import { ArchiveModal } from "./components/ArchiveModal";
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
  const reorderProject = useStore((s) => s.reorderProject);

  const archivedProjects = useStore((s) => s.archivedProjects);
  const archiveProject = useStore((s) => s.archiveProject);
  const unarchiveProject = useStore((s) => s.unarchiveProject);
  const loadArchivedProjects = useStore((s) => s.loadArchivedProjects);

  const [archiveOpen, setArchiveOpen] = useState(false);

  const openArchive = useCallback(() => {
    void loadArchivedProjects();
    setArchiveOpen(true);
  }, [loadArchivedProjects]);

  const setVerdict = useStore((s) => s.setVerdict);
  const unlockCell = useStore((s) => s.unlockCell);
  const reorderCell = useStore((s) => s.reorderCell);
  const collapsedCells = useStore((s) => s.collapsedCells);
  const toggleCell = useStore((s) => s.toggleCell);
  const deleteCell = useStore((s) => s.deleteCell);
  const updateCell = useStore((s) => s.updateCell);
  const addMarkdownCellAfter = useStore((s) => s.addMarkdownCellAfter);
  const addEmptyCellAfter = useStore((s) => s.addEmptyCellAfter);
  const addSectionCellAfter = useStore((s) => s.addSectionCellAfter);
  const toggleSection = useStore((s) => s.toggleSection);

  // Load projects on mount
  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    void loadArchivedProjects();
  }, [loadArchivedProjects]);

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

  const archiveModal = archiveOpen ? (
    <ArchiveModal
      projects={archivedProjects}
      onUnarchive={(pid) => void unarchiveProject(pid)}
      onDelete={(pid) => void deleteProject(pid)}
      onClose={() => setArchiveOpen(false)}
    />
  ) : null;

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
          onArchive={(pid) => void archiveProject(pid)}
          onOpenArchive={openArchive}
          onReorder={(pid, toIndex) => void reorderProject(pid, toIndex)}
          onAdd={() => {
            const name = window.prompt("Project name") || "untitled";
            void createProject(name);
          }}
        />
        <FilterBar
          title={activeProject.name}
          filter={filter}
          counts={counts}
          onSetFilter={setFilter}
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
        <span>local working copy</span>
        {activeProject.repo && <span className="dim">{activeProject.repo}</span>}
      </footer>
      {archiveModal}
    </div>
  );
}
