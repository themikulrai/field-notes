import { useEffect, useState, useRef } from "react";
import type { Cell, VerdictState } from "../lib/types";
import { fmtAgo } from "../lib/format";

interface Props {
  cell: Cell;
  onVerdict: (state: VerdictState | null, note: string) => void;
  onUnlock: () => void;
}

export function VerdictZone({ cell, onVerdict, onUnlock }: Props) {
  const v = cell.verdict;
  const [draft, setDraft] = useState(v?.note || "");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => setDraft(v?.note || ""), [cell.id, v?.note]);

  const has = !!v;
  const state = v?.state ?? null;
  const hasDraft = draft.trim().length > 0;
  const stale = !!v && new Date(cell.updated_at) > new Date(v.at);

  const commit = (next: VerdictState) => {
    onVerdict(next === state ? null : next, draft);
  };

  if (cell.locked) {
    return (
      <div className="verdict verdict--locked">
        <div className="verdict-tag">
          <span className="verdict-tag-label">HUMAN</span>
          <span className="locked-chip">LOCKED</span>
          {stale && (
            <span
              className="verdict-stale-chip"
              title="cell edited after verdict — please re-review"
            >
              STALE
            </span>
          )}
          {has && <span className="verdict-tag-time mono">{fmtAgo(v!.at)}</span>}
        </div>
        <div className="verdict-body">
          {v?.note && (
            <div className="verdict-note-wrap">
              <div className="verdict-note">{v.note}</div>
            </div>
          )}
          <div className="verdict-row">
            <div className="verdict-locked-actions">
              <button type="button" className="unlock-btn" onClick={onUnlock} aria-label="unlock cell">
                unlock
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`verdict ${has ? `verdict--${state}` : "verdict--empty"}`}>
      <div className="verdict-tag">
        <span className="verdict-tag-label">HUMAN</span>
        {stale && (
          <span
            className="verdict-stale-chip"
            title="cell edited after verdict — please re-review"
          >
            STALE
          </span>
        )}
        {has && <span className="verdict-tag-time mono">{fmtAgo(v!.at)}</span>}
      </div>
      <div className="verdict-body">
        <label className="verdict-label mono" htmlFor={`note-${cell.id}`}>
          <span>comment</span>
          <span className="dim">— attached to your verdict</span>
        </label>
        <div className="verdict-note-wrap">
          <textarea
            id={`note-${cell.id}`}
            ref={ref}
            className="verdict-note"
            placeholder={
              has
                ? "edit your annotation…"
                : "write what you think — then verify or reject below"
            }
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={2}
          />
          <div className="verdict-note-rule" aria-hidden="true" />
        </div>
        <div className="verdict-row">
          <div className="verdict-actions">
            <button
              type="button"
              className={`vbtn vbtn--accept ${state === "accept" ? "is-on" : ""}`}
              onClick={() => commit("accept")}
              aria-pressed={state === "accept"}
            >
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                <path
                  d="M3 8.5l3.2 3.2L13 4.8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span>
                {state === "accept" ? "verified" : hasDraft ? "verify with comment" : "verify"}
              </span>
            </button>
            <button
              type="button"
              className={`vbtn vbtn--reject ${state === "reject" ? "is-on" : ""}`}
              onClick={() => commit("reject")}
              aria-pressed={state === "reject"}
            >
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                <path
                  d="M4 4l8 8M12 4l-8 8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
              <span>
                {state === "reject" ? "rejected" : hasDraft ? "reject with comment" : "reject"}
              </span>
            </button>
          </div>
          {has && (
            <div className="verdict-meta">
              <span className="mono dim">signed {v!.by}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
