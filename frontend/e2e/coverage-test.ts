import { expect, test as base, type TestInfo } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * V01 — opt-in V8 coverage 수집.
 * PW_COVERAGE=1 일 때만 테스트별 누적 V8 function coverage를
 * coverage-raw/<worker>-<testid>.json으로 저장한다. 미설정 시 no-op.
 * 기존 scoped 래퍼(memory/quality)도 writeRawCoverage로 전체 엔트리를 공유 저장한다.
 */
export const COVERAGE_ENABLED = process.env.PW_COVERAGE === "1";
const OUT_DIR = path.resolve(process.env.PW_COVERAGE_DIR || "coverage-raw");

export function writeRawCoverage(entries: unknown[], testInfo: TestInfo): void {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const name = `${testInfo.workerIndex}-${testInfo.retry}-${testInfo.testId.replace(/\W+/g, "_")}.json`;
  fs.writeFileSync(path.join(OUT_DIR, name), JSON.stringify(entries));
}

export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    if (COVERAGE_ENABLED && page.coverage) {
      await page.coverage.startJSCoverage({ resetOnNavigation: false });
    }
    await use(page);
    // 테스트 본문이 page.close()한 경우 stop은 불가 — 그 테스트는 coverage 없음
    if (COVERAGE_ENABLED && page.coverage && !page.isClosed()) {
      writeRawCoverage(await page.coverage.stopJSCoverage(), testInfo);
    }
  },
});

export { expect };
