import { defineConfig, devices } from "@playwright/test";

const WEB_URL = process.env.WEB_URL || "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { outputFolder: "playwright-report" }]],
  use: {
    baseURL: WEB_URL,
    trace: "on-first-retry",
    extraHTTPHeaders: { "X-API-Key": "free_tier" },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        locale: "es-ES",
      },
    },
  ],
  webServer: [
    {
      command: `uvicorn api.main:app --host 0.0.0.0 --port 8000`,
      port: 8000,
      reuseExistingServer: !process.env.CI,
      cwd: "..",
      timeout: 30000,
    },
    {
      command: "npm run dev",
      port: 3000,
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
    },
  ],
});
