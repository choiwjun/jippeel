import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * D03-6 완결본 관리 — fixture-only UI 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

const NOW = "2026-09-13T00:00:00.000Z";
const PROJECT_ID = 1;

type Edition = {
  id: number;
  project_id: number;
  label: string | null;
  created_at: string;
  serial_state: string;
  chapter_count: number;
  total_chars: number;
  manifest: Array<Record<string, unknown>>;
  content_md: string;
  checklist: Record<string, unknown>;
};

const CHECKLIST = {
  serial_state: "completed",
  serial_completed_at: NOW,
  chapters: {
    total: 2,
    by_stage: { planning: 0, writing: 0, revising: 1, confirmed: 1 },
    unconfirmed: 1,
  },
  foreshadows: {
    total: 3,
    open: [{ id: 9, title: "검은 검의 주인", status: "설치" }],
    by_disposition: {
      resolved: 1,
      intentional_unresolved: 0,
      side_story: 1,
      closed_unclassified: 0,
    },
  },
  pending_refine_runs: 2,
  broken_evidence_links: 1,
  finale_goals_missing_ending: [{ chapter_id: 7, title: "최종화" }],
};

/** catch-all로 받은 미모킹 요청 — afterEach에서 비어 있음을 단정한다. */
let unhandled: string[] = [];

function edition(id: number, label: string | null): Edition {
  const content = "## 1화\n\n첫째 본문\n\n## 2화\n\n둘째 본문";
  return {
    id,
    project_id: PROJECT_ID,
    label,
    created_at: NOW,
    serial_state: "completed",
    chapter_count: 2,
    total_chars: content.length,
    manifest: [
      {
        chapter_id: 11,
        title: "1화",
        sort_order: 1,
        revision: 3,
        flow_stage: "confirmed",
        status: "완료",
        chars: 5,
      },
      {
        chapter_id: 12,
        title: "2화",
        sort_order: 2,
        revision: 1,
        flow_stage: "revising",
        status: "초고",
        chars: 5,
      },
    ],
    content_md: content,
    checklist: CHECKLIST,
  };
}

type Fixture = {
  editions: Map<number, Edition>;
  posts: Array<Record<string, unknown>>;
  deletes: number[];
  nextId: number;
};

