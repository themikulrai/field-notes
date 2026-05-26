// Tiny markdown renderer ported from the prototype (app.jsx 829–877).
// Supports: # / ## / ### / #### headings, **bold**, *italic*, `code`, [link](url),
// > blockquote, - / * lists, --- hr, paragraphs.

import DOMPurify from "isomorphic-dompurify";

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Allow only well-known safe URL schemes / relative / fragment links. Anything
// else (javascript:, data:, vbscript:, etc.) is rejected so the renderer can
// fall back to plain text. Leading whitespace is stripped before testing so
// `[x]( javascript:...)` cannot smuggle a scheme past the check.
export function isSafeHref(url: string): boolean {
  const trimmed = url.trim();
  return /^(https?:|mailto:|\/|#)/i.test(trimmed);
}

function renderInline(s: string): string {
  let out = escapeHtml(s);
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|\W)\*([^*\n]+)\*(?=\W|$)/g, "$1<em>$2</em>");
  out = out.replace(/_([^_\n]+)_/g, "<em>$1</em>");
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text: string, url: string) => {
    if (!isSafeHref(url)) return text;
    return `<a href="${url}" target="_blank" rel="noopener">${text}</a>`;
  });
  return out;
}

export function renderMarkdown(src: string | null | undefined): string {
  const lines = (src || "").split("\n");
  const blocks: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith("#### ")) {
      blocks.push(`<h4>${renderInline(line.slice(5))}</h4>`);
      i++;
      continue;
    }
    if (line.startsWith("### ")) {
      blocks.push(`<h3>${renderInline(line.slice(4))}</h3>`);
      i++;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push(`<h2>${renderInline(line.slice(3))}</h2>`);
      i++;
      continue;
    }
    if (line.startsWith("# ")) {
      blocks.push(`<h1>${renderInline(line.slice(2))}</h1>`);
      i++;
      continue;
    }
    // Defensive: any other `#`-prefixed line (e.g. `#####`, `#hashtag`,
    // `##NoSpace`) is not a recognized heading. The paragraph block below
    // refuses to consume `#`-prefixed lines, so without this guard `i` would
    // never advance and renderMarkdown would loop forever, hanging the React
    // render path and locking the browser.
    if (line.startsWith("#")) {
      blocks.push(`<p>${renderInline(line)}</p>`);
      i++;
      continue;
    }
    if (line.trim() === "---" || line.trim() === "***") {
      blocks.push("<hr />");
      i++;
      continue;
    }
    if (line.startsWith("> ")) {
      const buf: string[] = [];
      while (i < lines.length && lines[i].startsWith("> ")) {
        buf.push(renderInline(lines[i].slice(2)));
        i++;
      }
      blocks.push(`<blockquote>${buf.join("<br />")}</blockquote>`);
      continue;
    }
    if (/^[-*]\s/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i])) {
        buf.push(`<li>${renderInline(lines[i].replace(/^[-*]\s/, ""))}</li>`);
        i++;
      }
      blocks.push(`<ul>${buf.join("")}</ul>`);
      continue;
    }
    if (/^\d+\.\s/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        buf.push(`<li>${renderInline(lines[i].replace(/^\d+\.\s/, ""))}</li>`);
        i++;
      }
      blocks.push(`<ol>${buf.join("")}</ol>`);
      continue;
    }
    const buf: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].startsWith("#") &&
      !lines[i].startsWith("> ") &&
      !/^[-*]\s/.test(lines[i]) &&
      !/^\d+\.\s/.test(lines[i])
    ) {
      buf.push(renderInline(lines[i]));
      i++;
    }
    blocks.push(`<p>${buf.join("<br />")}</p>`);
  }
  return blocks.join("");
}

// Sanitize a chunk of inline SVG. Delegates to DOMPurify (isomorphic-dompurify)
// with the built-in SVG + SVG filters profiles so element/attribute allow-listing
// happens against a real DOM rather than the previous brittle regex pass.
export function sanitizeSvg(svg: string): string {
  return DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true, svgFilters: true } });
}
