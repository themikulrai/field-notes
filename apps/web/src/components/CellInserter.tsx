import { useState } from "react";

interface Props {
  onAddMarkdown: () => void;
  onAddEmpty: () => void;
}

export function CellInserter({ onAddMarkdown, onAddEmpty }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className={`inserter ${open ? "is-open" : ""}`}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        className="inserter-handle"
        onClick={() => setOpen((v) => !v)}
        aria-label="insert between"
      >
        <span className="inserter-line" />
        <span className="inserter-plus mono">
          <svg viewBox="0 0 12 12" width="10" height="10">
            <path
              d="M6 1.5v9M1.5 6h9"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
          insert
        </span>
        <span className="inserter-line" />
      </button>
      {open && (
        <div className="inserter-menu mono">
          <button
            onClick={() => {
              onAddMarkdown();
              setOpen(false);
            }}
          >
            <svg viewBox="0 0 16 16" width="12" height="12">
              <path
                d="M2 4h12v8H2z M2 8h12 M5 6v4 M5 10l2-2 2 2"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.3"
              />
            </svg>
            markdown note
          </button>
          <button
            onClick={() => {
              onAddEmpty();
              setOpen(false);
            }}
          >
            <svg viewBox="0 0 16 16" width="12" height="12">
              <path d="M2 2h12v12H2z" fill="none" stroke="currentColor" strokeWidth="1.3" />
              <path
                d="M8 5v6M5 8h6"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinecap="round"
              />
            </svg>
            empty cell
          </button>
        </div>
      )}
    </div>
  );
}
