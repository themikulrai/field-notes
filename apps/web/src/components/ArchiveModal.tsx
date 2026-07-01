import { useEffect } from "react";
import type { Project, ProjectCounts } from "../lib/types";

const ZERO_COUNTS: ProjectCounts = { in_progress: 0, open: 0, verified: 0, rejected: 0 };

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
                  <div className="archive-row-pips ptab-counts mono">
                    {(() => {
                      const c = p.counts ?? ZERO_COUNTS;
                      if (c.open === 0 && c.verified === 0 && c.rejected === 0) {
                        return (
                          <span className="ptab-pip dim">
                            <span className="pip-dot pip-rest" />0
                          </span>
                        );
                      }
                      return (
                        <>
                          {c.open > 0 && (
                            <span className="ptab-pip" title={`${c.open} awaiting review`}>
                              <span className="pip-dot pip-blue" />{c.open}
                            </span>
                          )}
                          {c.verified > 0 && (
                            <span className="ptab-pip" title={`${c.verified} verified`}>
                              <span className="pip-dot pip-green" />{c.verified}
                            </span>
                          )}
                          {c.rejected > 0 && (
                            <span className="ptab-pip" title={`${c.rejected} rejected`}>
                              <span className="pip-dot pip-red" />{c.rejected}
                            </span>
                          )}
                        </>
                      );
                    })()}
                  </div>
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
