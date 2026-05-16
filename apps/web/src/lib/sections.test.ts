import { describe, it, expect } from "vitest";
import { inferSections } from "./sections";
import type { Cell } from "./types";

function md(id: string, body: string, position: number): Cell {
  return {
    id,
    project_id: "p",
    kind: "markdown",
    position,
    created_at: "",
    updated_at: "",
    locked: false,
    body,
  };
}
function agent(id: string, position: number, status: Cell["status"] = "open"): Cell {
  return {
    id,
    project_id: "p",
    kind: "agent",
    position,
    created_at: "",
    updated_at: "",
    locked: false,
    title: id,
    status,
  };
}

describe("inferSections", () => {
  it("flat list with no headings yields top-level cells", () => {
    const tree = inferSections([agent("a", 0), agent("b", 1), agent("c", 2)]);
    expect(tree).toHaveLength(3);
    expect(tree.every((n) => n.kind === "cell")).toBe(true);
  });

  it("## followed by 3 cells nests all 3", () => {
    const cells = [md("h1", "## Section A", 0), agent("a", 1), agent("b", 2), agent("c", 3)];
    const tree = inferSections(cells);
    expect(tree).toHaveLength(1);
    expect(tree[0].kind).toBe("section");
    expect(tree[0].level).toBe(2);
    expect(tree[0].children).toHaveLength(3);
  });

  it("## then ## yields two sibling sections", () => {
    const cells = [
      md("h1", "## A", 0),
      agent("a", 1),
      md("h2", "## B", 2),
      agent("b", 3),
    ];
    const tree = inferSections(cells);
    expect(tree).toHaveLength(2);
    expect(tree[0].children).toHaveLength(1);
    expect(tree[1].children).toHaveLength(1);
  });

  it("## then ### then ## : the second ## closes both", () => {
    const cells = [
      md("h1", "## A", 0),
      md("h2", "### sub", 1),
      agent("x", 2),
      md("h3", "## B", 3),
      agent("y", 4),
    ];
    const tree = inferSections(cells);
    expect(tree).toHaveLength(2);
    expect(tree[0].children).toHaveLength(1); // the ###
    expect(tree[0].children![0].kind).toBe("section");
    expect(tree[0].children![0].children).toHaveLength(1); // x
    expect(tree[1].children).toHaveLength(1); // y
  });

  it("### before any ## creates an orphan h3 at top level", () => {
    const cells = [md("h", "### loose", 0), agent("a", 1)];
    const tree = inferSections(cells);
    expect(tree[0].kind).toBe("section");
    expect(tree[0].level).toBe(3);
    expect(tree[0].children).toHaveLength(1);
  });

  it("heading at the end with no following cells: empty section", () => {
    const cells = [agent("a", 0), md("h", "## end", 1)];
    const tree = inferSections(cells);
    expect(tree).toHaveLength(2);
    expect(tree[1].kind).toBe("section");
    expect(tree[1].children).toHaveLength(0);
  });

  it("heading line with no trailing newline still detected", () => {
    const cells = [md("h", "## headline-only", 0), agent("a", 1)];
    const tree = inferSections(cells);
    expect(tree[0].kind).toBe("section");
    expect(tree[0].children).toHaveLength(1);
  });

  it("markdown without a ## is treated as markdown node, not section", () => {
    const cells = [md("h", "just some prose", 0), agent("a", 1)];
    const tree = inferSections(cells);
    expect(tree[0].kind).toBe("markdown");
    expect(tree[1].kind).toBe("cell");
  });

  it("keys are stable per id+position", () => {
    const cells = [md("h", "## A", 0), agent("a", 1)];
    const k1 = inferSections(cells)[0].key;
    const k2 = inferSections(cells)[0].key;
    expect(k1).toBe(k2);
  });
});
