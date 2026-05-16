// Tiny markdown renderer ported from the prototype (app.jsx 829–877).
// Supports: # / ## / ### headings, **bold**, *italic*, `code`, [link](url),
// > blockquote, - / * lists, --- hr, paragraphs.

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderInline(s: string): string {
  let out = escapeHtml(s);
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|\W)\*([^*\n]+)\*(?=\W|$)/g, "$1<em>$2</em>");
  out = out.replace(/_([^_\n]+)_/g, "<em>$1</em>");
  out = out.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>',
  );
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

// Sanitize a chunk of inline SVG/HTML. Removes <script>, <iframe>, etc, and
// any on* event attributes and javascript: URLs. Regex-only — not a full
// DOMPurify, but good enough for trusted-author content with light hygiene.
export function sanitizeSvg(src: string): string {
  let out = src;
  // Remove dangerous tags entirely (including their inner content).
  const danger = ["script", "iframe", "object", "embed", "link", "meta", "style"];
  for (const tag of danger) {
    const open = new RegExp(`<${tag}\\b[^>]*>[\\s\\S]*?</${tag}>`, "gi");
    const selfClose = new RegExp(`<${tag}\\b[^>]*/?>`, "gi");
    out = out.replace(open, "");
    out = out.replace(selfClose, "");
  }
  // Strip event handler attributes (on*="..." or on*='...' or on*=bare).
  out = out.replace(/\son[a-z]+\s*=\s*"[^"]*"/gi, "");
  out = out.replace(/\son[a-z]+\s*=\s*'[^']*'/gi, "");
  out = out.replace(/\son[a-z]+\s*=\s*[^\s>]+/gi, "");
  // Strip javascript: URLs in href/src/xlink:href.
  out = out.replace(/(href|src|xlink:href)\s*=\s*"\s*javascript:[^"]*"/gi, '$1="#"');
  out = out.replace(/(href|src|xlink:href)\s*=\s*'\s*javascript:[^']*'/gi, "$1='#'");
  return out;
}
