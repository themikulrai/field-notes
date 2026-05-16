import { useEffect, useRef, useState } from "react";
import type { Cell } from "../lib/types";
import { renderMarkdown } from "../lib/markdown";

interface Props {
  cell: Cell;
  index: number;
  total: number;
  onReorder: (cid: string, dir: "up" | "down") => void;
  onDelete: (cid: string) => void;
  onChange: (cid: string, body: string) => void;
}

export function MarkdownCell({ cell, index, total, onReorder, onDelete, onChange }: Props) {
  const [editing, setEditing] = useState(!cell.body);
  const [draft, setDraft] = useState(cell.body || "");
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setDraft(cell.body || "");
  }, [cell.id, cell.body]);

  useEffect(() => {
    if (editing && taRef.current) {
      taRef.current.focus();
      const t = taRef.current;
      t.style.height = "auto";
      t.style.height = Math.max(120, t.scrollHeight) + "px";
    }
  }, [editing]);

  const commit = () => {
    onChange(cell.id, draft);
    if (draft.trim()) setEditing(false);
  };

  return (
    <article className="md-cell" data-screen-label={`note-${index + 1}`}>
      <div className="md-gutter">
        <span className="md-tag mono">NOTE</span>
      </div>
      <div className="md-body">
        {editing ? (
          <>
            <textarea
              ref={taRef}
              className="md-editor mono"
              placeholder={"# heading\n\nWrite a section header, hypothesis, or quick note. Markdown: **bold**, *italic*, `code`, > quote, - list, [link](url)."}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                const t = e.target;
                t.style.height = "auto";
                t.style.height = Math.max(120, t.scrollHeight) + "px";
              }}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  commit();
                }
                if (e.key === "Escape") {
                  e.preventDefault();
                  setDraft(cell.body || "");
                  setEditing(false);
                }
              }}
              onBlur={commit}
            />
            <div className="md-editor-hint mono">
              <span>
                <kbd>⌘</kbd>+<kbd>↵</kbd> save · <kbd>esc</kbd> cancel · markdown
              </span>
            </div>
          </>
        ) : (
          <div
            className="md-rendered"
            onClick={() => setEditing(true)}
            title="click to edit"
            dangerouslySetInnerHTML={{
              __html: renderMarkdown(cell.body || "*(empty note — click to edit)*"),
            }}
          />
        )}
      </div>
      <div className="md-actions">
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
        <button
          className="icon-btn"
          onClick={() => setEditing((v) => !v)}
          aria-label={editing ? "preview" : "edit"}
          title={editing ? "preview" : "edit"}
        >
          {editing ? (
            <svg viewBox="0 0 16 16" width="12" height="12">
              <path
                d="M1 8s2.5-4.5 7-4.5S15 8 15 8s-2.5 4.5-7 4.5S1 8 1 8z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
              />
              <circle cx="8" cy="8" r="1.8" fill="currentColor" />
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" width="12" height="12">
              <path
                d="M2 12.5V14h1.5L12 5.5 10.5 4 2 12.5zM13.4 3.6l-1-1a.6.6 0 00-.9 0L10.7 3.4l1.9 1.9.8-.8a.6.6 0 000-.9z"
                fill="currentColor"
              />
            </svg>
          )}
        </button>
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
    </article>
  );
}
