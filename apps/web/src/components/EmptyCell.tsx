import type { Cell } from "../lib/types";

interface Props {
  cell: Cell;
  index: number;
  total: number;
  onReorder: (cid: string, dir: "up" | "down") => void;
  onDelete: (cid: string) => void;
}

export function EmptyCell({ cell, index, total, onReorder, onDelete }: Props) {
  return (
    <article className="cell cell--empty" data-screen-label={`cell-${index + 1}-empty`}>
      <div className="rail" aria-hidden="true" />
      <header className="cell-head">
        <div className="cell-head-left">
          <div className="cell-meta">
            <span className="status-badge size-md status-badge--empty">
              <span className="status-dot" />
              empty
            </span>
            <span className="mono dim sep">·</span>
            <span className="mono dim">manual</span>
            <span className="mono dim sep">·</span>
            <span className="mono dim">just now</span>
          </div>
          <h2 className="cell-title dim">untitled cell</h2>
        </div>
        <div className="cell-head-right">
          <div className="reorder">
            <button
              className="icon-btn"
              disabled={index === 0}
              onClick={() => onReorder(cell.id, "up")}
              aria-label="move up"
            >
              <svg viewBox="0 0 16 16" width="12" height="12">
                <path
                  d="M8 3v10M3 8l5-5 5 5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            <button
              className="icon-btn"
              disabled={index === total - 1}
              onClick={() => onReorder(cell.id, "down")}
              aria-label="move down"
            >
              <svg viewBox="0 0 16 16" width="12" height="12">
                <path
                  d="M8 13V3M3 8l5 5 5-5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
          <button className="icon-btn" onClick={() => onDelete(cell.id)} aria-label="delete">
            <svg viewBox="0 0 16 16" width="12" height="12">
              <path
                d="M4 5h8M6 5V3.5h4V5M5.5 5l.5 8h4l.5-8"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </header>
      <div className="empty-body">
        <div className="empty-prompt mono">waiting for an agent to push a result</div>
      </div>
    </article>
  );
}
