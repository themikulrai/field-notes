// Asserts the table-of-contents stays visible at common laptop widths and
// collapses on mobile. Runs against a dev server you start yourself
// (default http://localhost:5173/, override via TOC_URL).
//
// Quick run:
//   VITE_DEFAULT_KEY=mikulrai npm run dev &
//   npx playwright test e2e/toc-responsive.spec.ts
//
// For ad-hoc screenshots at the same widths, see `npm run shots`.

import { test, expect } from "@playwright/test";

const URL = process.env.TOC_URL || "http://localhost:5173/";

const VISIBLE = [
  { w: 1920, h: 1080 },
  { w: 1440, h: 900 },
  { w: 1366, h: 768 },
  { w: 1280, h: 800 },
  { w: 1024, h: 768 },
];

const HIDDEN = [
  { w: 768, h: 1024 },
  { w: 600, h: 900 },
];

async function waitForApp(page: import("@playwright/test").Page) {
  await page.goto(URL, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".page", { timeout: 10_000 });
  // Settle one frame so sticky layout reports stable rects.
  await page.waitForTimeout(200);
}

for (const vp of VISIBLE) {
  test(`ToC is visible at ${vp.w}x${vp.h}`, async ({ page }) => {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await waitForApp(page);
    const toc = page.locator(".toc");
    await expect(toc).toBeVisible();
    const box = await toc.boundingBox();
    expect(box).not.toBeNull();
    // ToC must sit inside the viewport horizontally (the original bug
    // pushed it off-screen at viewport widths below ~1720px).
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(vp.w);
    // ToC must clear the sticky header — top should be at least the
    // header's height, never overlapping it.
    const headerH = await page.locator(".top").evaluate((el) => el.getBoundingClientRect().height);
    expect(box!.y).toBeGreaterThanOrEqual(headerH - 1);
  });
}

for (const vp of HIDDEN) {
  test(`ToC is hidden (mobile) at ${vp.w}x${vp.h}`, async ({ page }) => {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await waitForApp(page);
    const display = await page
      .locator(".toc")
      .evaluate((el) => getComputedStyle(el).display);
    expect(display).toBe("none");
  });
}
