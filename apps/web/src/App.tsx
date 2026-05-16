// Top-level layout: tabs + brand + stats + filter + cells list (with sections).
// Wires the store; the live-events hook re-fetches/patches state from SSE.

import { useEffect, useMemo } from "react";
import { useStore } from "./lib/store";
import { useLiveEvents } from "./lib/live";
import { getApiKey } from "./lib/api";
import { fmtAgo } from "./lib/format";
import { inferSections, type SectionNode } from "./lib/sections";

import { KeyGate } from "./components/KeyGate";
import { ErrorBanner } from "./components/ErrorBanner";
import { ProjectTabStrip } from "./components/ProjectTabStrip";
import { FilterBar } from "./components/FilterBar";
import { Cell } from "./components/Cell";
import { MarkdownCell } from "./components/MarkdownCell";
import { EmptyCell } from "./components/EmptyCell";
import { CellInserter } from "./components/CellInserter";
import { SectionGroup } from "./components/SectionGroup";
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

  const loadProjects = useStore((s) => s.loadProjects);
  const loadCells = useStore((s) => s.loadCells);
  const setActiveProject = useStore((s) => s.setActiveProject);
  const setFilter = useStore((s) => s.setFilter);
  const createProject = useStore((s) => s.createProject);
  const deleteProject = useStore((s) => s.deleteProject);

  const setVerdict = useStore((s) => s.setVerdict);
  const unlockCell = useStore((s) => s.unlockCell);
  const reorderCell = useStore((s) => s.reorderCell);
  const deleteCell = useStore((s) => s.deleteCell);
  const updateCell = useStore((s) => s.updateCell);
  const addMarkdownCell = useStore((s) => s.addMarkdownCell);
  const addEmptyCell = useStore((s) => s.addEmptyCell);
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

  const renderNode = (node: SectionNode, idx: number, total: number): JSX.Element => {
    if (node.kind === "section" && node.cell) {
      const sectionKey = node.key;
      const collapsed = !!collapsedSections[activeProject.id]?.[sectionKey];
      return (
        <SectionGroup
          key={sectionKey}
          level={node.level || 2}
          heading={node.heading || ""}
          collapsed={collapsed}
          onToggle={() => toggleSection(activeProject.id, sectionKey)}
        >
          {(node.children || []).map((child, i) => renderNode(child, i, (node.children || []).length))}
        </SectionGroup>
      );
    }
    if (node.kind === "markdown" && node.cell) {
      return (
        <MarkdownCell
          key={node.key}
          cell={node.cell}
          index={idx}
          total={total}
          onReorder={(cid, dir) => void reorderCell(cid, dir)}
          onDelete={(cid) => void deleteCell(cid)}
          onChange={(cid, body) => void updateCell(cid, { body })}
        />
      );
    }
    if (node.kind === "cell" && node.cell) {
      const cell = node.cell;
      if (cell.kind === "empty") {
        return (
          <EmptyCell
            key={node.key}
            cell={cell}
            index={idx}
            total={total}
            onReorder={(cid, dir) => void reorderCell(cid, dir)}
            onDelete={(cid) => void deleteCell(cid)}
            onFill={(cid) =>
              void updateCell(cid, {
                title: "Manual entry — investigation",
                agent_id: "human-note",
                status: "open",
                conclusion:
                  "Manual placeholder. Replace with a hypothesis, a link to a thread, or pull in an agent's report.",
              })
            }
          />
        );
      }
      return (
        <Cell
          key={node.key}
          cell={cell}
          index={idx}
          total={total}
          onReorder={(cid, dir) => void reorderCell(cid, dir)}
          onVerdict={(cid, state, note) => void setVerdict(cid, state, note)}
          onUnlock={(cid) => void unlockCell(cid)}
          onDelete={(cid) => void deleteCell(cid)}
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
          cellsByProject={cellsByProject}
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
        />
      </header>

      <main className="cells">
        {visibleCells.length === 0 && (
          <div className="empty-state mono">
            no cells in <strong>{filter === "all" ? "this view" : filter}</strong> right now.
          </div>
        )}
        {visibleCells.length > 0 && (
          <CellInserter
            onAddMarkdown={() => void addMarkdownCell(activeProject.id, 0)}
            onAddEmpty={() => void addEmptyCell(activeProject.id, 0)}
          />
        )}
        {sections.map((node, i) => {
          const out = renderNode(node, i, sections.length);
          const inserter =
            i < sections.length - 1 ? (
              <CellInserter
                key={`${node.key}-ins`}
                onAddMarkdown={() => void addMarkdownCell(activeProject.id, i + 1)}
                onAddEmpty={() => void addEmptyCell(activeProject.id, i + 1)}
              />
            ) : null;
          return (
            <span key={node.key}>
              {out}
              {inserter}
            </span>
          );
        })}
        {visibleCells.length > 0 && (
          <CellInserter
            onAddMarkdown={() => void addMarkdownCell(activeProject.id, cells.length)}
            onAddEmpty={() => void addEmptyCell(activeProject.id, cells.length)}
          />
        )}
      </main>

      <footer className="foot mono">
        <span>field notes · local working copy</span>
        {activeProject.repo && <span className="dim">{activeProject.repo}</span>}
      </footer>
    </div>
  );
}
