// Agent cell. Rail + status header + agent body + verdict zone + deep toggle.
// Locked-cell rendering is delegated to VerdictZone but we add `cell--locked`
// + a LOCKED chip in the meta row.

import { useState } from "react";
import type { CSSProperties, KeyboardEvent } from "react";
import type { Cell as CellData, VerdictState } from "../lib/types";
import { statusMeta, fmtAgo } from "../lib/format";
import { StatusBadge } from "./StatusBadge";
import { MetricRow } from "./MetricRow";
import { VideoSlot } from "./VideoSlot";
import { Sparkline } from "./Sparkline";
import { VerdictZone } from "./VerdictZone";
import { DeepLayer } from "./DeepLayer";
import { InlineEdit } from "./InlineEdit";

interface Props {
  cell: CellData;
  index: number;
  total: number;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onReorder: (cid: string, dir: "up" | "down") => void;
  onVerdict: (cid: string, state: VerdictState | null, note: string) => void;
  onUnlock: (cid: string) => void;
  onDelete: (cid: string) => void;
  onChange: (cid: string, patch: { title?: string; conclusion?: string }) => void;
}

export function Cell({
  cell,
  index,
  total,
  collapsed = false,
  onToggleCollapse,
  onReorder,
  onVerdict,
  onUnlock,
  onDelete,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const status = cell.status || "open";
  const s = statusMeta(status);
  const locked = !!cell.locked;

  const toggleCollapse = onToggleCollapse ?? (() => {});
  const handleHeadKey = (e: KeyboardEvent) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    toggleCollapse();
  };

  return (
    <article
      className={`cell cell--${status} ${locked ? "cell--locked" : ""} ${collapsed ? "cell--collapsed" : ""}`}
      style={{ ["--rail" as string]: s.rail, ["--rail-bg" as string]: s.bg } as CSSProperties}
      data-screen-label={`cell-${index + 1}`}
    >
      <div className="rail" aria-hidden="true" />
      <header className="cell-head">
        <div
          className="cell-head-left cell-head-toggle"
          role="button"
          tabIndex={0}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "expand cell" : "collapse cell"}
          onClick={toggleCollapse}
          onKeyDown={handleHeadKey}
        >
          <div className="cell-meta">
            <StatusBadge status={status} />
            {locked && <span className="locked-chip">LOCKED</span>}
            <span className="mono dim sep">·</span>
            <span className="mono dim">{cell.agent_id || "agent"}</span>
            <span className="mono dim sep">·</span>
            <span className="mono dim">updated {fmtAgo(cell.updated_at)}</span>
          </div>
          <h2 className="cell-title">
            <span className="cell-collapse-chevron" aria-hidden="true">
              {collapsed ? "▸" : "▾"}
            </span>
            <InlineEdit
              value={cell.title || ""}
              multiline={false}
              disabled={locked}
              ariaLabel="edit title"
              renderView={() => <>{cell.title || "untitled"}</>}
              onSave={(next) => onChange(cell.id, { title: next })}
            />
          </h2>
        </div>
        <div className="cell-head-right">
          <div className="reorder">
            <button
              className="icon-btn"
              type="button"
              aria-label="move up"
              disabled={index === 0}
              onClick={() => onReorder(cell.id, "up")}
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
              type="button"
              aria-label="move down"
              disabled={index === total - 1}
              onClick={() => onReorder(cell.id, "down")}
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
          <button
            className="icon-btn"
            type="button"
            aria-label="delete cell"
            onClick={() => onDelete(cell.id)}
            title="delete"
          >
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

      {!collapsed && (
        <>
          <div className="agent-block">
            <div className="agent-rail" aria-hidden="true">
              <span className="agent-rail-label mono">agent</span>
            </div>
            <div className="agent-content">
              <InlineEdit
                value={cell.conclusion || ""}
                multiline
                disabled={locked}
                ariaLabel="edit conclusion"
                renderView={() =>
                  cell.conclusion ? (
                    <p className="conclusion">{cell.conclusion}</p>
                  ) : (
                    <p className="conclusion conclusion--placeholder">add conclusion…</p>
                  )
                }
                onSave={(next) => onChange(cell.id, { conclusion: next })}
              />
              {(cell.metrics || cell.visual || cell.video) && (
                <div className="outputs">
                  {cell.metrics && cell.metrics.length > 0 && <MetricRow items={cell.metrics} />}
                  {cell.visual && (
                    <div className="chart-wrap">
                      <Sparkline visual={cell.visual} />
                    </div>
                  )}
                  {cell.video && <VideoSlot video={cell.video} />}
                </div>
              )}
            </div>
          </div>

          <VerdictZone
            cell={cell}
            onVerdict={(state, note) => onVerdict(cell.id, state, note)}
            onUnlock={() => onUnlock(cell.id)}
          />

          <button
            className={`deep-toggle ${open ? "is-open" : ""}`}
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
          >
            <span className="deep-toggle-line" aria-hidden="true" />
            <span className="deep-toggle-label mono">
              <svg
                viewBox="0 0 12 12"
                width="10"
                height="10"
                aria-hidden="true"
                style={{
                  transform: open ? "rotate(90deg)" : "none",
                  transition: "transform 160ms",
                }}
              >
                <path
                  d="M4 2l4 4-4 4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              {open ? "hide details" : "show hyperparameters, files, runs, logs"}
            </span>
            <span className="deep-toggle-line" aria-hidden="true" />
          </button>

          {open && cell.deep && <DeepLayer deep={cell.deep} />}
        </>
      )}
    </article>
  );
}
