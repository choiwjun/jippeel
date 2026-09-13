import { writeFile } from "node:fs/promises";
import { test as base } from "@playwright/test";
import { writeRawCoverage } from "./coverage-test";

// Independent B03 collector: retain all runtime entries/maps for later source-hash merge.
export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const scoped = process.env.QUALITY_SCOPED_COVERAGE === "1";
    const full = process.env.PW_COVERAGE === "1";
    if (scoped || full)
      await page.coverage.startJSCoverage({ resetOnNavigation: false });
    await use(page);
    if ((scoped || full) && !page.isClosed()) {
      const entries = await page.coverage.stopJSCoverage();
      if (full) writeRawCoverage(entries, testInfo);
      if (scoped) {
        const filtered = entries.filter(
          (entry) =>
            entry.url &&
            [
              "/src/components/editor/QualityDialog.tsx",
              "/src/components/ui/dialog.tsx",
            ].includes(new URL(entry.url).pathname),
        );
        const file = testInfo.outputPath("quality-scoped-v8.json");
        await writeFile(file, JSON.stringify(filtered));
        await testInfo.attach("quality-scoped-v8", {
          path: file,
          contentType: "application/json",
        });
      }
    }
  },
});
