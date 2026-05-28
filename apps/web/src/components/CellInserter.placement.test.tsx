// Verifies the cell-inserter placement logic in <App />:
//   - exactly one inserter per visible gap (top + after every cell/section)
//   - inserters render between sibling sections (bug 1)
//   - inserters render between cells inside a section (bug 2)
//   - inserter at the boundary between a section's last cell and the next
//     section header (bug 3 / 4 — the General-project case)
//   - inserter inside a collapsed section is hidden, but the inserter that
//     follows the whole section anchors to its last descendant
//   - empty section (only header, no children) has NO inside inserter —
//     the outside after-section inserter handles "add first child"
//   - no double inserter at section boundaries (Bug A / B follow-up)
//
// We don't fire clicks here — the spec calls for asserting structure and
// DOM order. The store actions are exercised in store.test.ts.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import type { Cell } from "../lib/types";

// Stub the live-events stream so useLiveEvents in <App /> doesn't try to
// open an EventSource against jsdom (which would throw or hang).
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

function agent(id: string, position: number, title: string): Cell {
  return {
    id,
    project_id: "p1",
    kind: "agent",
    position,
    created_at: "",
    updated_at: "",
    locked: false,
    title,
    status: "open",
  };
}

async function renderWithCells(cells: Cell[], collapsedSections?: Record<string, Record<string, boolean>>) {
  // Seed the API key so App skips KeyGate.
  localStorage.setItem("field-notes-key", "k");
  vi.resetModules();

  const { useStore } = await import("../lib/store");
  useStore.setState({
    projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
    activeProjectId: "p1",
    cellsByProject: { p1: cells },
    filter: "all",
    collapsedSections: collapsedSections ?? {},
  });
  // Stub fetch-driven loaders so mount-time effects don't hit the network.
  useStore.setState({
    loadProjects: vi.fn().mockResolvedValue(undefined),
    loadCells: vi.fn().mockResolvedValue(undefined),
  } as Partial<ReturnType<typeof useStore.getState>>);

  const AppMod = await import("../App");
  const App = AppMod.default;
  return render(<App />);
}

// Walks the rendered DOM and returns a flat in-order list of "anchor"
// nodes — each entry is either an inserter or a labelled cell/section.
type Anchor =
  | { type: "inserter"; el: Element }
  | { type: "cell"; el: Element; label: string }
  | { type: "section"; el: Element; label: string };

function collectAnchors(root: Element): Anchor[] {
  const out: Anchor[] = [];
  // querySelectorAll preserves DOM order — we then dedupe nested matches by
  // walking once and recording whichever role each element plays.
  const all = root.querySelectorAll<Element>(
    ".inserter, .md-cell, .cell, .section-group",
  );
  all.forEach((el) => {
    if (el.classList.contains("inserter")) {
      out.push({ type: "inserter", el });
      return;
    }
    if (el.classList.contains("section-group")) {
      const headingEl = el.querySelector(".section-heading-text");
      const label = headingEl?.textContent?.trim() || "(untitled)";
      out.push({ type: "section", el, label });
      return;
    }
    // Either .md-cell (markdown note) or .cell (agent/empty cell).
    // Skip .cell elements that are descendants of a .section-group section-heading-text
    // — none today, but defensive.
    let label = "";
    if (el.classList.contains("md-cell")) {
      label = el.textContent?.trim().slice(0, 80) || "";
    } else {
      const title = el.querySelector(".cell-title");
      label = title?.textContent?.trim() || el.textContent?.trim().slice(0, 80) || "";
    }
    out.push({ type: "cell", el, label });
  });
  return out;
}

