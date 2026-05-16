// Collapsible markdown-heading section. Title is rendered as <h2>/<h3>.
// Also exposes edit/delete/reorder controls so a heading cell can be managed
// through the UI just like a regular MarkdownCell.

import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";
import type { Cell } from "../lib/types";

interface Props {
  level: 2 | 3;
  heading: string;
  collapsed: boolean;
  onToggle: () => void;
  children: ReactNode;
  // Heading-cell management. All optional so existing call sites
  // that didn't wire these up keep working (caret-only mode).
  cell?: Cell;
  index?: number;
  total?: number;
  onReorder?: (cid: string, dir: "up" | "down") => void;
  onDelete?: (cid: string) => void;
  onChange?: (cid: string, body: string) => void;
}

// A freshly-created section cell has body like "## " — non-empty but the
// heading text is empty. Treat that as "still needs typing" and start in
// edit mode so the user can immediately type the title.
function isHeadingBodyEmpty(body: string | null | undefined): boolean {
  if (!body) return true;
  const t = body.trim();
  return t === "##" || t === "###";
}

export function SectionGroup({
  level,
  heading,
  collapsed,
  onToggle,
  children,
  cell,
  index,
  total,
  onReorder,
  onDelete,
  onChange,
}: Props) {
  const Head = level === 2 ? "h2" : "h3";

  const [editing, setEditing] = useState<boolean>(
    !!cell && !!onChange && isHeadingBodyEmpty(cell.body),
  );
  const [draft, setDraft] = useState<string>(cell?.body ?? "");
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setDraft(cell?.body ?? "");
  }, [cell?.id, cell?.body]);

  useEffect(() => {
    if (editing && taRef.current) {
      taRef.current.focus();
      const t = taRef.current;
      t.style.height = "auto";
      t.style.height = Math.max(80, t.scrollHeight) + "px";
    }
  }, [editing]);

  const stop = (e: MouseEvent) => e.stopPropagation();

  const commit = () => {
    if (!cell || !onChange) return;
    onChange(cell.id, draft);
    // Leave edit mode only once the user has typed something substantive.
    // (Same UX as MarkdownCell.commit's `if (draft.trim()) setEditing(false)`.)
    if (!isHeadingBodyEmpty(draft)) setEditing(false);
  };

  const canManage = !!cell && !!onChange && !!onDelete && !!onReorder && index !== undefined && total !== undefined;

  return (
    <section className={`section-group section-level-${level}`}>
      <header className="section-heading" aria-expanded={!collapsed}>
        <span
          className={`section-caret mono ${!collapsed ? "is-open" : ""}`}
          role="button"
          aria-label={collapsed ? "expand section" : "collapse section"}
          onClick={onToggle}
        >
          ▶
        </span>
        {editing && cell ? (
          <div className="section-editor-wrap" onClick={stop}>
            <textarea
              ref={taRef}
              className="md-editor mono section-editor"
              placeholder={"## section title\n\nOptional body under the heading."}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                const t = e.target;
                t.style.height = "auto";
                t.style.height = Math.max(80, t.scrollHeight) + "px";
              }}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  commit();
                }
                if (e.key === "Escape") {
                  e.preventDefault();
                  setDraft(cell.body ?? "");
                  setEditing(false);
                }
              }}
              onBlur={commit}
            />
            <div className="md-editor-hint mono">
              <span>
                <kbd>⌘</kbd>+<kbd>↵</kbd> save · <kbd>esc</kbd> cancel · keep <code>## </code> prefix to stay a section
              </span>
            </div>
          </div>
        ) : (
          <Head
            className="mono section-heading-text"
            onClick={onToggle}
          >
            {heading || "(untitled section)"}
          </Head>
        )}
        {canManage && !editing && (
          <div className="section-actions" onClick={stop}>
            <div className="reorder">
              <button
                className="icon-btn"
                disabled={index === 0}
                onClick={(e) => {
                  e.stopPropagation();
                  onReorder!(cell!.id, "up");
                }}
                aria-label="move section up"
                title="move up"
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
                disabled={index === (total as number) - 1}
                onClick={(e) => {
                  e.stopPropagation();
                  onReorder!(cell!.id, "down");
                }}
                aria-label="move section down"
                title="move down"
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
              onClick={(e) => {
                e.stopPropagation();
                setEditing(true);
              }}
              aria-label="edit section"
              title="edit"
            >
              <svg viewBox="0 0 16 16" width="12" height="12">
                <path
                  d="M2 12.5V14h1.5L12 5.5 10.5 4 2 12.5zM13.4 3.6l-1-1a.6.6 0 00-.9 0L10.7 3.4l1.9 1.9.8-.8a.6.6 0 000-.9z"
                  fill="currentColor"
                />
              </svg>
            </button>
            <button
              className="icon-btn"
              onClick={(e) => {
                e.stopPropagation();
                onDelete!(cell!.id);
              }}
              aria-label="delete section"
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
        )}
      </header>
      {!collapsed && <div className="section-children">{children}</div>}
    </section>
  );
}
