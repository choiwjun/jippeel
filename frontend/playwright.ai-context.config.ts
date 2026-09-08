import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: /ai-context-consistency\.spec\.ts/,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:15212',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 900 },
    locale: 'ko-KR',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: '"../backend/.venv/Scripts/python.exe" "../scripts/ai_context_backend_fixture.py" --backend-port 18112 --provider-port 18113 --hold-server --json-report ../.eval_tmp/ai-context-task-4/backend-fixture.json',
      url: 'http://127.0.0.1:18112/health',
      reuseExistingServer: false,
      timeout: 90_000,
    },
    {
      command: 'npx vite --host 127.0.0.1 --port 15212 --strictPort --config vite.ai-context.config.ts',
      url: 'http://127.0.0.1:15212',
      reuseExistingServer: false,
      timeout: 90_000,
    },
  ],
});
