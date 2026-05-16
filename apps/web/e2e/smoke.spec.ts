// Playwright smoke test.
//
// Spins up the API as a subprocess against in-memory SQLite, runs `tools/seed`
// to populate the prototype's mock data, then opens the built Vite preview and
// confirms the four project tabs render, a cell can be expanded, the locked
// chip is visible, and the browser console stays clean.
//
// Status on the iris lab login node where this was authored: SKIPPED. The node
// has no chromium binary and the sandbox doesn't permit `playwright install
// chromium` to fetch the ~150MB headless browser. The spec is wired up so that
// in any CI / dev environment with Chromium available (e.g. GitHub Actions
// with the official `setup-playwright` action), removing the `.skip` below
// runs the full smoke loop. The Vitest suite already covers the React
// component behaviour; this spec is the cross-cutting "does the whole stack
// actually serve a page" check.
//
// To enable locally:
//   npm i -D @playwright/test
//   npx playwright install chromium
//   # then drop the .skip below

import { test, expect } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";

let api: ChildProcess | null = null;
let web: ChildProcess | null = null;

async function waitForUrl(url: string, timeoutMs = 15000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {
      /* connection refused while booting */
    }
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

test.beforeAll(async () => {
  const env = {
    ...process.env,
    FIELD_NOTES_KEY: "changeme",
    DATABASE_URL: "sqlite+aiosqlite:///:memory:",
    TEST_DATABASE_URL: "sqlite+aiosqlite:///:memory:",
  };
  // 1) API subprocess (uvicorn) — sqlite in-memory so we don't need docker.
  api = spawn(
    "uv",
    ["run", "--package", "field-notes-api", "uvicorn", "field_notes_api.main:app", "--port", "8765"],
    { cwd: "../..", env, stdio: "inherit" },
  );
  await waitForUrl("http://localhost:8765/healthz");

  // 2) Seed the API with the prototype's mock data.
  const seed = spawn("uv", ["run", "python", "-m", "tools.seed"], {
    cwd: "../..",
    env: { ...env, FIELD_NOTES_API_URL: "http://localhost:8765" },
    stdio: "inherit",
  });
  await new Promise<void>((resolve, reject) =>
    seed.on("exit", (code) => (code === 0 ? resolve() : reject(new Error(`seed exit ${code}`)))),
  );

  // 3) Vite preview against the build (npm run build must have been run already).
  web = spawn("npm", ["run", "preview", "--", "--port", "5174"], {
    cwd: "..",
    env: { ...env, VITE_API_URL: "http://localhost:8765" },
    stdio: "inherit",
  });
  await waitForUrl("http://localhost:5174");
});

test.afterAll(async () => {
  api?.kill("SIGTERM");
  web?.kill("SIGTERM");
});

test.skip("smoke: four projects, a deep-toggle, and a LOCKED chip", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  // Inject the API key into localStorage so the KeyGate doesn't block us.
  await page.addInitScript(() => {
    localStorage.setItem("field-notes-key", "changeme");
  });
  await page.goto("http://localhost:5174/");

  // Four project tabs visible (seed creates exactly four projects).
  const tabs = page.locator("[data-tab='project']");
  await expect(tabs).toHaveCount(4);

  // A LOCKED chip exists somewhere (orca · manipulation has c-006 locked).
  const lockedChip = page.getByText(/LOCKED/i).first();
  await expect(lockedChip).toBeVisible();

  // Click the first cell's deep-toggle (button has a stable label "deep").
  const deepToggle = page.getByRole("button", { name: /deep/i }).first();
  await expect(deepToggle).toBeVisible();
  await deepToggle.click();

  // No console errors after exercising the page.
  expect(errors, errors.join("\n")).toHaveLength(0);
});
