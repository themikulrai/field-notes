# Inline cell editing + agent deep-block nudge

Date: 2026-06-21

## Goal

Two independent changes to field-notes:

1. **Inline editing of agent cells in the web UI** — let the human edit an agent
   cell's text (title, conclusion) directly in the browser by double-clicking it.
   (Markdown cells are **already** editable — see Background — so they need no
   change.)
2. **Push agents to fill the deep block** — reword the `create_cell` /
   `update_cell` MCP tool descriptions so agents populate
   `deep` (hparams / files / runs / logs) on every agent cell.

These ship together but touch disjoint code (web frontend vs MCP server) and can
be reviewed/tested independently.

## Background (current state)

- The data model already has everything needed. `Cell` has `title`,
  `conclusion`, `body`, and a `deep` JSON block (`DeepBlock`:
  `hparams: dict[str,str]`, `files: list[str]`, `runs: list[dict]`, `logs: str`).
- The **edit backend already exists**: `PATCH /cells/{cid}` accepts `CellUpdate`,
  the web API client has `updateCell(cid, body)`, and the Zustand store has an
  optimistic `updateCell` action. **Nothing on the server or in the store needs
  to change for request 1** — only a UI affordance is missing.
- Web edits carry `source = "http"` (the default), so they do **not** trip the
  MCP-only "any agent edit re-opens the cell" invariant. A human edit keeps the
  cell's status and verdict untouched.
- Cells render in `apps/web/src/components/Cell.tsx` (agent) and
  `apps/web/src/components/MarkdownCell.tsx` (markdown). The agent title lives
  inside a collapse-toggle button; the conclusion is a `<p class="conclusion">`.
- **`MarkdownCell` already implements inline editing**: single-click the
  rendered markdown → textarea, Cmd/Ctrl-Enter or blur saves, Esc cancels, plus
  a pencil/preview toggle, all wired through `onChange(cid, body)` →
  `store.updateCell`. So **markdown bodies are already editable** and are out of
  scope. The gap is the **agent cell** (`Cell.tsx`), which is read-only except
  for verdict/reorder/delete.
- The MCP tool descriptions (`packages/mcp_server/field_notes_mcp/tools.py`)
  never mention the `deep` block, so agents almost never fill it.

## Request 1 — Inline cell editing (web UI)

### Scope

Editable fields (text only — **not** metrics/visual/video). **Only the agent
cell needs work**; markdown bodies are already editable:

| Field        | Cell kind | Editor              | Status |
| ------------ | --------- | ------------------- | ------ |
| `title`      | agent     | single-line input   | **new** |
| `conclusion` | agent     | multi-line textarea | **new** |
| `body`       | markdown  | multi-line textarea | already exists, no change |

Empty/section cells have no editable text and are skipped. Locked cells are not
editable.

### Interaction

- **Trigger:** double-click the rendered text. Single-click keeps its current
  meaning (collapse-toggle on the title, follow-links in markdown). Double-click
  swaps the rendered text for an editor seeded with the current value.
- **Save:**
  - title (single-line): **Enter** or **blur** saves.
  - conclusion / body (multi-line): **Cmd/Ctrl-Enter** or **blur** saves; plain
    Enter inserts a newline.
- **Cancel:** **Esc** discards the draft and restores the rendered text.
- **No-op guard:** if the draft equals the original value, no API call is made
  (just exit edit mode).
- **No hover cue** — text looks normal until double-clicked. (Explicit choice.)

### Component design

A single small reusable editor component, `InlineEdit`, holds all the
edit-mode mechanics so `Cell` and `MarkdownCell` stay thin:

```
InlineEdit({
  value: string,
  multiline: boolean,
  disabled: boolean,           // locked cells pass true
  renderView: () => ReactNode, // how the text looks when NOT editing
  onSave: (next: string) => void,
})
```

- Owns local `editing` + `draft` state. The draft is **independent of `value`**
  while editing — so an incoming SSE patch to the same cell does not clobber an
  open editor (see "Concurrency" below).
- When not editing: renders `renderView()` wrapped in an element with
  `onDoubleClick` (no-op if `disabled`).
