import { defineConfig, devices } from '@playwright/test';
import { fixtureServer } from './e2e/fixture-server';
const fixture = fixtureServer(15484);

export default defineConfig({
  testDir: './e2e', testMatch: /story-map\.spec\.ts/,
  timeout: 90_000, expect: { timeout: 10_000 }, workers: 1, retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:15484', viewport: { width: 1600, height: 1000 },
    trace: 'retain-on-failure', screenshot: 'only-on-failure', locale: 'ko-KR' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1600, height: 1000 } } }],
  ...fixture,
  webServer: { ...fixture.webServer, timeout: 120_000,
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 15484 --strictPort --config vite.story-map.config.ts' },
});