async function setupFixture(page: Page, seed: Edition[]): Promise<Fixture> {
  const editions = new Map<number, Edition>(seed.map((e) => [e.id, e]));
  const fixture: Fixture = { editions, posts: [], deletes: [], nextId: 100 };

  await page.context().route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    const body = () => JSON.parse(route.request().postData() ?? "{}");

    if (method === "GET" && path === `/projects/${PROJECT_ID}/completion-checklist`)
      return json(200, CHECKLIST);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/final-editions`) {
      const rows = [...editions.values()].map(
        ({ manifest, content_md, checklist, ...meta }) => meta,
      );
      return json(200, rows);
    }
    if (method === "POST" && path === `/projects/${PROJECT_ID}/final-editions`) {
      const req = body();
      fixture.posts.push(req);
      // 백엔드 FinalEditionCreate와 동일 — extra=forbid, label만 허용
      const unknown = Object.keys(req).filter((k) => k !== "label");
      if (unknown.length) return json(422, { detail: `extra fields: ${unknown}` });
      if (req.label !== undefined && req.label !== null && typeof req.label !== "string")
        return json(422, { detail: "label must be a string" });
      const e = edition(fixture.nextId++, req.label ?? null);
      editions.set(e.id, e);
      return json(201, e);
    }
    const detailMatch = path.match(
      new RegExp(`^/projects/${PROJECT_ID}/final-editions/(\\d+)$`),
    );
    if (detailMatch) {
      const e = editions.get(Number(detailMatch[1]));
      if (!e) return json(404, { detail: "final edition not found" });
      if (method === "GET") return json(200, e);
      if (method === "DELETE") {
        fixture.deletes.push(e.id);
        editions.delete(e.id);
        return route.fulfill({ status: 204 });
      }
    }
    unhandled.push(`${method} ${path}`);
    return json(500, { detail: `unhandled ${method} ${path}` });
  });
  return fixture;
}

test.afterEach(() => {
  expect(unhandled, `unhandled API requests: ${unhandled}`).toEqual([]);
  unhandled = [];
});

test.describe("D03-6 완결본 관리", () => {
  test("완결 점검표 수치·배지·미회수 복선 표시", async ({ page }) => {
    await setupFixture(page, []);
    await page.goto(`/projects/${PROJECT_ID}/completion`);

    await expect(page.getByText("미회수 복선:")).toBeVisible();
    await expect(page.getByText("검은 검의 주인")).toBeVisible();
    await expect(page.getByText("미수용 감수 2건")).toBeVisible();
    await expect(page.getByText("파손 근거 링크 1건")).toBeVisible();
    await expect(page.getByText("결말 의도 없는 최종화 목표:")).toBeVisible();
    await expect(page.getByText("최종화")).toBeVisible();
    // 단계 배지
    await expect(page.getByText("확정 1", { exact: true })).toBeVisible();
    await expect(page.getByText("퇴고 1")).toBeVisible();
    // disposition 배지
    await expect(page.getByText("해결 1")).toBeVisible();
    await expect(page.getByText("외전 이관 1")).toBeVisible();
  });

  test("완결본 생성 — 라벨 없으면 '완결본 {id}'로 목록 반영", async ({ page }) => {
    const fixture = await setupFixture(page, []);
    await page.goto(`/projects/${PROJECT_ID}/completion`);

    await page.getByRole("button", { name: "완결본 생성" }).click();
    await expect(page.getByText("완결본 100")).toBeVisible();
    expect(fixture.posts).toEqual([{ label: null }]);

    await page.getByLabel("라벨(선택)").fill("1차 완결본");
    await page.getByRole("button", { name: "완결본 생성" }).click();
    await expect(page.getByText("1차 완결본")).toBeVisible();
    expect(fixture.posts[1]).toEqual({ label: "1차 완결본" });
  });

  test("완결본 상세 — 매니페스트·원고 전문 표시", async ({ page }) => {
    await setupFixture(page, [edition(5, "보존본")]);
    await page.goto(`/projects/${PROJECT_ID}/completion`);

    await page.getByText("보존본").click();
    await expect(page.getByText("매니페스트")).toBeVisible();
    await expect(page.getByText("1화 · r3 · 확정 · 5자")).toBeVisible();
    await expect(page.getByText("첫째 본문")).toBeVisible();
    await expect(page.getByText("둘째 본문")).toBeVisible();
  });

  test("완결본 삭제 — 목록에서 제거", async ({ page }) => {
    const fixture = await setupFixture(page, [edition(5, "보존본")]);
    await page.goto(`/projects/${PROJECT_ID}/completion`);

    await expect(page.getByText("보존본")).toBeVisible();
    await page.getByRole("button", { name: "삭제" }).click();
    await expect(page.getByText("보존본")).not.toBeVisible();
    await expect(page.getByText("아직 완결본이 없습니다.")).toBeVisible();
    expect(fixture.deletes).toEqual([5]);
  });

  test("연재 상태 배지 표시 — 완결 라벨", async ({ page }) => {
    await setupFixture(page, [edition(5, null)]);
    await page.goto(`/projects/${PROJECT_ID}/completion`);
    // 완결본 행의 배지를 행 범위로 한정해 단정한다
    const row = page.locator("li", { hasText: "완결본 5" });
    await expect(row.getByText("완결", { exact: true })).toBeVisible();
  });

  test("a11y — serious/critical 위반 없음", async ({ page }) => {
    await setupFixture(page, [edition(5, "보존본")]);
    await page.goto(`/projects/${PROJECT_ID}/completion`);
    await page.getByText("보존본").click();
    await expect(page.getByText("매니페스트")).toBeVisible();

    const results = await new AxeBuilder({ page }).analyze();
    const violations = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(violations).toEqual([]);
  });
});