- When editing: renders an `<input>` (single-line) or `<textarea>` (multiline)
  with the key handlers above, autofocused, text selected.
- `onSave` is only called when `draft !== value`.

Wiring:

- `Cell.tsx`: wrap the title text and the conclusion `<p>` in `InlineEdit`.
  - Title's `onDoubleClick` must `stopPropagation` so it does not also fire the
    header collapse-toggle.
  - `onSave` → `store.updateCell(cell.id, { title })` /
    `{ conclusion }`. `disabled = cell.locked`.
  - When the agent cell has **no** conclusion yet, still allow adding one:
    render a faint placeholder ("add conclusion…") as the view so there's a
    double-click target. (Title already always renders, defaulting to
    "untitled".)
- `MarkdownCell.tsx`: **no change** — it already has its own inline editor.

### Concurrency

While an editor is open, `InlineEdit` ignores changes to the incoming `value`
prop (the draft is local state, seeded once on entering edit mode). So if an
agent updates the cell via MCP mid-edit, the human's draft is preserved; on
save the human's text wins (last-write). On cancel, the editor re-reads the
(now-updated) `value`. This is acceptable for a single-human research notebook;
true conflict resolution is out of scope.

### Status / verdict behavior

Unchanged and intentional: a web edit (`source=http`) does **not** reset the
cell's status or clear its verdict. Editing a verified cell's text leaves it
verified. (If undesirable later, a separate change could re-open on human edit;
not in this spec.)

### Tests (web, vitest)

- `InlineEdit`: double-click enters edit mode; Enter/blur saves single-line;
  Cmd-Enter saves multiline; Esc cancels; no-op when unchanged → `onSave` not
  called; `disabled` blocks edit mode.
- `Cell`: double-clicking title does not toggle collapse (stopPropagation);
  saving title/conclusion calls `store.updateCell` with the right patch; locked
  cell is not editable; an agent cell with no conclusion shows an "add
  conclusion…" target that becomes editable on double-click.

## Request 2 — Stronger MCP tool descriptions

Reword two tool descriptions in `tools.py` (`register_tools`):

- **`create_cell`**: append guidance that for **agent** cells the agent should
  populate `deep` with:
  - `hparams` — the key config that defines the run,
  - `files` — paths created/modified,
  - `runs` — wandb/job links (`wandb://…` or URLs),
  - `logs` — the salient stdout/metrics lines,
  and state that an agent cell **without** a deep block is considered
  incomplete because the human audits work through it. Note `deep` does not
  apply to markdown/empty cells.
- **`update_cell`**: add a one-line reminder to keep `deep` current
  (e.g. add the wandb run once launched, append final logs when done).

This is a **soft** nudge (wording only). No schema or validation change. Markdown
and empty cells still reject `deep` server-side, so the guidance is scoped to
agent cells.

### Tests (mcp, pytest)

- Assert the rendered tool descriptions for `create_cell` and `update_cell`
  mention the deep block (e.g. contain "hparams" / "deep"). This pins the
  intent so a future edit doesn't silently drop it. (Existing tool tests live in
  `packages/mcp_server/tests/`.)

## Out of scope

- UI "missing deep block" badge (would make gaps visible; deferred).
- Hard enforcement / validation that agent cells carry a deep block.
- Editing metrics / visual / video from the web UI.
- Re-opening a cell on human edit.

## Risks

1. **Soft incentive.** Description wording does not guarantee agents fill
   `deep`. Chosen as the cheapest path; revisit with a UI badge or validation if
   compliance stays low.
2. **Mid-edit clobber** mitigated (local draft) but last-write-wins on save.
3. **Double-click discoverability** — no hover cue by choice; the gesture is
   undiscoverable until tried. Mitigation deferred.
4. **Verdict drift** — editing a verified cell keeps the verdict; the text now
   differs from what was verified. Acceptable for a single-human notebook.
5. **Trigger inconsistency** — markdown cells edit on **single**-click (existing
   behavior, unchanged), while new agent-cell editing is **double**-click (to
   avoid the title's collapse-toggle conflict). Two gestures across cell kinds.
   Aligning them would mean changing established markdown behavior + tests;
   deferred. Flagging it.
