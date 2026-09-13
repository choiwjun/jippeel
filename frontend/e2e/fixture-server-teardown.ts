import { existsSync, readFileSync } from "node:fs";
import type { FullConfig } from "@playwright/test";

export default function checkFixtureApiIsolation(config: FullConfig) {
  const file = config.metadata.fixtureApiViolations as string;
  const violations = existsSync(file) ? readFileSync(file, "utf8") : "";
  console.log(`Fixture API tripwire: ${file}; ${violations ? "FAILED" : "no escapes"}`);
  if (violations) throw new Error(`Unmocked API requests reached fixture Vite server:\n${violations}`);
}
