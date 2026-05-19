import { describe, it, expect } from "vitest";
import { renderMarkdown } from "./markdown";

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
});
