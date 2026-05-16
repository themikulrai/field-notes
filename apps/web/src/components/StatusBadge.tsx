import type { CellStatus } from "../lib/types";
import { STATUSES } from "../lib/format";
import type { CSSProperties } from "react";

interface Props {
  status: CellStatus;
  size?: "sm" | "md";
}

export function StatusBadge({ status, size = "md" }: Props) {
  const s = STATUSES[status];
  return (
    <span
      className={`status-badge size-${size}`}
      style={{ ["--c" as string]: s.color, ["--bg" as string]: s.bg } as CSSProperties}
      aria-label={`status: ${s.label}`}
    >
      <span className={`status-dot ${s.dotAnim ? "pulse" : ""}`} />
      {s.label}
    </span>
  );
}