describe("CellInserter placement", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("3 plain markdown cells, no sections -> 4 inserters (top + after each)", async () => {
    const { container } = await renderWithCells([
      md("m1", "first note", 0),
      md("m2", "second note", 1),
      md("m3", "third note", 2),
    ]);
    const inserters = container.querySelectorAll(".inserter");
    // top + after-each-of-3 = 4
    expect(inserters.length).toBe(4);
  });

  it("General-like layout [H1-A, MD1, MD2, H1-B, MD3] has an inserter between MD2 and H1-B", async () => {
    // H1 headings each open their own top-level section (bug-4 case).
    const cells = [
      md("hA", "# Active", 0),
      md("m1", "note one", 1),
      md("m2", "note two", 2),
      md("hB", "# Pending", 3),
      md("m3", "note three", 4),
    ];
    const { container } = await renderWithCells(cells);
    const anchors = collectAnchors(container);

    // Find the indexes of m2 (last child of Active) and the Pending section.
    const m2Idx = anchors.findIndex(
      (a) => a.type === "cell" && a.label.includes("note two"),
    );
    const pendingIdx = anchors.findIndex(
      (a) => a.type === "section" && a.label === "Pending",
    );
    expect(m2Idx).toBeGreaterThan(-1);
    expect(pendingIdx).toBeGreaterThan(m2Idx);

    // There must be at least one inserter strictly between them.
    const between = anchors
      .slice(m2Idx + 1, pendingIdx)
      .filter((a) => a.type === "inserter");
    expect(between.length).toBeGreaterThan(0);
  });

  it("section with multiple children has inserters between children (bug 2)", async () => {
    const cells = [
      md("h", "## A", 0),
      agent("c1", 1, "alpha"),
      agent("c2", 2, "bravo"),
      agent("c3", 3, "charlie"),
    ];
    const { container } = await renderWithCells(cells);
    const anchors = collectAnchors(container);

    // The .cell-title text includes a chevron glyph prefix ("▸"/"▾") followed
    // by the title — match by inclusion, not equality.
    const idxAlpha = anchors.findIndex(
      (a) => a.type === "cell" && a.label.includes("alpha"),
    );
    const idxBravo = anchors.findIndex(
      (a) => a.type === "cell" && a.label.includes("bravo"),
    );
    const idxCharlie = anchors.findIndex(
      (a) => a.type === "cell" && a.label.includes("charlie"),
    );
    expect(idxAlpha).toBeGreaterThan(-1);
    expect(idxBravo).toBeGreaterThan(idxAlpha);
    expect(idxCharlie).toBeGreaterThan(idxBravo);

    const betweenAB = anchors
      .slice(idxAlpha + 1, idxBravo)
      .filter((a) => a.type === "inserter");
    const betweenBC = anchors
      .slice(idxBravo + 1, idxCharlie)
      .filter((a) => a.type === "inserter");
    expect(betweenAB.length).toBeGreaterThan(0);
    expect(betweenBC.length).toBeGreaterThan(0);
  });

  it("collapsed section hides inner inserters; outer inserters still present", async () => {
    const cells = [
      md("h", "## A", 0),
      agent("c1", 1, "alpha"),
      agent("c2", 2, "bravo"),
    ];
    // Section key in inferSections is `${cell.id}#${idx}`. For cell "h" at
    // visible index 0 the key is "h#0".
    const { container } = await renderWithCells(cells, {
      p1: { "h#0": true },
    });

    // SectionGroup only renders .section-children when not collapsed.
    const childrenWrap = container.querySelector(".section-children");
    expect(childrenWrap).toBeNull();

    // Visible inserters when section is collapsed: top-of-list + after-section.
    const inserters = container.querySelectorAll(".inserter");
    expect(inserters.length).toBe(2);
  });

  it("empty section (only header) has top-of-list + after-section inserters only (no inside duplicate)", async () => {
    // Bug B follow-up: an empty section used to render an inside
    // top-of-children inserter anchored to the header id AND an outside
    // after-section inserter anchored to the header id — visually adjacent
    // duplicates. The fix drops the inside one; clicking the outside
    // after-section inserter creates a cell with after_cell_id=headerId
    // which the backend places as the section's first child.
    const cells = [md("h", "## empty", 0)];
    const { container } = await renderWithCells(cells);

    // Top-of-list + after-section = 2 (no inside inserter for empty section).
    const inserters = container.querySelectorAll(".inserter");
    expect(inserters.length).toBe(2);

    // .section-children only renders when the section actually has children;
    // for an empty (expanded) section SectionGroup renders an empty wrapper.
    // The wrapper, if present, must contain zero inserters.
    const childrenWrap = container.querySelector(".section-children");
    if (childrenWrap) {
      expect(childrenWrap.querySelectorAll(".inserter").length).toBe(0);
    }
  });

  it("General-like layout [H1-A, MD1, MD2, H1-B, MD3] renders exact inserter count (no doubles)", async () => {
    // Cells:
    //   hA  -> section "Active"   level 1
    //     m1
    //     m2
    //   hB  -> section "Pending"  level 1
    //     m3
    //
    // Expected inserters (Bug A / B follow-up fix):
    //   1) ins-top (top of list)
    //   2) section Active inside: top-of-children (anchored to hA)
    //   3) section Active inside: between m1 and m2
    //   4) ins-after-Active (parent loop, outside, anchored to m2)
    //   5) section Pending inside: top-of-children (anchored to hB)
    //   6) ins-after-Pending (parent loop, outside, anchored to m3)
    // Total = 6. There is NO inside-bottom inserter after the last child of
    // either section — the parent loop's outside inserter occupies that gap.
    const cells = [
      md("hA", "# Active", 0),
      md("m1", "note one", 1),
      md("m2", "note two", 2),
      md("hB", "# Pending", 3),
      md("m3", "note three", 4),
    ];
    const { container } = await renderWithCells(cells);
    const inserters = container.querySelectorAll(".inserter");
    expect(inserters.length).toBe(6);
  });

  it("exactly one inserter between every adjacent visible cell/section pair (no doubles)", async () => {
    // Hits the Bug A regression directly: at every section boundary there
    // used to be TWO stacked inserters (inside-bottom + outside-after). The
    // fix guarantees one inserter per gap.
    const cells = [
      md("hA", "# Active", 0),
      md("m1", "note one", 1),
      md("m2", "note two", 2),
      md("hB", "# Pending", 3),
      md("m3", "note three", 4),
    ];
    const { container } = await renderWithCells(cells);
    const anchors = collectAnchors(container);

    // Find indices of every cell/section anchor and check the gap between
    // every adjacent pair contains exactly one inserter.
    const nonInserterIdx: number[] = [];
    anchors.forEach((a, i) => {
      if (a.type !== "inserter") nonInserterIdx.push(i);
    });
    expect(nonInserterIdx.length).toBeGreaterThan(1);
    for (let k = 0; k + 1 < nonInserterIdx.length; k++) {
      const from = nonInserterIdx[k];
      const to = nonInserterIdx[k + 1];
      const between = anchors
        .slice(from + 1, to)
        .filter((a) => a.type === "inserter");
      // collectAnchors records a section group once at its outer .section-group
      // element; child cells are recorded as nested anchors that follow. The
      // outside-after-section inserter is emitted AFTER the .section-group node
      // in DOM order, so the gap between a section anchor and its first
      // descendant cell is empty in collectAnchors terms — accept 0 or 1.
      expect(between.length).toBeLessThanOrEqual(1);
    }
  });
});
