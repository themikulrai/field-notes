// Reusable inline-edit affordance: double-click the rendered view to swap it
// for an input/textarea seeded once from `value`. The draft is local state and
// is NOT re-synced from `value` while editing, so an SSE patch mid-edit does
// not clobber the human's in-progress text (last-write-wins on save).

import { useEffect, useRef, useState } from "react";

interface Props {
  value: string;
  multiline: boolean;
  disabled: boolean;
  placeholder?: string;
  renderView: () => React.ReactNode;
  onSave: (next: string) => void;
  ariaLabel?: string;
}

export function InlineEdit({
  value,
  multiline,
  disabled,
  placeholder,
  renderView,
  onSave,
  ariaLabel,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // Seed the draft once on entering edit mode, then focus + select.
  useEffect(() => {
    if (!editing) return;
    const el = multiline ? taRef.current : inputRef.current;
    if (el) {
      el.focus();
      el.select();
    }
  }, [editing, multiline]);

  const enter = () => {
    if (disabled) return;
    setDraft(value);
    setEditing(true);
  };

  const commit = () => {
    if (draft !== value) onSave(draft);
    setEditing(false);
  };

  const cancel = () => {
    setEditing(false);
  };

  if (!editing) {
    return (
      <span
        className="inline-edit-view"
        onDoubleClick={(e) => {
          e.stopPropagation();
          enter();
        }}
      >
        {renderView()}
      </span>
    );
  }

  if (multiline) {
    return (
      <textarea
        ref={taRef}
        className="md-editor mono inline-edit-input"
        aria-label={ariaLabel}
        placeholder={placeholder}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          // Stop every keystroke from reaching ancestor key handlers (e.g. the
          // cell header's Space/Enter collapse toggle) while editing.
          e.stopPropagation();
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            commit();
          } else if (e.key === "Escape") {
            e.preventDefault();
            cancel();
          }
        }}
        // Clicking to place the cursor must not bubble to a parent collapse
        // toggle (which would collapse the cell mid-edit).
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
        onBlur={commit}
      />
    );
  }

  return (
    <input
      ref={inputRef}
      type="text"
      className="inline-edit-input"
      aria-label={ariaLabel}
      placeholder={placeholder}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        // Stop every keystroke (notably Space) from bubbling to the cell
        // header's collapse toggle; otherwise typing a space collapses the cell.
        e.stopPropagation();
        if (e.key === "Enter") {
          e.preventDefault();
          commit();
        } else if (e.key === "Escape") {
          e.preventDefault();
          cancel();
        }
      }}
      // Clicking to place the cursor must not bubble to a parent collapse toggle.
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
      onBlur={commit}
    />
  );
}
