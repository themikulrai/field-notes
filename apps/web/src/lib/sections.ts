// Walks a cell list and groups cells under markdown ## / ### headings.
// Output is a tree of SectionNode for the renderer; collapse state survives
// reorder because keys are derived from cell IDs.

import type { Cell } from "./types";

export type SectionNodeKind = "section" | "cell" | "markdown";

export interface SectionNode {
  kind: SectionNodeKind;
  level?: 2 | 3;
  heading?: string;
  cell?: Cell;
  key: string;
  children?: SectionNode[];
}

function headingLevel(body: string | null | undefined): 2 | 3 | null {
  if (!body) return null;
  // Find first non-blank line; that's where the heading must live to count.
  const lines = body.split("\n");
  for (const raw of lines) {
    const line = raw.trimStart();
    if (!line.trim()) continue;
    if (line.startsWith("### ")) return 3;
    if (line.startsWith("## ")) return 2;
    return null;
  }
  return null;
}

function headingText(body: string): string {
  const lines = body.split("\n");
  for (const raw of lines) {
    const line = raw.trimStart();
    if (!line.trim()) continue;
    if (line.startsWith("### ")) return line.slice(4).trim();
    if (line.startsWith("## ")) return line.slice(3).trim();
    return "";
  }
  return "";
}

export function inferSections(cells: Cell[]): SectionNode[] {
  // Two-pass: build a flat list of tokens, then fold into nested sections.
  type Tok =
    | { t: "h2"; cell: Cell; key: string; text: string }
    | { t: "h3"; cell: Cell; key: string; text: string }
    | { t: "cell"; cell: Cell; key: string }
    | { t: "md"; cell: Cell; key: string };

  const tokens: Tok[] = cells.map((cell, idx) => {
    const key = `${cell.id}#${idx}`;
    if (cell.kind === "markdown") {
      const lvl = headingLevel(cell.body);
      if (lvl === 2) return { t: "h2", cell, key, text: headingText(cell.body || "") };
      if (lvl === 3) return { t: "h3", cell, key, text: headingText(cell.body || "") };
      return { t: "md", cell, key };
    }
    return { t: "cell", cell, key };
  });

  // Fold with a stack: top is current open section (level 2 or 3).
  const root: SectionNode[] = [];
  let curH2: SectionNode | null = null;
  let curH3: SectionNode | null = null;

  const push = (n: SectionNode) => {
    const target = curH3 ?? curH2;
    if (target) target.children!.push(n);
    else root.push(n);
  };

  for (const tok of tokens) {
    if (tok.t === "h2") {
      const node: SectionNode = {
        kind: "section",
        level: 2,
        heading: tok.text,
        cell: tok.cell,
        key: tok.key,
        children: [],
      };
      root.push(node);
      curH2 = node;
      curH3 = null;
      continue;
    }
    if (tok.t === "h3") {
      const node: SectionNode = {
        kind: "section",
        level: 3,
        heading: tok.text,
        cell: tok.cell,
        key: tok.key,
        children: [],
      };
      if (curH2) curH2.children!.push(node);
      else root.push(node);
      curH3 = node;
      continue;
    }
    if (tok.t === "md") {
      push({ kind: "markdown", cell: tok.cell, key: tok.key });
      continue;
    }
    // plain cell
    push({ kind: "cell", cell: tok.cell, key: tok.key });
  }

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
