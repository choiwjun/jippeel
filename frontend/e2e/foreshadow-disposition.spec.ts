import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * D03-5 복선 이관 구분(disposition) — fixture-only UI 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

type Disposition = "resolved" | "intentional_unresolved" | "side_story";
type Foreshadow = {
  id: number;
  project_id: number;
  title: string;
  content: string | null;
  keywords: string[] | null;
  status: "설치" | "회수" | "보류";
  disposition: Disposition | null;
  audience_knows: boolean;
  planted_chapter_id: number | null;
  resolved_chapter_id: number | null;
  created_at: string;
  updated_at: string;
};

const NOW = "2026-09-13T00:00:00.000Z";
const PROJECT_ID = 1;

/** catch-all로 받은 미모킹 요청 — afterEach에서 비어 있음을 단정한다. */
let unhandled: string[] = [];

function foreshadow(
  id: number,
  title: string,
  status: Foreshadow["status"],
  disposition: Disposition | null = null,
): Foreshadow {
  return {
    id,
    project_id: PROJECT_ID,
    title,
    content: `${title} 내용`,
    keywords: [],
    status,
    disposition,
    audience_knows: false,
    planted_chapter_id: null,
    resolved_chapter_id: null,
    created_at: NOW,
    updated_at: NOW,
  };
}

type Fixture = {
  rows: Map<number, Foreshadow>;
  patches: Array<{ id: number; body: Record<string, unknown> }>;
  posts: Array<Record<string, unknown>>;
};

/** fixture 서버 — PATCH /foreshadows/{id}에 백엔드 동일 불변조건(설치+disposition → 422). */
async function setupFixture(page: Page, seed: Foreshadow[]): Promise<Fixture> {
  const rows = new Map<number, Foreshadow>(seed.map((f) => [f.id, f]));
  const fixture: Fixture = { rows, patches: [], posts: [] };
  let nextId = Math.max(0, ...seed.map((f) => f.id)) + 1;

  await page.context().route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    const body = () => JSON.parse(route.request().postData() ?? "{}");

    if (method === "GET" && path === `/projects/${PROJECT_ID}/foreshadows`)
      return json(200, [...rows.values()]);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/chapters`)
      return json(200, []);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/foreshadows/reminder`)
      return json(200, { window: 5, latest_chapter: null, items: [] });
    if (method === "POST" && path === `/projects/${PROJECT_ID}/foreshadows`) {
      const req = body();
      fixture.posts.push(req);
      // G-045 — 백엔드 계약: 요청 audience_knows를 저장·반환한다
      const f: Foreshadow = {
        id: nextId++,
        project_id: PROJECT_ID,
        title: String(req.title ?? ""),
        content: (req.content as string | null) ?? null,
        keywords: (req.keywords as string[] | null) ?? null,
        status: (req.status as Foreshadow["status"]) ?? "설치",
        disposition: (req.disposition as Disposition | null) ?? null,
        audience_knows: req.audience_knows === true,
        planted_chapter_id: (req.planted_chapter_id as number | null) ?? null,
        resolved_chapter_id: (req.resolved_chapter_id as number | null) ?? null,
        created_at: NOW,
        updated_at: NOW,
      };
      rows.set(f.id, f);
      return json(201, f);
    }

    const patchMatch = path.match(/^\/foreshadows\/(\d+)$/);
    if (patchMatch) {
      const f = rows.get(Number(patchMatch[1]));
      if (!f) return json(404, { detail: "not found" });
      if (method === "PATCH") {
        const req = body();
        fixture.patches.push({ id: f.id, body: req });
        // 사전 검증(백엔드 Literal/VALID_*와 동일)
        if (req.status !== undefined && !["설치", "회수", "보류"].includes(req.status))
          return json(422, { detail: "status는 설치|회수|보류 중 하나여야 합니다" });
        if (
          "disposition" in req &&
          req.disposition !== null &&
          !["resolved", "intentional_unresolved", "side_story"].includes(req.disposition)
        )
          return json(422, {
            detail:
              "disposition은 resolved|intentional_unresolved|side_story 중 하나여야 합니다",
          });
        // 백엔드와 동일한 불변조건 — 패치 결과가 설치+disposition이면 422
        const nextStatus = (req.status ?? f.status) as string;
        const nextDisp =
          "disposition" in req ? (req.disposition as Disposition | null) : f.disposition;
        if (nextStatus === "설치" && nextDisp !== null)
          return json(422, {
            detail: "설치 상태의 복선에는 disposition을 지정할 수 없습니다",
          });
        // exclude_unset과 동일 — 제공된 필드만 병합
        for (const key of [
          "title",
          "content",
          "keywords",
          "status",
          "disposition",
          "audience_knows",
          "planted_chapter_id",
          "resolved_chapter_id",
        ] as const)
          if (key in req) (f as unknown as Record<string, unknown>)[key] = req[key];
        f.updated_at = NOW;
        return json(200, f);
      }
      if (method === "DELETE") {
        rows.delete(f.id);
        return json(204, null);
      }
      return json(405, { detail: "method not allowed" });
    }

    if (method === "GET" && path === `/projects/${PROJECT_ID}`)
      return json(200, { id: PROJECT_ID, title: "이관 작품" });

    unhandled.push(`${method} ${path}`);
    return json(404, { detail: `unhandled fixture route: ${method} ${path}` });
  });
  return fixture;
}

async function openPage(page: Page) {
  await page.goto(`/projects/${PROJECT_ID}/foreshadows`);
  await expect(page.getByRole("heading", { name: "복선 관리" })).toBeVisible();
}

