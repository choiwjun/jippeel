import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * D03-7 결말 변경 영향 — fixture-only UI 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

const NOW = "2026-09-13T00:00:00.000Z";
const PROJECT_ID = 1;

type Project = {
  id: number;
  title: string;
  genre: string | null;
  synopsis: string | null;
  platform_note: string | null;
  style_profile: string | null;
  serial_state: string;
  serial_completed_at: string | null;
  ending_intent: string | null;
  ending_locked: boolean;
  ending_updated_at: string | null;
  created_at: string;
  updated_at: string;
};

const IMPACT = {
  ending_intent: "주인공은 고향으로 돌아간다",
  ending_locked: false,
  ending_updated_at: NOW,
  open_foreshadows: [{ id: 3, title: "검은 검의 주인" }],
  stale_goal_chapters: [{ chapter_id: 5, title: "7화", goal_version: 2 }],
  finale_chapters: [
    { chapter_id: 9, title: "최종화", has_ending_intent: true },
    { chapter_id: 10, title: "진 최종화", has_ending_intent: false },
  ],
};

let unhandled: string[] = [];

function project(): Project {
  return {
    id: PROJECT_ID,
    title: "결말 작품",
    genre: null,
    synopsis: null,
    platform_note: null,
    style_profile: null,
    serial_state: "ongoing",
    serial_completed_at: null,
    ending_intent: null,
    ending_locked: false,
    ending_updated_at: null,
    created_at: NOW,
    updated_at: NOW,
  };
}

type Fixture = {
  project: Project;
  patches: Array<Record<string, unknown>>;
};

/** fixture 서버 — PATCH /projects/{id}에 백엔드 동일 잠금 불변조건 적용. */
async function setupFixture(page: Page): Promise<Fixture> {
  const fixture: Fixture = { project: project(), patches: [] };

  await page.context().route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    const body = () => JSON.parse(route.request().postData() ?? "{}");
    const p = fixture.project;

    if (method === "GET" && path === `/projects/${PROJECT_ID}`) return json(200, p);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/volume-notes`)
      return json(200, []);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/ending-impact`)
      return json(200, { ...IMPACT, ending_intent: p.ending_intent, ending_locked: p.ending_locked, ending_updated_at: p.ending_updated_at });

    if (method === "PATCH" && path === `/projects/${PROJECT_ID}`) {
      const req = body();
      fixture.patches.push(req);
      // 허용 필드만(백엔드 ProjectUpdate와 동일 사전)
      const allowed = new Set([
        "title", "genre", "synopsis", "platform_note", "style_profile",
        "serial_state", "ending_intent", "ending_locked",
      ]);
      const unknown = Object.keys(req).filter((k) => !allowed.has(k));
      if (unknown.length) return json(422, { detail: `extra fields: ${unknown}` });
      if ("serial_state" in req && req.serial_state === null)
        return json(422, { detail: "serial_state must be one of: ongoing, hiatus, completed" });
      if ("serial_state" in req && !["ongoing", "hiatus", "completed"].includes(req.serial_state as string))
        return json(422, { detail: "invalid serial_state" });
      // 백엔드 불변조건 — 잠긴 결말의 실제 변경은 같은 요청의 해제 없이 409
      const endingChanging =
        "ending_intent" in req && req.ending_intent !== p.ending_intent;
      if (endingChanging && p.ending_locked && req.ending_locked !== false)
        return json(409, { detail: "결말이 잠겨 있습니다" });
      for (const [k, v] of Object.entries(req)) {
        (p as Record<string, unknown>)[k] = v;
      }
      if ("serial_state" in req) {
        p.serial_completed_at = req.serial_state === "completed" ? NOW : null;
      }
      if (endingChanging) p.ending_updated_at = NOW;
      return json(200, p);
    }
    unhandled.push(`${method} ${path}`);
    return json(500, { detail: `unhandled ${method} ${path}` });
  });
  return fixture;
}

