import { writeFile } from "node:fs/promises";
import { test as base } from "@playwright/test";

const changedSources = new Set([
  "/src/App.tsx",
  "/src/pages/MemoryPage.tsx",
  "/src/lib/manuscriptDrafts.ts",
  "/src/lib/queryClient.ts",
]);

// Optional test-only collection. Artifacts follow Playwright's caller-owned output directory.
export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const enabled = process.env.MEMORY_SCOPED_COVERAGE === "1";
    if (enabled) await page.coverage.startJSCoverage({ resetOnNavigation: false });
    await use(page);
    if (enabled && !page.isClosed()) {
      const entries = (await page.coverage.stopJSCoverage()).filter((entry) =>
        entry.url && changedSources.has(new URL(entry.url).pathname),
      );
      const file = testInfo.outputPath("memory-scoped-v8.json");
      await writeFile(file, JSON.stringify(entries));
      await testInfo.attach("memory-scoped-v8", {
        path: file,
        contentType: "application/json",
      });
    }
  },
});
