import type { CellStatus } from "../lib/types";
import { STATUSES, STATUS_ORDER } from "../lib/format";
import type { CSSProperties } from "react";

interface Props {
  filter: "all" | CellStatus;
  counts: Record<"all" | CellStatus, number>;
  onSetFilter: (f: "all" | CellStatus) => void;
  onAddMarkdown: () => void;
  onAddEmpty: () => void;
  onAddSection: () => void;
}

function FilterPill({
  id,
  active,
  count,
  onClick,
}: {
  id: "all" | CellStatus;
  active: boolean;
  count: number;
  onClick: () => void;
}) {
  const meta = id === "all" ? { label: "all", color: "var(--ink)" } : STATUSES[id];
  return (
    <button
      className={`pill ${active ? "is-active" : ""}`}
      style={{ ["--c" as string]: meta.color } as CSSProperties}
      onClick={onClick}
      type="button"
    >
      {id !== "all" && <span className="pill-dot" />}
      <span className="pill-label">{meta.label}</span>
      <span className="pill-count">{count}</span>
    </button>
  );
}

export function FilterBar({ filter, counts, onSetFilter, onAddMarkdown, onAddEmpty, onAddSection }: Props) {
  return (
    <div className="filter-bar">
      <div className="filter-pills">
        <FilterPill
          id="all"
          active={filter === "all"}
          count={counts.all}
          onClick={() => onSetFilter("all")}
        />
        <span className="pill-sep" />
        {STATUS_ORDER.map((k) => (
          <FilterPill
            key={k}
            id={k}
            active={filter === k}
            count={counts[k]}
            onClick={() => onSetFilter(k)}
          />
        ))}
      </div>
      <div className="filter-actions">
        <button
          className="ghost-btn mono"
          onClick={onAddMarkdown}
          type="button"
          title="add markdown note"
        >
          <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
            <path
              d="M2 4h12v8H2z M2 8h12 M5 6v4 M5 10l2-2 2 2"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.3"
            />
          </svg>
          add note
        </button>
        <button className="ghost-btn mono" onClick={onAddEmpty} type="button">
          <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
            <path
              d="M8 3v10M3 8h10"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
          add cell
        </button>
        <button
          className="ghost-btn mono"
          onClick={onAddSection}
          type="button"
          title="add a collapsible section heading"
        >
          <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
            <path
              d="M2 4h12 M2 8h9 M2 12h6"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          add section
        </button>
      </div>
    </div>
  );
}
