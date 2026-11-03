import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e/operations",
  timeout: 45000,
  fullyParallel: false,
  workers: 1,
  reporter: [
    ["list"],
    ["json", { outputFile: ".cache/operations/e2e-results.json" }],
  ],
  outputDir: ".cache/operations/playwright",
  use: {
    baseURL: process.env.DASHBOARD_URL ?? "http://127.0.0.1:4317",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
