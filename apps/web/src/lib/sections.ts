// Walks a cell list and groups cells under markdown # / ## / ### / #### headings.
// Output is a tree of SectionNode for the renderer; collapse state survives
// reorder because keys are derived from cell IDs.
//
// Levels follow the markdown heading depth:
//   `# title`    -> level 1
//   `## title`   -> level 2
//   `### title`  -> level 3
//   `#### title` -> level 4
// A heading at level N nests under the closest open heading of level < N, so
// H4s tuck under their H3 which tucks under their H2 which tucks under its H1.
// Headings shallower than or equal to the current depth close the stack first.

import type { Cell } from "./types";

export type SectionLevel = 1 | 2 | 3 | 4;
export type SectionNodeKind = "section" | "cell" | "markdown";

export interface SectionNode {
  kind: SectionNodeKind;
  level?: SectionLevel;
  heading?: string;
  cell?: Cell;
  key: string;
  children?: SectionNode[];
}

function headingLevel(body: string | null | undefined): SectionLevel | null {
  if (!body) return null;
  // Find first non-blank line; that's where the heading must live to count.
  const lines = body.split("\n");
  for (const raw of lines) {
    const line = raw.trimStart();
    if (!line.trim()) continue;
    if (line.startsWith("#### ")) return 4;
    if (line.startsWith("### ")) return 3;
    if (line.startsWith("## ")) return 2;
    if (line.startsWith("# ")) return 1;
    return null;
  }
  return null;
}

function headingText(body: string): string {
  const lines = body.split("\n");
  for (const raw of lines) {
    const line = raw.trimStart();
    if (!line.trim()) continue;
    if (line.startsWith("#### ")) return line.slice(5).trim();
    if (line.startsWith("### ")) return line.slice(4).trim();
    if (line.startsWith("## ")) return line.slice(3).trim();
    if (line.startsWith("# ")) return line.slice(2).trim();
    return "";
  }
  return "";
}

export function inferSections(cells: Cell[]): SectionNode[] {
  const root: SectionNode[] = [];
  // Stack of open section nodes, deepest-last.
  const stack: SectionNode[] = [];

  const push = (n: SectionNode) => {
    const target = stack.length ? stack[stack.length - 1] : null;
    if (target) target.children!.push(n);
    else root.push(n);
  };

  cells.forEach((cell, idx) => {
    const key = `${cell.id}#${idx}`;
    if (cell.kind === "markdown") {
      const lvl = headingLevel(cell.body);
      if (lvl) {
        // Close any open sections at the same or deeper level.
        while (stack.length && (stack[stack.length - 1].level ?? 0) >= lvl) {
          stack.pop();
        }
        const node: SectionNode = {
          kind: "section",
          level: lvl,
          heading: headingText(cell.body || ""),
          cell,
          key,
          children: [],
        };
        push(node);
        stack.push(node);
        return;
      }
      // Plain note (no heading) — attaches like a regular cell.
      push({ kind: "markdown", cell, key });
      return;
    }
    push({ kind: "cell", cell, key });
  });

  return root;
}

// Flatten a section tree to a list of leaf cells (used by the empty-state /
// filter logic that operates on raw cells, not the tree).
export function flattenSections(nodes: SectionNode[]): Cell[] {
  const out: Cell[] = [];
  const walk = (n: SectionNode) => {
    if (n.cell) out.push(n.cell);
    if (n.children) for (const c of n.children) walk(c);
  };
  for (const n of nodes) walk(n);
  return out;
}

// Returns the id of the deepest right-most descendant cell of a subtree.
// For a plain (non-section) node, returns its own cell id. For a section
// with no children, returns the section's header cell id. Used by the
// cell-inserter UI to anchor an "insert after this subtree" affordance.
export function lastCellId(node: SectionNode): string {
  if (node.kind === "section" && node.children && node.children.length > 0) {
    return lastCellId(node.children[node.children.length - 1]);
  }
  return node.cell!.id;
}
