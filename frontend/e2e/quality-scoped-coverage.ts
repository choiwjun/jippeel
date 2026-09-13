import { writeFile } from "node:fs/promises";
import { test as base } from "@playwright/test";

// Independent B03 collector: retain all runtime entries/maps for later source-hash merge.
export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const enabled = process.env.QUALITY_SCOPED_COVERAGE === "1";
    if (enabled)
      await page.coverage.startJSCoverage({ resetOnNavigation: false });
    await use(page);
    if (enabled && !page.isClosed()) {
      const entries = (await page.coverage.stopJSCoverage()).filter(
        (entry) =>
          entry.url &&
          [
            "/src/components/editor/QualityDialog.tsx",
            "/src/components/ui/dialog.tsx",
          ].includes(new URL(entry.url).pathname),
      );
      const file = testInfo.outputPath("quality-scoped-v8.json");
      await writeFile(file, JSON.stringify(entries));
      await testInfo.attach("quality-scoped-v8", {
        path: file,
        contentType: "application/json",
      });
    }
  },
});
