import { useState } from "react";
import type { Project, ProjectCounts } from "../lib/types";

interface StripProps {
  projects: Project[];
  activeId: string | null;
  onSelect: (pid: string) => void;
  onClose: (pid: string) => void;
  onAdd: () => void;
  // Drop `pid` at the displayed index `toIndex` (drag-to-reorder the tab strip).
  onReorder: (pid: string, toIndex: number) => void;
}

const ZERO_COUNTS: ProjectCounts = { in_progress: 0, open: 0, verified: 0, rejected: 0 };

function ProjectTab({
  project,
  active,
  canClose,
  dragging,
  dragOver,
  onClick,
  onClose,
  onDragStart,
  onDragEnter,
  onDragEnd,
  onDrop,
}: {
  project: Project;
  active: boolean;
  canClose: boolean;
  dragging: boolean;
  dragOver: boolean;
  onClick: () => void;
  onClose: () => void;
  onDragStart: () => void;
  onDragEnter: () => void;
  onDragEnd: () => void;
  onDrop: () => void;
}) {
  const c = project.counts ?? ZERO_COUNTS;
  const tooltip = project.subtitle ? `${project.name} · ${project.subtitle}` : project.name;
  return (
    <div
      className={`ptab ${active ? "is-active" : ""} ${dragging ? "is-dragging" : ""} ${
        dragOver ? "is-drag-over" : ""
      }`}
      role="tab"
      aria-selected={active}
      tabIndex={0}
      title={tooltip}
      draggable
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      onDragStart={(e) => {
        // jsdom has no dataTransfer; guard so unit tests can fire dragStart.
        if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
        onDragStart();
      }}
      onDragEnter={onDragEnter}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        onDrop();
      }}
      onDragEnd={onDragEnd}
    >
      <div className="ptab-body">
        <div className="ptab-name">{project.name}</div>
        <div className="ptab-meta">
          <span className="ptab-counts mono">
            {c.open > 0 && (
              <span className="ptab-pip" title={`${c.open} awaiting review`}>
                <span className="pip-dot pip-blue" />
                {c.open}
              </span>
            )}
            {c.verified > 0 && (
              <span className="ptab-pip" title={`${c.verified} verified`}>
                <span className="pip-dot pip-green" />
                {c.verified}
              </span>
            )}
            {c.rejected > 0 && (
              <span className="ptab-pip" title={`${c.rejected} rejected`}>
                <span className="pip-dot pip-red" />
                {c.rejected}
              </span>
            )}
            {c.open === 0 && c.verified === 0 && c.rejected === 0 && (
              <span className="ptab-pip dim">
                <span className="pip-dot pip-rest" />0
              </span>
            )}
          </span>
        </div>
      </div>
      {active && canClose && (
        <button
          className="ptab-close"
          aria-label={`close ${project.name}`}
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          title="close project"
        >
          <svg viewBox="0 0 12 12" width="10" height="10">
            <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
        </button>
      )}
    </div>
  );
}

export function ProjectTabStrip({
  projects,
  activeId,
  onSelect,
  onClose,
  onAdd,
  onReorder,
}: StripProps) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  return (
    <div className="ptab-strip" role="tablist" aria-label="projects">
      <div className="ptab-folder" aria-hidden="true">
        <svg viewBox="0 0 18 14" width="14" height="12">
          <path
            d="M1 3.5c0-.8.7-1.5 1.5-1.5h3.7c.5 0 1 .2 1.3.6L8.7 4H15.5c.8 0 1.5.7 1.5 1.5v6c0 .8-.7 1.5-1.5 1.5h-13C1.7 13 1 12.3 1 11.5v-8z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
          />
        </svg>
        <span className="mono">projects</span>
      </div>
      <div className="ptab-list">
        {projects.map((p) => (
          <ProjectTab
            key={p.id}
            project={p}
            active={p.id === activeId}
            canClose={projects.length > 1}
            dragging={dragId === p.id}
            dragOver={overId === p.id && dragId !== null && dragId !== p.id}
            onClick={() => onSelect(p.id)}
            onClose={() => onClose(p.id)}
            onDragStart={() => {
              setDragId(p.id);
              setOverId(p.id);
            }}
            onDragEnter={() => setOverId(p.id)}
            onDragEnd={() => {
              setDragId(null);
              setOverId(null);
            }}
            onDrop={() => {
              if (dragId && dragId !== p.id) {
                const toIndex = projects.findIndex((x) => x.id === p.id);
                if (toIndex >= 0) onReorder(dragId, toIndex);
              }
              setDragId(null);
              setOverId(null);
            }}
          />
        ))}
      </div>
      <button className="ptab-add" onClick={onAdd} aria-label="new project" title="new project">
        <svg viewBox="0 0 16 16" width="12" height="12">
          <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
}
