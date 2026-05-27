// Regression guard for the table-overflow corruption seen in production
// (long mono identifiers like `HF_LEROBOT_HOME` bleeding across grid cell
// borders into neighbouring columns). The styling contract is:
//   - `.metric` must clip + allow grid-track shrinking (overflow:hidden, min-width:0)
//   - `.metric-k|v|d` must permit intra-token wrapping (overflow-wrap:anywhere)
// jsdom does not honour `import "../styles/app.css"` for CSSOM, so we read
// the stylesheet as text and assert the relevant rule bodies contain the
// required declarations.

import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { MetricRow } from "./MetricRow";

const cssPath = resolve(process.cwd(), "src/styles/app.css");
const css = readFileSync(cssPath, "utf-8");

const longTokenItems = [
  { k: "SLURM_ARM0", v: "15599326 (v3); v1 15551167 FAIL/no-HF_LEROBOT_HOME v2 15567912 OOM@step~2000" },
  { k: "SLURM_ARM1", v: "15599327 (v3); v1 15551168 FAIL, v2 15567914 OOM@step~2000" },
  { k: "WANDB_PROJECT", v: "LB-Pi05-overfit" },
];

// Extract the body of the LAST CSS rule whose selector list contains
// `selector` (so a later override wins, matching CSS cascade).
function ruleBody(selector: string): string {
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  let last = "";
  while ((match = re.exec(css)) !== null) {
    const selectors = match[1].split(",").map((s) => s.trim());
    if (selectors.includes(selector)) last = match[2];
  }
  return last;
}

describe("MetricRow overflow contract", () => {
  it("renders all items with the structural classes", () => {
    const { container } = render(<MetricRow items={longTokenItems} />);
    expect(container.querySelectorAll(".metric")).toHaveLength(3);
    expect(container.querySelectorAll(".metric-k")).toHaveLength(3);
    expect(container.querySelectorAll(".metric-v")).toHaveLength(3);
  });

  it(".metric clips overflow and can shrink below intrinsic size", () => {
    const body = ruleBody(".metric");
    expect(body, "no .metric rule found").not.toBe("");
    expect(body).toMatch(/min-width\s*:\s*0\b/);
    expect(body).toMatch(/overflow\s*:\s*hidden\b/);
  });

  it(".metric-k / .metric-v / .metric-d allow intra-token wrapping", () => {
    // The combined selector lives on one rule, so check each individually
    // by looking for any rule that covers them with the required props.
    const re = /([^{}]+)\{([^{}]*overflow-wrap\s*:\s*anywhere[^{}]*word-break\s*:\s*break-word[^{}]*)\}/g;
    let hit = false;
    let m: RegExpExecArray | null;
    while ((m = re.exec(css)) !== null) {
      const selectors = m[1].split(",").map((s) => s.trim());
      if (
        selectors.includes(".metric-k") &&
        selectors.includes(".metric-v") &&
        selectors.includes(".metric-d")
      ) {
        hit = true;
        break;
      }
    }
    expect(hit, "no rule covers .metric-k, .metric-v, .metric-d with overflow-wrap:anywhere + word-break:break-word").toBe(true);
  });
});
