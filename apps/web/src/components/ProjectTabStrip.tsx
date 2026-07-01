import { useState } from "react";
import type { Project, ProjectCounts } from "../lib/types";

interface StripProps {
  projects: Project[];
  activeId: string | null;
  onSelect: (pid: string) => void;
  onArchive: (pid: string) => void;
  onOpenArchive: () => void;
  onAdd: () => void;
  // Drop `pid` at the displayed index `toIndex` (drag-to-reorder the tab strip).
  onReorder: (pid: string, toIndex: number) => void;
}

const ZERO_COUNTS: ProjectCounts = { in_progress: 0, open: 0, verified: 0, rejected: 0 };

function ProjectTab({
  project,
  active,
  dragging,
  dragOver,
  onClick,
  onArchive,
  onDragStart,
  onDragEnter,
  onDragEnd,
  onDrop,
}: {
  project: Project;
  active: boolean;
  dragging: boolean;
  dragOver: boolean;
  onClick: () => void;
  onArchive: () => void;
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
    </div>
  );
}

export function ProjectTabStrip({
  projects,
  activeId,
  onSelect,
  onArchive,
  onOpenArchive,
  onAdd,
  onReorder,
}: StripProps) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  return (
    <div className="ptab-strip" role="tablist" aria-label="projects">
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
      <div className="ptab-list">
        {projects.map((p) => (
          <ProjectTab
            key={p.id}
            project={p}
            active={p.id === activeId}
            dragging={dragId === p.id}
            dragOver={overId === p.id && dragId !== null && dragId !== p.id}
            onClick={() => onSelect(p.id)}
            onArchive={() => onArchive(p.id)}
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
