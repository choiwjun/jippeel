import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * D03-3 연재 상태(serial_state) — fixture-only UI 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

type SerialState = "ongoing" | "hiatus" | "completed";
type Project = {
  id: number;
  title: string;
  genre: string | null;
  synopsis: string | null;
  platform_note: string | null;
  style_profile: string | null;
  serial_state: SerialState;
  serial_completed_at: string | null;
  created_at: string;
  updated_at: string;
  chapter_count: number;
  total_chars: number;
};

const NOW = "2026-09-13T00:00:00.000Z";
const COMPLETED_AT = "2026-09-13T01:30:00.000Z";

/** catch-all로 받은 미모킹 요청 — afterEach에서 비어 있음을 단정한다. */
let unhandled: string[] = [];

function project(id: number, title: string, serial_state: SerialState = "ongoing"): Project {
  return {
    id,
    title,
    genre: "판타지",
    synopsis: `${title} 시놉시스`,
    platform_note: null,
    style_profile: null,
    serial_state,
    serial_completed_at: serial_state === "completed" ? COMPLETED_AT : null,
    created_at: NOW,
    updated_at: NOW,
    chapter_count: 2,
    total_chars: 1200,
  };
}

type SerialFixture = {
  projects: Map<number, Project>;
  patches: Array<{ id: number; body: Record<string, unknown> }>;
};

/** fixture 서버 — PATCH /projects/{id}에 백엔드 동일 규칙(completed 진입 시각 기록/이탈 시 제거). */
async function setupFixture(page: Page, seed: Project[]): Promise<SerialFixture> {
  const projects = new Map<number, Project>(seed.map((p) => [p.id, p]));
  const fixture: SerialFixture = { projects, patches: [] };

  await page.context().route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    const body = () => JSON.parse(route.request().postData() ?? "{}");

    if (method === "GET" && path === "/projects")
      return json(200, [...projects.values()]);

    const projectMatch = path.match(/^\/projects\/(\d+)$/);
    if (projectMatch) {
      const p = projects.get(Number(projectMatch[1]));
      if (!p) return json(404, { detail: "not found" });
      if (method === "PATCH") {
        const patch = body();
        if ("serial_state" in patch) {
          const next = patch.serial_state;
          if (!["ongoing", "hiatus", "completed"].includes(String(next)))
            return json(422, {
              detail: [
                {
                  type: "literal_error",
                  loc: ["body", "serial_state"],
                  msg: "Input should be 'ongoing', 'hiatus' or 'completed'",
                },
              ],
            });
          p.serial_state = next as SerialState;
          p.serial_completed_at = next === "completed" ? COMPLETED_AT : null;
        }
        fixture.patches.push({ id: p.id, body: patch });
        return json(200, p);
      }
      return json(405, { detail: "method not allowed" });
    }

    const plusMatch = path.match(/^\/projects\/(\d+)\/plus-status$/);
    if (method === "GET" && plusMatch)
      return json(200, {
        chapter_count: projects.get(Number(plusMatch[1]))?.chapter_count ?? 0,
        chapter_count_met: false,
        done_chapter_count: 0,
        done_chapters_3000: 0,
        done_chars_met: false,
        eligible: false,
      });

    unhandled.push(`${method} ${path}`);
    return json(404, { detail: `unhandled fixture route: ${method} ${path}` });
  });
  return fixture;
}

const serialSelect = (page: Page, title: string) =>
  page
    .locator("div.rounded-lg.border", { hasText: title })
    .getByRole("combobox", { name: "연재 상태 변경 (회차 집필 확정과 별개)" });

test.describe("D03-3 연재 상태", () => {
  test.beforeEach(() => {
    unhandled = [];
  });
  test.afterEach(() => {
    expect(unhandled, `unhandled fixture requests: ${unhandled.join(", ")}`).toEqual([]);
  });

  test("기본값 ongoing — '연재 중' 표시", async ({ page }) => {
    await setupFixture(page, [project(1, "완결 안 된 작품")]);
    await page.goto("/");
    await expect(serialSelect(page, "완결 안 된 작품")).toHaveValue("ongoing");
  });

  test("serial_state 없는 레거시 응답도 ongoing으로 표시", async ({ page }) => {
    const legacy = project(1, "레거시 작품");
    delete (legacy as Partial<Project>).serial_state;
    delete (legacy as Partial<Project>).serial_completed_at;
    await setupFixture(page, [legacy]);
    await page.goto("/");
    await expect(serialSelect(page, "레거시 작품")).toHaveValue("ongoing");
  });

  test("완결 전환 — PATCH 본문에 serial_state만, 시각 표시", async ({ page }) => {
    const fx = await setupFixture(page, [project(1, "연재 작품")]);
    await page.goto("/");
    const select = serialSelect(page, "연재 작품");
    await select.selectOption("completed");
    await expect.poll(() => fx.patches).toHaveLength(1);
    expect(fx.patches).toEqual([{ id: 1, body: { serial_state: "completed" } }]);
    await expect(select).toHaveValue("completed");
    await expect(
      page.locator("div.rounded-lg.border", { hasText: "연재 작품" }).getByText("완결 2026")
    ).toBeVisible();
  });

  test("완결 → 연재 중 복귀 — 시각 표시 사라짐", async ({ page }) => {
    const fx = await setupFixture(page, [project(1, "완결 작품", "completed")]);
    await page.goto("/");
    const select = serialSelect(page, "완결 작품");
    await expect(select).toHaveValue("completed");
    await select.selectOption("ongoing");
    await expect.poll(() => fx.patches).toHaveLength(1);
    expect(fx.patches.at(-1)).toEqual({ id: 1, body: { serial_state: "ongoing" } });
    await expect(select).toHaveValue("ongoing");
    await expect(
      page.locator("div.rounded-lg.border", { hasText: "완결 작품" }).getByText("완결 2026")
    ).toHaveCount(0);
  });

  test("연재 상태는 회차 집필 확정과 별개임이 레이블에 명시됨", async ({ page }) => {
    await setupFixture(page, [project(1, "독립 수명주기")]);
    await page.goto("/");
    const select = serialSelect(page, "독립 수명주기");
    await expect(select).toHaveAccessibleName(/회차 집필 확정과 별개/);
    await expect(select).toHaveAttribute("title", /집필 확정과는 별개/);
  });

  test("접근성 — axe serious/critical 위반 0", async ({ page }) => {
    await setupFixture(page, [project(1, "접근성 검사", "completed")]);
    await page.goto("/");
    await expect(serialSelect(page, "접근성 검사")).toHaveValue("completed");
    const results = await new AxeBuilder({ page }).analyze();
    const serious = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(serious).toEqual([]);
  });
});
