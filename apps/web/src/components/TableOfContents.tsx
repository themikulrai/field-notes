// Left-rail table of contents that mirrors the inferred section tree.
//
// Walks the section tree depth-first to build a flat list of H1/H2/H3/H4
// entries with a count of descendant cells. Scroll-spy tracks which section's
// heading has crossed the viewport's upper third; click-to-jump scrolls
// smoothly to the section via its `data-section-id` anchor.

import { useEffect, useMemo, useState } from "react";
import type { SectionNode, SectionLevel } from "../lib/sections";

interface TocItem {
  id: string;
  level: SectionLevel;
  title: string;
  count: number;
}

function descendantLeafCount(node: SectionNode): number {
  let n = 0;
  for (const ch of node.children || []) {
    if (ch.kind === "section") n += descendantLeafCount(ch);
    else n += 1;
  }
  return n;
}

function flattenHeadings(nodes: SectionNode[], out: TocItem[]): void {
  for (const node of nodes) {
    if (node.kind === "section" && node.cell && node.level) {
      out.push({
        id: node.cell.id,
        level: node.level,
        title: node.heading || "(untitled section)",
        count: descendantLeafCount(node),
      });
      flattenHeadings(node.children || [], out);
    } else if (node.kind === "section") {
      flattenHeadings(node.children || [], out);
    }
  }
}

interface Props {
  sections: SectionNode[];
}

export function TableOfContents({ sections }: Props) {
  const items = useMemo(() => {
    const acc: TocItem[] = [];
    flattenHeadings(sections, acc);
    return acc;
  }, [sections]);

  const [active, setActive] = useState<string | null>(null);
  const ids = useMemo(() => items.map((i) => i.id).join("|"), [items]);

  useEffect(() => {
    const idList = items.map((i) => i.id);
    if (idList.length === 0) {
      setActive(null);
      return;
    }
    const onScroll = () => {
      const trigger = window.innerHeight * 0.33;
      let current: string | null = null;
      for (const id of idList) {
        const el = document.querySelector(`[data-section-id="${id}"]`);
        if (!el) continue;
        const top = el.getBoundingClientRect().top;
        if (top - trigger <= 0) current = id;
      }
      setActive(current);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids]);

  const scrollTo = (id: string) => {
    const el = document.querySelector(`[data-section-id="${id}"]`);
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY - 100;
    window.scrollTo({ top, behavior: "smooth" });
    setActive(id);
  };

  return (
    <nav className="toc" aria-label="Table of contents">
      <div className="toc-head">
        <h3 className="toc-title mono">CONTENTS</h3>
        <span className="toc-count mono">{items.length || "—"}</span>
      </div>
      {items.length === 0 ? (
        <div className="toc-empty">
          no sections yet · use <strong>#</strong>, <strong>##</strong>, <strong>###</strong>, <strong>####</strong> in notes
        </div>
      ) : (
        <ul className="toc-list">
          {items.map((it) => (
            <li
              key={it.id}
              className={`toc-item toc-item--${it.level} ${active === it.id ? "is-current" : ""}`}
              onClick={() => scrollTo(it.id)}
              title={it.title}
            >
              <span className="toc-tier mono">H{it.level}</span>
              <span className="toc-label">{it.title}</span>
              {it.count > 0 && <span className="toc-pill mono">{it.count}</span>}
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