test.beforeEach(() => {
  unhandled = [];
});

test.afterEach(() => {
  expect(unhandled, `unhandled API requests: ${unhandled}`).toEqual([]);
});

test.describe("D03-7 결말 변경 영향", () => {
  test("결말 후보 저장 — PATCH 본문과 변경 시각 표시", async ({ page }) => {
    const fixture = await setupFixture(page);
    await page.goto(`/projects/${PROJECT_ID}/plan`);

    await page.getByRole("textbox", { name: "결말 후보" }).fill("주인공은 고향으로");
    await page.getByRole("button", { name: "저장" }).click();

    await expect.poll(() => fixture.patches).toHaveLength(1);
    expect(fixture.patches).toEqual([
      { ending_intent: "주인공은 고향으로" },
    ]);
    await expect(page.getByText("변경 2026")).toBeVisible();
  });

  test("빈 결말은 null로 전송 — 지우기 계약", async ({ page }) => {
    const fixture = await setupFixture(page);
    fixture.project.ending_intent = "결말 A";
    await page.goto(`/projects/${PROJECT_ID}/plan`);

    const box = page.getByRole("textbox", { name: "결말 후보" });
    await expect(box).toHaveValue("결말 A");
    await box.fill("   ");
    await page.getByRole("button", { name: "저장" }).click();

    await expect.poll(() => fixture.patches).toHaveLength(1);
    expect(fixture.patches).toEqual([{ ending_intent: null }]);
  });

  test("잠금 토글 — PATCH ending_locked, textarea disabled + 잠김 배지", async ({ page }) => {
    const fixture = await setupFixture(page);
    await page.goto(`/projects/${PROJECT_ID}/plan`);

    await page.getByRole("button", { name: "잠금" }).click();
    await expect.poll(() => fixture.patches).toHaveLength(1);
    expect(fixture.patches).toEqual([{ ending_locked: true }]);
    await expect(page.getByText("잠김")).toBeVisible();
    await expect(page.getByRole("textbox", { name: "결말 후보" })).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "잠금 해제" }),
    ).toBeVisible();
  });

  test("잠긴 상태 저장 — 단일 PATCH로 해제+저장", async ({ page }) => {
    const fixture = await setupFixture(page);
    fixture.project.ending_intent = "결말 A";
    fixture.project.ending_locked = true;
    await page.goto(`/projects/${PROJECT_ID}/plan`);

    await expect(page.getByRole("textbox", { name: "결말 후보" })).toBeDisabled();
    await page.getByRole("button", { name: "저장" }).click();

    await expect.poll(() => fixture.patches).toHaveLength(1);
    expect(fixture.patches).toEqual([
      { ending_locked: false, ending_intent: "결말 A" },
    ]);
    await expect(page.getByRole("textbox", { name: "결말 후보" })).toBeEnabled();
  });

  test("변경 영향 — 미해결 복선·오래된 목표·최종화 회차 표시", async ({ page }) => {
    await setupFixture(page);
    await page.goto(`/projects/${PROJECT_ID}/plan`);

    await expect(page.getByText("미해결 복선:")).toBeVisible();
    await expect(page.getByText("검은 검의 주인")).toBeVisible();
    await expect(page.getByText("결말 변경 전 목표:")).toBeVisible();
    await expect(page.getByText("7화(목표 v2)")).toBeVisible();
    await expect(page.getByText("최종화 회차:")).toBeVisible();
    await expect(page.getByText("진 최종화(결말 의도 없음)")).toBeVisible();
  });

  test("a11y — serious/critical 위반 없음", async ({ page }) => {
    await setupFixture(page);
    await page.goto(`/projects/${PROJECT_ID}/plan`);
    await expect(page.getByRole("textbox", { name: "결말 후보" })).toBeVisible();

    const results = await new AxeBuilder({ page }).analyze();
    const violations = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(violations).toEqual([]);
  });
});
