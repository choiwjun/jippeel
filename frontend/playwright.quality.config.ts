import { defineConfig, devices } from "@playwright/test";
import { fixtureServer } from "./e2e/fixture-server";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /quality-dialog\.spec\.ts/,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:15229",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1440, height: 1000 },
    locale: "ko-KR",
    serviceWorkers: "block",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  ...fixtureServer(15229),
});
