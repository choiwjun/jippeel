import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * U02 — 로어 참조 회차 표시 (F-016) — fixture-only UI 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

type LoreEntry = {
  id: number;
  project_id: number;
  category: string;
  title: string;
  content: string | null;
  keywords: string[] | null;
  created_at: string;
  updated_at: string;
};

type Chapter = {
  id: number;
  project_id: number;
  volume: number | null;
  sort_order: number;
  title: string;
  status: string;
  word_count_cache: number;
  memo: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
};

const NOW = "2026-09-13T00:00:00.000Z";
let unhandled: string[] = [];

function entry(id: number, title: string): LoreEntry {
  return {
    id, project_id: 1, category: "용어", title,
    content: `${title} 설명`, keywords: [title],
    created_at: NOW, updated_at: NOW,
  };
}

function chapter(id: number, title: string, volume: number | null = null): Chapter {
  return {
    id, project_id: 1, volume, sort_order: id, title,
    status: "done", word_count_cache: 100, memo: null, revision: 1,
    created_at: NOW, updated_at: NOW,
  };
}

type RefFixture = {
  entries: Map<number, LoreEntry>;
  refsByEntry: Map<number, Chapter[]>;
  refRequests: number;
};

async function setupFixture(
  page: Page,
  seed: LoreEntry[],
  refs: Record<number, Chapter[]>,
): Promise<RefFixture> {
  const entries = new Map(seed.map((e) => [e.id, e]));
  const fixture: RefFixture = {
    entries,
    refsByEntry: new Map(Object.entries(refs).map(([k, v]) => [Number(k), v])),
    refRequests: 0,
  };

  await page.context().route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (method === "GET" && path === "/projects") return json(200, []);
    if (method === "GET" && path === "/projects/1/lore")
      return json(200, [...entries.values()]);

    const refMatch = path.match(/^\/lore\/(\d+)\/referencing-chapters$/);
    if (refMatch && method === "GET") {
      fixture.refRequests += 1;
      const id = Number(refMatch[1]);
      if (!entries.has(id)) return json(404, { detail: "not found" });
      return json(200, fixture.refsByEntry.get(id) ?? []);
    }

    const loreMatch = path.match(/^\/lore\/(\d+)$/);
    if (loreMatch && method === "GET") {
      const e = entries.get(Number(loreMatch[1]));
      return e ? json(200, e) : json(404, { detail: "not found" });
    }

    unhandled.push(`${method} ${path}`);
    return json(404, { detail: `unhandled fixture route: ${method} ${path}` });
  });
  return fixture;
}

async function openDrawer(page: Page, title: string) {
  await page.goto("/projects/1/lore");
  await page.getByRole("button", { name: new RegExp(title) }).first().click();
}

test.describe("U02 참조 회차", () => {
  test.beforeEach(() => {
    unhandled = [];
  });
  test.afterEach(() => {
    expect(unhandled, `unhandled fixture requests: ${unhandled.join(", ")}`).toEqual([]);
  });

  test("접이식을 열면 참조 회차가 권·제목과 함께 표시된다", async ({ page }) => {
    await setupFixture(page, [entry(1, "검기")], {
      1: [chapter(11, "3화", 1), chapter(12, "7화", 2)],
    });
    await openDrawer(page, "검기");

    const toggle = page.getByRole("button", { name: /참조 회차/ });
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");

    await expect(page.getByText("1권 3화")).toBeVisible();
    await expect(page.getByText("2권 7화")).toBeVisible();
    await expect(toggle).toHaveText(/참조 회차 \(2\)/);
  });

  test("펼치기 전에는 요청하지 않고, 펼치면 한 번만 조회한다", async ({ page }) => {
    const fx = await setupFixture(page, [entry(1, "철혈단")], {
      1: [chapter(5, "1화")],
    });
    await openDrawer(page, "철혈단");
    expect(fx.refRequests).toBe(0);

    await page.getByRole("button", { name: /참조 회차/ }).click();
    await expect(page.getByText("1화")).toBeVisible();
    expect(fx.refRequests).toBe(1);
  });

  test("참조 회차가 없으면 빈 상태 안내를 보인다", async ({ page }) => {
    await setupFixture(page, [entry(1, "미언급")], { 1: [] });
    await openDrawer(page, "미언급");

    await page.getByRole("button", { name: /참조 회차/ }).click();
    await expect(
      page.getByText("본문에서 이 항목을 언급하는 회차가 없습니다.")
    ).toBeVisible();
  });

  test("다시 접으면 목록이 닫힌다", async ({ page }) => {
    await setupFixture(page, [entry(1, "검기")], { 1: [chapter(1, "1화")] });
    await openDrawer(page, "검기");

    const toggle = page.getByRole("button", { name: /참조 회차/ });
    await toggle.click();
    await expect(page.getByText("1화")).toBeVisible();
    await toggle.click();
    await expect(page.getByText("1화")).not.toBeVisible();
  });
});
