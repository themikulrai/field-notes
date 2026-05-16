// Collapsible markdown-heading section. Title is rendered as <h2>/<h3>.

import type { ReactNode } from "react";

interface Props {
  level: 2 | 3;
  heading: string;
  collapsed: boolean;
  onToggle: () => void;
  children: ReactNode;
}

export function SectionGroup({ level, heading, collapsed, onToggle, children }: Props) {
  const Head = level === 2 ? "h2" : "h3";
  return (
    <section className={`section-group section-level-${level}`}>
      <header className="section-heading" onClick={onToggle} role="button" aria-expanded={!collapsed}>
        <span className={`section-caret mono ${!collapsed ? "is-open" : ""}`}>▶</span>
        <Head className="mono">{heading || "(untitled section)"}</Head>
      </header>
      {!collapsed && <div className="section-children">{children}</div>}
    </section>
  );
}
