import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: /manuscript-preservation\.integration\.spec\.ts/,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:15202',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 900 },
    locale: 'ko-KR',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: '..\\backend\\.venv\\Scripts\\python.exe ..\\scripts\\preservation_backend_fixture.py --port 18080 --hold-server --json-report ..\\.eval_tmp\\preservation-task3\\integration-backend-server.json',
      url: 'http://127.0.0.1:18080/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npx vite --host 127.0.0.1 --port 15202 --strictPort --config vite.preservation.integration.config.ts',
      url: 'http://127.0.0.1:15202',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
