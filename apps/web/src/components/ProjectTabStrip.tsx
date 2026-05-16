import type { Cell, CellStatus, Project } from "../lib/types";

interface StripProps {
  projects: Project[];
  activeId: string | null;
  cellsByProject: Record<string, Cell[]>;
  onSelect: (pid: string) => void;
  onClose: (pid: string) => void;
  onAdd: () => void;
}

function projectCounts(cells: Cell[]): Record<"all" | CellStatus, number> {
  const c = { all: 0, in_progress: 0, open: 0, verified: 0, rejected: 0 };
  for (const x of cells) {
    if (x.kind !== "agent") continue;
    c.all++;
    if (x.status) c[x.status]++;
  }
  return c;
}

function ProjectTab({
  project,
  active,
  cells,
  canClose,
  onClick,
  onClose,
}: {
  project: Project;
  active: boolean;
  cells: Cell[];
  canClose: boolean;
  onClick: () => void;
  onClose: () => void;
}) {
  const c = projectCounts(cells);
  return (
    <div
      className={`ptab ${active ? "is-active" : ""}`}
      role="tab"
      aria-selected={active}
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <div className="ptab-body">
        <div className="ptab-name">{project.name}</div>
        <div className="ptab-meta">
          <span className="ptab-counts mono">
            {c.in_progress > 0 && (
              <span className="ptab-pip" title={`${c.in_progress} in progress`}>
                <span className="pip-dot pip-amber pulse" />
                {c.in_progress}
              </span>
            )}
            {c.open > 0 && (
              <span className="ptab-pip" title={`${c.open} awaiting review`}>
                <span className="pip-dot pip-blue" />
                {c.open}
              </span>
            )}
            {c.in_progress === 0 && c.open === 0 && (
              <span className="ptab-pip dim">
                <span className="pip-dot pip-rest" />0
              </span>
            )}
          </span>
          {project.subtitle && <span className="ptab-sub mono dim">· {project.subtitle}</span>}
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
  cellsByProject,
  onSelect,
  onClose,
  onAdd,
}: StripProps) {
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
            cells={cellsByProject[p.id] || []}
            canClose={projects.length > 1}
            onClick={() => onSelect(p.id)}
            onClose={() => onClose(p.id)}
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
