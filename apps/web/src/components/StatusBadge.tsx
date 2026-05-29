import type { CellStatus } from "../lib/types";
import { statusMeta } from "../lib/format";
import type { CSSProperties } from "react";

interface Props {
  // Widened to string: the backend can send a status this build doesn't model
  // (e.g. the deprecated "ready"); statusMeta() resolves it safely.
  status: CellStatus | string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, size = "md" }: Props) {
  const s = statusMeta(status);
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
