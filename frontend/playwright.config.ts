import { defineConfig, devices } from "@playwright/test";

const WEB_URL = process.env.WEB_URL || "http://127.0.0.1:3100";
const API_URL = process.env.E2E_API_URL || "http://127.0.0.1:8010";
const TEST_DATABASE = "sqlite:///./frontend/.e2e-acoustic.db";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["html", { outputFolder: "playwright-report", open: "never" }], ["list"]],
  use: {
    baseURL: WEB_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    locale: "es-ES",
    acceptDownloads: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: /mobile\.spec\.ts/,
    },
    {
      name: "mobile-chromium",
      testMatch: /mobile\.spec\.ts/,
      use: {
        ...devices["iPhone 13"],
        browserName: "chromium",
        viewport: { width: 375, height: 812 },
      },
    },
  ],
  webServer: [
    {
      command: "python3 frontend/e2e/setup_paid_license.py && uvicorn frontend.e2e.api_server:app --host 127.0.0.1 --port 8010 --workers 2",
      url: `${API_URL}/api/v1/health`,
      reuseExistingServer: false,
      cwd: "..",
      timeout: 45_000,
      env: {
        ...process.env,
        DATABASE_URL: TEST_DATABASE,
        ACOUSTIC_CORS_ORIGINS: '["http://127.0.0.1:3100"]',
      },
    },
    {
      command: `npm run build && python3 e2e/web_server.py --host 127.0.0.1 --port 3100 --directory .next-e2e --api-url ${API_URL}`,
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { ...process.env, NEXT_DIST_DIR: ".next-e2e" },
    },
  ],
});
