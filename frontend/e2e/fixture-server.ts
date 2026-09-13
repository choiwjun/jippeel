import { mkdtempSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import path from "node:path";

export function fixtureServer(port: number) {
  const root = mkdtempSync(path.join(tmpdir(), "jippeel-fixture-tripwire-"));
  const violations = path.join(root, "violations.jsonl");
  return {
    metadata: { fixtureApiViolations: violations },
    globalTeardown: fileURLToPath(new URL("./fixture-server-teardown.ts", import.meta.url)),
    webServer: {
      command: `npx vite --host 127.0.0.1 --port ${port} --strictPort --config vite.fixture.config.ts`,
      url: `http://127.0.0.1:${port}`,
      env: { JIPPEEL_FIXTURE_API_VIOLATIONS: violations },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  };
}
