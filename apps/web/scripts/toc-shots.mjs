// Capture screenshots of the running dev server at multiple viewport widths,
// and dump structured layout info for the .toc / .page-body / .top elements
// so we can diagnose what's actually rendered (not what we hope is rendered).

import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const URL = process.env.URL || "http://localhost:5173/";
const OUT = process.env.OUT || "/iris/u/mikulrai/.claude/jobs/fe41652d/shots";
const VIEWPORTS = [
  { w: 1920, h: 1080, label: "1920" },
  { w: 1440, h: 900,  label: "1440" },
  { w: 1280, h: 800,  label: "1280" },
  { w: 1024, h: 768,  label: "1024" },
  { w: 768,  h: 1024, label: "768"  },
];

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext();
const page = await ctx.newPage();

// Capture console + network failures so a broken JS load doesn't get silently masked.
page.on("console", (m) => {
  if (m.type() === "error" || m.type() === "warning") {
    console.log(`[console:${m.type()}]`, m.text());
  }
});
page.on("pageerror", (e) => console.log("[pageerror]", e.message));
page.on("requestfailed", (req) =>
  console.log("[requestfailed]", req.url(), req.failure()?.errorText),
);

const report = [];

for (const vp of VIEWPORTS) {
  await page.setViewportSize({ width: vp.w, height: vp.h });
  await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 15_000 });
  // SSE /events stream keeps the network busy forever; wait for the app shell instead.
  try {
    await page.waitForSelector(".page", { timeout: 10_000 });
  } catch (_e) {
    console.log(`[${vp.label}] WARNING: .page never rendered`);
  }
  await page.waitForTimeout(800);

  const layout = await page.evaluate(() => {
    const q = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return {
        x: Math.round(r.x),
        y: Math.round(r.y),
        w: Math.round(r.width),
        h: Math.round(r.height),
        display: cs.display,
        position: cs.position,
        visibility: cs.visibility,
        top: cs.top,
        right: cs.right,
        zIndex: cs.zIndex,
      };
    };
    return {
      vw: window.innerWidth,
      vh: window.innerHeight,
      "html.scrollHeight": document.documentElement.scrollHeight,
      "--top-h": getComputedStyle(document.documentElement).getPropertyValue("--top-h").trim(),
      ".top": q(".top"),
      ".page": q(".page"),
      ".page-body": q(".page-body"),
      ".toc": q(".toc"),
      ".toc-list": q(".toc-list"),
      ".cells": q(".cells"),
      "toc-items": document.querySelectorAll(".toc-item").length,
      "section-anchors": document.querySelectorAll("[data-section-id]").length,
      "key-gate-present": !!document.querySelector(".key-gate-page"),
    };
  });

  const file = `${OUT}/toc-${vp.label}.png`;
  await page.screenshot({ path: file, fullPage: false });

  report.push({ viewport: vp, file, layout });
  console.log(`captured ${vp.label}px → ${file}`);
}

writeFileSync(`${OUT}/report.json`, JSON.stringify(report, null, 2));
console.log(`\nwrote ${OUT}/report.json`);

await browser.close();
