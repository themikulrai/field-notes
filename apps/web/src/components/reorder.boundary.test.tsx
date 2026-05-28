// Bug 5 regression: the up/down reorder buttons in cell/markdown/empty
// rows and section headers must gate on TRUE flat-array boundaries, not
// on the local sibling position inside a SectionNode subtree. Otherwise
// the first child of a section has "up" disabled even though the backend
// (and store.reorderCell) supports moving across section boundaries on
// the flat array.
//
// We render <App /> with a known cell list, then locate each cell's row
// (by `data-section-id` for section heads, or by walking from a content
// match for markdown notes) and assert the `disabled` attribute on its
// "move up" / "move down" buttons.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import type { Cell } from "../lib/types";

// Stub the live-events stream so useLiveEvents in <App /> doesn't try to
// open an EventSource against jsdom.
vi.mock("../lib/events", () => ({
  openEventStream: () => ({ close: () => {} }),
}));

function md(id: string, body: string, position: number): Cell {
  return {
    id,
    project_id: "p1",
    kind: "markdown",
    position,
    created_at: "",
    updated_at: "",
    locked: false,
    body,
  };
}

async function renderWithCells(cells: Cell[]) {
  localStorage.setItem("field-notes-key", "k");
  vi.resetModules();

  const { useStore } = await import("../lib/store");
  useStore.setState({
    projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
    activeProjectId: "p1",
    cellsByProject: { p1: cells },
    filter: "all",
    collapsedSections: {},
  });
  useStore.setState({
    loadProjects: vi.fn().mockResolvedValue(undefined),
    loadCells: vi.fn().mockResolvedValue(undefined),
  } as Partial<ReturnType<typeof useStore.getState>>);

  const AppMod = await import("../App");
  const App = AppMod.default;
  return render(<App />);
}

// Find the .section-group element for the given heading cell id.
function sectionEl(root: Element, cellId: string): Element | null {
  return root.querySelector(`.section-group[data-section-id="${cellId}"]`);
}

// Find the markdown-note row whose rendered body contains `text`. We have
// to skip nested .md-cell matches inside section bodies (none today, but
// defensive) and pick the .md-cell ancestor of the matching text.
function markdownRowByText(root: Element, text: string): Element | null {
  const rows = root.querySelectorAll<Element>(".md-cell");
  for (const row of rows) {
    if (row.textContent && row.textContent.includes(text)) return row;
  }
  return null;
}

// On a SectionGroup header the buttons use aria-label "move section up/down".
// On a MarkdownCell/Cell/EmptyCell row the buttons use "move up/down".
function getMoveButtons(rowEl: Element, variant: "section" | "row"): {
  up: HTMLButtonElement | null;
  down: HTMLButtonElement | null;
} {
  const upLabel = variant === "section" ? "move section up" : "move up";
  const downLabel = variant === "section" ? "move section down" : "move down";
  return {
    up: rowEl.querySelector<HTMLButtonElement>(
      `button[aria-label="${upLabel}"]`,
    ),
    down: rowEl.querySelector<HTMLButtonElement>(
      `button[aria-label="${downLabel}"]`,
    ),
  };
}

describe("reorder boundary disabled-state (bug 5)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("[H1-A, MD1, MD2, H1-B, MD3]: section children are NOT trapped at local boundaries", async () => {
    const cells = [
      md("hA", "# Active", 0),
      md("m1", "first child of A", 1),
      md("m2", "last child of A", 2),
      md("hB", "# Pending", 3),
      md("m3", "only child of B", 4),
    ];
    const { container } = await renderWithCells(cells);

    // hA is the first cell overall -> "up" IS disabled, "down" enabled.
    const hARow = sectionEl(container, "hA")!;
    expect(hARow).toBeTruthy();
    const hABtns = getMoveButtons(hARow, "section");
    expect(hABtns.up).toBeTruthy();
    expect(hABtns.down).toBeTruthy();
    expect(hABtns.up!.disabled).toBe(true);
    expect(hABtns.down!.disabled).toBe(false);

    // MD1 is local-index 0 inside section A, but flat-index 1 overall.
    // "up" must NOT be disabled — the user wants to move it above hA.
    const m1Row = markdownRowByText(container, "first child of A")!;
    expect(m1Row).toBeTruthy();
    const m1Btns = getMoveButtons(m1Row, "row");
    expect(m1Btns.up).toBeTruthy();
    expect(m1Btns.down).toBeTruthy();
    expect(m1Btns.up!.disabled).toBe(false);
    expect(m1Btns.down!.disabled).toBe(false);

    // MD2 is the last child of section A (local total-1) but flat-index 2
    // of 5 — "down" must NOT be disabled.
    const m2Row = markdownRowByText(container, "last child of A")!;
    expect(m2Row).toBeTruthy();
    const m2Btns = getMoveButtons(m2Row, "row");
    expect(m2Btns.up!.disabled).toBe(false);
    expect(m2Btns.down!.disabled).toBe(false);

    // MD3 is the first AND last child of section B, and the last cell
    // overall — "up" NOT disabled, "down" IS disabled.
    const m3Row = markdownRowByText(container, "only child of B")!;
    expect(m3Row).toBeTruthy();
    const m3Btns = getMoveButtons(m3Row, "row");
    expect(m3Btns.up!.disabled).toBe(false);
    expect(m3Btns.down!.disabled).toBe(true);
  });

  it("[MD1, MD2, MD3] plain list: boundaries gate exactly the first and last cell", async () => {
    const cells = [
      md("m1", "alpha note", 0),
      md("m2", "bravo note", 1),
      md("m3", "charlie note", 2),
    ];
    const { container } = await renderWithCells(cells);

    const m1 = markdownRowByText(container, "alpha note")!;
    const m2 = markdownRowByText(container, "bravo note")!;
    const m3 = markdownRowByText(container, "charlie note")!;
    expect(m1).toBeTruthy();
    expect(m2).toBeTruthy();
    expect(m3).toBeTruthy();

    const b1 = getMoveButtons(m1, "row");
    const b2 = getMoveButtons(m2, "row");
    const b3 = getMoveButtons(m3, "row");

    expect(b1.up!.disabled).toBe(true);
    expect(b1.down!.disabled).toBe(false);

    expect(b2.up!.disabled).toBe(false);
    expect(b2.down!.disabled).toBe(false);

    expect(b3.up!.disabled).toBe(false);
    expect(b3.down!.disabled).toBe(true);
  });
});
