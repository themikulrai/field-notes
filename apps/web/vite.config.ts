import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `test` is read by vitest's vite-config loader. Plain `vite build` ignores
// unknown keys but tsc rejects them — cast to UserConfig to silence.
const config = {
  plugins: [react()],
  server: { port: 5173 },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    css: false,
    // `e2e/` is for Playwright, not Vitest. Exclude or Vitest will try to
    // resolve `@playwright/test` and fail.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "dist", "e2e/**"],
  },
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default defineConfig(config as any);
