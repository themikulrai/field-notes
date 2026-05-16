import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Sparkline, buildSandboxSrcdoc } from "./Sparkline";
import type { Visual } from "../lib/types";

describe("Sparkline", () => {
  it("data + line renders SVG <path>", () => {
    const visual: Visual = {
      kind: "data",
      chart: "line",
      series: [
        { x: 0, y: 1 },
        { x: 1, y: 0.5 },
        { x: 2, y: 0.2 },
      ],
    };
    const { container } = render(<Sparkline visual={visual} />);
    const paths = container.querySelectorAll("path");
    expect(paths.length).toBeGreaterThan(0);
  });

  it("svg kind strips <script> tag", () => {
    const visual: Visual = {
      kind: "svg",
      source: '<svg><script>alert(1)</script><rect onclick="bad()" x="0" y="0"/></svg>',
    };
    const { container } = render(<Sparkline visual={visual} />);
    expect(container.innerHTML).not.toMatch(/<script/i);
    expect(container.innerHTML).not.toMatch(/onclick/i);
  });

  it("svg kind strips iframe / javascript: href", () => {
    const visual: Visual = {
      kind: "svg",
      source: '<svg><iframe src="evil"></iframe><a href="javascript:bad()">x</a></svg>',
    };
    const { container } = render(<Sparkline visual={visual} />);
    expect(container.innerHTML).not.toMatch(/<iframe/i);
    expect(container.innerHTML).not.toMatch(/javascript:/i);
  });

  it("sandbox kind renders iframe with srcdoc containing html+js+css", () => {
    const visual: Visual = {
      kind: "sandbox",
      html: "<div id=hello>hi</div>",
      js: "console.log('x')",
      css: "body { color: red; }",
    };
    const { container } = render(<Sparkline visual={visual} />);
    const iframe = container.querySelector("iframe");
    expect(iframe).not.toBeNull();
    const srcdoc = iframe!.getAttribute("srcdoc") || "";
    expect(srcdoc).toContain("<div id=hello>hi</div>");
    expect(srcdoc).toContain("console.log('x')");
    expect(srcdoc).toContain("body { color: red; }");
    expect(srcdoc).toContain("plotly.min.js");
    expect(iframe!.getAttribute("sandbox")).toBe("allow-scripts");
  });

  it("buildSandboxSrcdoc round-trips fields", () => {
    const doc = buildSandboxSrcdoc({ kind: "sandbox", html: "<p>a</p>", js: "//j", css: ".c{}" });
    expect(doc).toContain("<p>a</p>");
    expect(doc).toContain(".c{}");
    expect(doc).toContain("//j");
  });

  // Vega test skipped: vega-embed dynamic-import in jsdom is fragile (canvas/SVG
  // dependencies). See README.
});
