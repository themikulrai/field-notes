import type { CellStatus } from "../lib/types";
import { statusMeta, STATUS_ORDER } from "../lib/format";
import type { CSSProperties } from "react";

interface Props {
  title: string;
  filter: "all" | CellStatus;
  counts: Record<"all" | CellStatus, number>;
  onSetFilter: (f: "all" | CellStatus) => void;
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
  const meta = id === "all" ? { label: "all", color: "var(--ink)" } : statusMeta(id);
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

// Slim header row: the active project's name on the left, the status filter
// pills on the right. The "open" pill count is the only place open-cell counts
// are surfaced now (the old "awaiting you" stat was a duplicate).
export function FilterBar({ title, filter, counts, onSetFilter }: Props) {
  return (
    <div className="filter-bar">
      <h1 className="filter-title">{title}</h1>
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
    </div>
  );
}
