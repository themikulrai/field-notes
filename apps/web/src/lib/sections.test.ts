import { describe, it, expect } from "vitest";
import { inferSections, lastCellId } from "./sections";
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

  it("key is the cell id (no #idx suffix) so React keys survive reorder", () => {
    const cells = [agent("alpha", 0), agent("beta", 1)];
    const tree = inferSections(cells);
    expect(tree[0].key).toBe("alpha");
    expect(tree[1].key).toBe("beta");
  });

  it("keys remain stable when a cell is inserted before another", () => {
    // beta starts at idx 1; after inserting alpha before it, beta is at
    // idx 2. Under the old `${id}#${idx}` scheme its key changed; under
    // the new scheme it stays "beta".
    const before = inferSections([agent("beta", 0)]);
    const after = inferSections([agent("alpha", 0), agent("beta", 1)]);
    const betaBefore = before.find((n) => n.cell?.id === "beta")!;
    const betaAfter = after.find((n) => n.cell?.id === "beta")!;
    expect(betaAfter.key).toBe(betaBefore.key);
  });
});

describe("lastCellId", () => {
  it("plain cell node returns its own id", () => {
    const tree = inferSections([agent("solo", 0)]);
    expect(lastCellId(tree[0])).toBe("solo");
  });

  it("plain markdown node returns its own id", () => {
    const tree = inferSections([md("note", "just prose", 0)]);
    expect(lastCellId(tree[0])).toBe("note");
  });

  it("section with one direct child returns that child's id", () => {
    const tree = inferSections([md("h", "## A", 0), agent("only", 1)]);
    expect(lastCellId(tree[0])).toBe("only");
  });

  it("section with multiple children returns the last child's id", () => {
    const tree = inferSections([
      md("h", "## A", 0),
      agent("first", 1),
      agent("middle", 2),
      agent("last", 3),
    ]);
    expect(lastCellId(tree[0])).toBe("last");
  });

  it("nested H1 > H2 > H3 with cells returns deepest right-most cell id", () => {
    const tree = inferSections([
      md("h1", "# outer", 0),
      md("h2", "## middle", 1),
      md("h3", "### inner", 2),
      agent("leaf-a", 3),
      agent("leaf-b", 4),
    ]);
    // tree[0] is the H1 section; its rightmost descendant is leaf-b inside
    // the H3 inside the H2.
    expect(lastCellId(tree[0])).toBe("leaf-b");
  });

  it("nested section: lastCellId of an inner section descends to its leaf", () => {
    const tree = inferSections([
      md("h2", "## outer", 0),
      md("h3", "### inner", 1),
      agent("x", 2),
    ]);
    // tree[0] is the H2; its only child is the H3 section; lastCellId of
    // the H3 child is "x".
    expect(lastCellId(tree[0].children![0])).toBe("x");
    expect(lastCellId(tree[0])).toBe("x");
  });

  it("empty section (only header, no children) returns the header cell id", () => {
    const tree = inferSections([md("h", "## empty", 0)]);
    expect(tree[0].kind).toBe("section");
    expect(tree[0].children).toHaveLength(0);
    expect(lastCellId(tree[0])).toBe("h");
  });
});
