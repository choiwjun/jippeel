import { writeFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";
import { test } from "./quality-scoped-coverage";

// Component fixture uses real stores/query client. No editor/save queue is mounted:
// API interception is context-wide (including fetch keepalive), with no backend.
for (const scenario of [
  {
    name: "empty",
    paragraphs: 0,
    score: 65,
    history: 2,
    external: true,
    riskScore: 7,
  },
  {
    name: "nonempty",
    paragraphs: 1,
    score: 100,
    history: 0,
    external: false,
    riskScore: undefined,
  },
  {
    name: "external-without-score",
    paragraphs: 1,
    score: 50,
    history: 2,
    external: true,
    riskScore: undefined,
  },
]) {
  test(`QualityDialog ${scenario.name} preserves numeric records and explains reference signals`, async ({
    page,
  }, testInfo) => {
    let requests: string[] = [];
    let unexpected: string[] = [];
    await page.context().route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== "http://127.0.0.1:15229") {
        unexpected = [...unexpected, url.href];
        return route.abort();
      }
      if (!url.pathname.startsWith("/api/")) return route.continue();
      requests = [...requests, url.pathname + url.search];
      if (
        route.request().method() === "GET" &&
        url.pathname === "/api/v1/chapters/10/quality"
      ) {
        return route.fulfill({
          json: {
            chapter_id: 10,
            score: scenario.score,
            recorded: true,
            metrics: {
              chars_novelpia: scenario.paragraphs * 4,
              dialogue_ratio: 0.25,
              avg_para_chars: 4,
              ending_repeat_per_1k: 0,
              connector_per_1k: 0,
              para_opener_variety: 1,
              para_count: scenario.paragraphs,
              hook_present: false,
              hook_score_applicable: true,
              episode_purpose: "serial",
              ...(scenario.external
                ? {
                    v2: {
                      risk_band: "synthetic",
                      risk_score: scenario.riskScore,
                    },
                  }
                : {}),
            },
            suggestions: ["합성 제안"],
            suggested_preset_names: ["합성 프리셋"],
          },
        });
      }
      if (
        route.request().method() === "GET" &&
        url.pathname === "/api/v1/chapters/10/quality/history"
      ) {
        return route.fulfill({
          json: scenario.history
            ? [
                {
                  id: 2,
                  chapter_id: 10,
                  score: 65,
                  created_at: "2026-09-12T00:00:00Z",
                },
                {
                  id: 1,
                  chapter_id: 10,
                  score: 50,
                  created_at: "2026-09-11T00:00:00Z",
                },
              ]
            : [],
        });
      }
      if (
        url.pathname === "/api/v1/ai/presets" &&
        route.request().method() === "GET"
      ) {
        if (scenario.name === "nonempty")
          return route.fulfill({
            status: 500,
            json: { detail: "synthetic preset failure" },
          });
        return route.fulfill({
          json:
            scenario.name === "empty" ? [{ id: 1, name: "합성 프리셋" }] : [],
        });
      }
      unexpected = [
        ...unexpected,
        route.request().method() + " " + url.pathname,
      ];
      return route.fulfill({
        status: 500,
        json: { detail: "unexpected B03 fixture API" },
      });
    });
    await page.goto("/e2e/quality-fixture.html");
    await page.getByRole("button").click();
    await expect(
      page.getByRole("heading", { name: "문체 신호 참고 점수", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "문체 신호 참고 점수", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("progressbar", { name: "문체 신호 참고 점수" }),
    ).toHaveAttribute("aria-valuenow", String(scenario.score));
    await expect(
      page.getByRole("dialog", { name: "문체 신호 참고 점수", exact: true }),
    ).toBeVisible();
    const warning = page.getByText(
      "빈 원고 — 점수를 품질 판단에 사용할 수 없습니다",
      { exact: true },
    );
    if (scenario.paragraphs === 0) await expect(warning).toBeVisible();
    else await expect(warning).toHaveCount(0);
    await expect(
      page.getByText(/종합 문학 품질 점수가 아닙니다/),
    ).toBeVisible();
    await expect(page.getByText(/Unicode 문자\/숫자\(L\/N\)/)).toBeVisible();
    await expect(
      page.getByText(/목적·규칙에 의존하는 참고 기록/),
    ).toBeVisible();
    await expect(
      page.getByText(
        /같은 본문도 현재 분석 값과 과거 저장 점수가 다를 수 있습니다/,
      ),
    ).toBeVisible();
    const external = page.getByText(/외부 essay 참고치\(내장 점수와 별개\)/);
    if (scenario.external) await expect(external).toBeVisible();
    else await expect(external).toHaveCount(0);
    expect(requests).toContain(
      "/api/v1/chapters/10/quality?episode_purpose=serial",
    );
    expect(requests.some((url) => url.includes("record=false"))).toBe(false);
    expect(unexpected).toEqual([]);
    const axe = await new AxeBuilder({ page }).analyze();
    const axeFile = testInfo.outputPath("quality-axe.json");
    await writeFile(axeFile, JSON.stringify(axe, null, 2));
    await testInfo.attach("quality-axe", {
      path: axeFile,
      contentType: "application/json",
    });
    expect(
      axe.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical",
      ),
    ).toEqual([]);
    await page
      .getByRole("button", { name: "합성 프리셋", exact: true })
      .click();
    const notice =
      scenario.name === "empty"
        ? /선택했습니다/
        : scenario.name === "nonempty"
          ? /프리셋 조회 실패/
          : /찾을 수 없습니다/;
    await expect(page.getByText(notice)).toBeVisible();
    expect(unexpected).toEqual([]);
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("heading", { name: "문체 신호 참고 점수", exact: true }),
    ).toHaveCount(0);
  });
}

for (const close of ["escape", "backdrop"]) {
  test(`Dialog omitted optional name preserves ${close} close`, async ({
    page,
  }) => {
    await page.context().route("**/api/**", (route) => route.abort());
    await page.goto("/e2e/quality-fixture.html?bare=1");
    await expect(page.getByRole("dialog")).not.toHaveAttribute("aria-label");
    await expect(page.getByText("optional name omitted")).toBeVisible();
    await page.keyboard.press("a");
    await expect(page.getByRole("dialog")).toBeVisible();
    if (close === "escape") await page.keyboard.press("Escape");
    else await page.mouse.click(5, 5);
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
}