test.describe("D03-5 복선 이관 구분", () => {
  test.beforeEach(() => {
    unhandled = [];
  });
  test.afterEach(() => {
    expect(unhandled, `unhandled fixture requests: ${unhandled.join(", ")}`).toEqual([]);
  });

  test("disposition 배지를 표시하고 미분류는 배지 없음", async ({ page }) => {
    await setupFixture(page, [
      foreshadow(1, "해결된 복선", "회수", "resolved"),
      foreshadow(2, "외전 복선", "보류", "side_story"),
      foreshadow(3, "유예된 복선", "보류", "intentional_unresolved"),
      foreshadow(4, "미분류 복선", "회수"),
    ]);
    await openPage(page);
    // 제목 행(div:has(> h2))의 rounded-full span만 — 키워드 배지와 구분된다
    const badge = (title: string) =>
      page
        .locator("article", { hasText: title })
        .locator("div:has(> h2) span.rounded-full");
    await expect(badge("해결된 복선")).toHaveText("해결");
    await expect(badge("외전 복선")).toHaveText("외전 이관");
    await expect(badge("유예된 복선")).toHaveText("의도적 미해결");
    await expect(badge("미분류 복선")).toHaveCount(0);
  });

  test("status 필터 버튼 회귀 — 기존 동작 유지", async ({ page }) => {
    await setupFixture(page, [
      foreshadow(1, "열린 복선", "설치"),
      foreshadow(2, "닫힌 복선", "회수", "resolved"),
      foreshadow(3, "유예 복선", "보류"),
    ]);
    await openPage(page);
    await page.getByRole("button", { name: "회수", exact: true }).click();
    await expect(page.locator("article")).toHaveCount(1);
    await expect(page.locator("article", { hasText: "닫힌 복선" })).toBeVisible();
    await page.getByRole("button", { name: "설치", exact: true }).click();
    await expect(page.locator("article")).toHaveCount(1);
    await expect(page.locator("article", { hasText: "열린 복선" })).toBeVisible();
    await page.getByRole("button", { name: "전체" }).click();
    await expect(page.locator("article")).toHaveCount(3);
  });

  test("disposition select가 PATCH 본문 계약을 지킨다", async ({ page }) => {
    const fx = await setupFixture(page, [foreshadow(1, "닫힌 복선", "보류")]);
    await openPage(page);
    const select = page.getByRole("combobox", { name: "복선 처분: 닫힌 복선" });
    await expect(select).toBeEnabled();
    await select.selectOption("side_story");
    await expect.poll(() => fx.patches).toHaveLength(1);
    expect(fx.patches[0]).toEqual({ id: 1, body: { disposition: "side_story" } });

    // 미분류로 되돌리면 명시적 null
    await select.selectOption("");
    await expect.poll(() => fx.patches.length).toBe(2);
    expect(fx.patches[1]).toEqual({ id: 1, body: { disposition: null } });
  });

  test("설치 상태 행은 disposition select가 disabled", async ({ page }) => {
    await setupFixture(page, [foreshadow(1, "열린 복선", "설치")]);
    await openPage(page);
    await expect(
      page.getByRole("combobox", { name: "복선 처분: 열린 복선" }),
    ).toBeDisabled();
  });

  test("disposition 있는 행을 설치로 변경하면 단일 PATCH로 해제 포함", async ({ page }) => {
    const fx = await setupFixture(page, [
      foreshadow(1, "재오픈 복선", "회수", "resolved"),
    ]);
    await openPage(page);
    await page
      .getByRole("combobox", { name: "복선 상태 변경: 재오픈 복선" })
      .selectOption("설치");
    await expect.poll(() => fx.patches).toHaveLength(1);
    expect(fx.patches[0]).toEqual({
      id: 1,
      body: { status: "설치", disposition: null },
    });
  });

  test("disposition 없는 행을 설치로 변경하면 disposition 키를 보내지 않는다", async ({ page }) => {
    const fx = await setupFixture(page, [foreshadow(1, "유예 복선", "보류")]);
    await openPage(page);
    await page
      .getByRole("combobox", { name: "복선 상태 변경: 유예 복선" })
      .selectOption("설치");
    await expect.poll(() => fx.patches).toHaveLength(1);
    expect(fx.patches[0]).toEqual({ id: 1, body: { status: "설치" } });
  });

  test("G-045 — 생성 폼의 독자 인지가 POST에 저장된다", async ({ page }) => {
    const fx = await setupFixture(page, [foreshadow(1, "기존 복선", "설치")]);
    await openPage(page);

    await page.getByLabel("복선 제목").fill("독자만 아는 비밀");
    await page.getByLabel("독자가 이미 알게 된 사실").check();
    await page.getByRole("button", { name: "+ 복선 등록" }).click();

    await expect.poll(() => fx.posts).toHaveLength(1);
    expect(fx.posts[0].audience_knows).toBe(true);
    // 새 행의 독자 인지 체크박스가 저장값을 반영한다
    await expect(
      page.getByLabel("독자 인지: 독자만 아는 비밀")
    ).toBeChecked();
    // 폼은 성공 후 초기화된다
    await expect(page.getByLabel("독자가 이미 알게 된 사실")).not.toBeChecked();
  });

  test("접근성 — axe serious/critical 위반 0", async ({ page }) => {
    await setupFixture(page, [
      foreshadow(1, "해결된 복선", "회수", "resolved"),
      foreshadow(2, "열린 복선", "설치"),
    ]);
    await openPage(page);
    await expect(page.locator("article")).toHaveCount(2);
    const results = await new AxeBuilder({ page }).analyze();
    const serious = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(serious).toEqual([]);
  });
});
