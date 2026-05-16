// Playwright config.
//
// Loaded only when @playwright/test is installed. The smoke spec is `.skip`-d
// on environments without a chromium binary (e.g. the iris lab login node).
//
// To run locally:
//   npm install --save-dev @playwright/test
//   npx playwright install chromium
//   npm run build
//   npm run e2e
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  use: {
    baseURL: "http://localhost:5174",
    trace: "on-first-retry",
  },
});
