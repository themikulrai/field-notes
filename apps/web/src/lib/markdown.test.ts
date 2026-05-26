import { describe, it, expect } from "vitest";
import { renderMarkdown, sanitizeSvg } from "./markdown";

describe("renderMarkdown", () => {
  it("renders h1/h2/h3/h4", () => {
    expect(renderMarkdown("# a")).toBe("<h1>a</h1>");
    expect(renderMarkdown("## b")).toBe("<h2>b</h2>");
    expect(renderMarkdown("### c")).toBe("<h3>c</h3>");
    expect(renderMarkdown("#### d")).toBe("<h4>d</h4>");
  });

  it("does not loop forever on unsupported `#`-prefixed lines", () => {
    // Regression: a line like `#####` or `#hashtag` previously hit a paragraph
    // loop that refused to consume `#`-prefixed lines without incrementing i,
    // hanging the renderer and locking the browser.
    for (const src of ["#####", "######", "#hashtag", "#", "##NoSpace"]) {
      // Vitest aborts a single test after a couple seconds; if this regresses
      // the test run hangs at this line.
      const out = renderMarkdown(src);
      expect(typeof out).toBe("string");
      expect(out.length).toBeGreaterThan(0);
    }
  });

  it("renders paragraphs and inline formatting", () => {
    expect(renderMarkdown("hello **world**")).toBe("<p>hello <strong>world</strong></p>");
  });

  describe("link href safety", () => {
    it("allows https URLs", () => {
      expect(renderMarkdown("[ok](https://x.com)")).toBe(
        '<p><a href="https://x.com" target="_blank" rel="noopener">ok</a></p>',
      );
    });
    it("allows mailto URLs", () => {
      expect(renderMarkdown("[ok](mailto:x@y.z)")).toBe(
        '<p><a href="mailto:x@y.z" target="_blank" rel="noopener">ok</a></p>',
      );
    });
    it("allows absolute path URLs", () => {
      expect(renderMarkdown("[ok](/path)")).toBe(
        '<p><a href="/path" target="_blank" rel="noopener">ok</a></p>',
      );
    });
    it("allows fragment URLs", () => {
      expect(renderMarkdown("[ok](#anchor)")).toBe(
        '<p><a href="#anchor" target="_blank" rel="noopener">ok</a></p>',
      );
    });
    it("rejects javascript: URLs and renders as plain text", () => {
      const out = renderMarkdown("[bad](javascript:alert(1))");
      expect(out).not.toContain("<a ");
      expect(out).not.toContain("javascript:");
      expect(out).toContain("bad");
    });
    it("rejects javascript: URLs case-insensitively", () => {
      const out = renderMarkdown("[bad](JaVaScRiPt:alert(1))");
      expect(out).not.toContain("<a ");
      expect(out).not.toMatch(/javascript:/i);
      expect(out).toContain("bad");
    });
    it("rejects data: URLs", () => {
      const out = renderMarkdown("[bad](data:text/html,xxx)");
      expect(out).not.toContain("<a ");
      expect(out).not.toContain("data:");
      expect(out).toContain("bad");
    });
    it("rejects vbscript: URLs", () => {
      const out = renderMarkdown("[bad](vbscript:msgbox)");
      expect(out).not.toContain("<a ");
      expect(out).not.toContain("vbscript:");
      expect(out).toContain("bad");
    });
    it("rejects javascript: with leading whitespace", () => {
      const out = renderMarkdown("[bad]( javascript:alert(1))");
      expect(out).not.toContain("<a ");
      expect(out).not.toMatch(/javascript:/i);
      expect(out).toContain("bad");
    });
  });
});

describe("sanitizeSvg", () => {
  it("strips onload event handler", () => {
    const out = sanitizeSvg('<svg onload="alert(1)"></svg>');
    expect(out.toLowerCase()).not.toContain("onload");
    expect(out).not.toContain("alert(1)");
  });

  it("strips inline <script> inside svg", () => {
    const out = sanitizeSvg("<svg><script>alert(1)</script></svg>");
    expect(out.toLowerCase()).not.toContain("<script");
    expect(out).not.toContain("alert(1)");
  });

  it("strips multiple event handlers including mixed case", () => {
    const out = sanitizeSvg("<svg onerror=alert(1) onLoad=alert(1)></svg>");
    expect(out.toLowerCase()).not.toContain("onerror");
    expect(out.toLowerCase()).not.toContain("onload");
    expect(out).not.toContain("alert(1)");
  });

  it("strips javascript: in <use href>", () => {
    const out = sanitizeSvg('<svg><use href="javascript:alert(1)"/></svg>');
    expect(out.toLowerCase()).not.toContain("javascript:");
    expect(out).not.toContain("alert(1)");
  });

  it("preserves a legitimate svg shape", () => {
    const out = sanitizeSvg('<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="3"/></svg>');
    expect(out.toLowerCase()).toContain("<svg");
    expect(out.toLowerCase()).toContain("<circle");
    expect(out).toContain('viewBox="0 0 10 10"');
    expect(out).toContain('cx="5"');
    expect(out).toContain('cy="5"');
    expect(out).toContain('r="3"');
  });

  it("strips newline-embedded event handlers", () => {
    const out = sanitizeSvg("<svg\n onload=\nalert(1)></svg>");
    expect(out.toLowerCase()).not.toContain("onload");
    expect(out).not.toContain("alert(1)");
  });
});
