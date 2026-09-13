import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * U01 — 캐릭터 card_json 자유 확장 편집 UI — fixture-only 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

type Character = {
  id: number;
  project_id: number;
  name: string;
  aliases: string[] | null;
  role: string | null;
  appearance: string | null;
  personality: string | null;
  speech_style: string | null;
  background: string | null;
  card_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

const NOW = "2026-09-13T00:00:00.000Z";

/** catch-all로 받은 미모킹 요청 — afterEach에서 비어 있음을 단정한다. */
let unhandled: string[] = [];

function character(id: number, cardJson: Record<string, unknown> | null = null): Character {
  return {
    id,
    project_id: 1,
    name: `캐릭터${id}`,
    aliases: [],
    role: "주연",
    appearance: null,
    personality: null,
    speech_style: null,
    background: null,
    card_json: cardJson,
    created_at: NOW,
    updated_at: NOW,
  };
}

type CardFixture = {
  characters: Map<number, Character>;
  patches: Array<{ id: number; patch: Record<string, unknown> }>;
};

const isObj = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v);

/** 백엔드 _merge_patch와 동일 계약 — null은 제거, 객체는 재귀 병합. */
function mergePatch(target: Record<string, unknown>, patch: Record<string, unknown>) {
  for (const [k, v] of Object.entries(patch)) {
    if (v === null) delete target[k];
    else if (isObj(v) && isObj(target[k])) mergePatch(target[k], v);
    else target[k] = v;
  }
}

async function setupFixture(page: Page, seed: Character[]): Promise<CardFixture> {
  const characters = new Map<number, Character>(seed.map((c) => [c.id, c]));
  const fixture: CardFixture = { characters, patches: [] };

  await page.context().route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    const body = () => JSON.parse(route.request().postData() ?? "{}");

    if (method === "GET" && path === "/projects")
      return json(200, []);
    if (method === "GET" && path === "/projects/1/characters")
      return json(200, [...characters.values()]);

    const cardMatch = path.match(/^\/characters\/(\d+)\/card_json$/);
    if (cardMatch) {
      const ch = characters.get(Number(cardMatch[1]));
      if (!ch) return json(404, { detail: "not found" });
      if (method === "PATCH") {
        const { patch } = body();
        if (!isObj(patch)) return json(422, { detail: "patch must be object" });
        fixture.patches.push({ id: ch.id, patch });
        const next = { ...(ch.card_json ?? {}) };
        mergePatch(next, patch);
        ch.card_json = next;
        return json(200, ch);
      }
      return json(405, { detail: "method not allowed" });
    }

    const relMatch = path.match(/^\/characters\/(\d+)\/relations$/);
    if (relMatch && method === "GET") return json(200, []);

    const chMatch = path.match(/^\/characters\/(\d+)$/);
    if (chMatch && method === "GET") {
      const ch = characters.get(Number(chMatch[1]));
      return ch ? json(200, ch) : json(404, { detail: "not found" });
    }

    unhandled.push(`${method} ${path}`);
    return json(404, { detail: `unhandled fixture route: ${method} ${path}` });
  });
  return fixture;
}

async function openDrawer(page: Page, name = "캐릭터1") {
  await page.goto("/projects/1/characters");
  await page.getByRole("button", { name: `${name} 상세 열기` }).click();
  await expect(page.getByLabel("확장 필드 JSON")).toBeVisible();
}

test.describe("U01 card_json 확장 편집", () => {
  test.beforeEach(() => {
    unhandled = [];
  });
  test.afterEach(() => {
    expect(unhandled, `unhandled fixture requests: ${unhandled.join(", ")}`).toEqual([]);
  });

  test("기존 card_json이 JSON으로 표시되고 편집이 merge patch로 저장된다", async ({ page }) => {
    const fx = await setupFixture(page, [
      character(1, { mes_example: "예시", tags: ["a"], ext: { keep: 1, drop: 2 } }),
    ]);
    await openDrawer(page);

    const editor = page.getByLabel("확장 필드 JSON");
    await expect(editor).toHaveValue(/mes_example/);

    await editor.fill(JSON.stringify({ mes_example: "수정", tags: ["a"], ext: { keep: 1 } }, null, 2));
    await page.getByRole("button", { name: "확장 필드 저장" }).click();

    await expect.poll(() => fx.patches).toHaveLength(1);
    const patch = fx.patches[0].patch;
    expect(patch.mes_example).toBe("수정");
    // 제거된 중첩 키는 null tombstone으로 병합 요청된다
    expect((patch.ext as Record<string, unknown>).drop).toBeNull();
    // 서버 응답(병합 결과)이 에디터에 반영된다
    await expect(editor).toHaveValue(/"keep": 1/);
    await expect(editor).not.toHaveValue(/drop/);
  });

  test("잘못된 JSON은 요청 없이 인라인 오류를 보인다", async ({ page }) => {
    const fx = await setupFixture(page, [character(1, { a: 1 })]);
    await openDrawer(page);

    await page.getByLabel("확장 필드 JSON").fill("{ not json ");
    await page.getByRole("button", { name: "확장 필드 저장" }).click();
    await expect(page.getByRole("alert")).toHaveText("JSON 형식이 올바르지 않습니다.");
    expect(fx.patches).toHaveLength(0);
  });

  test("최상위가 객체가 아니면 요청 없이 거부된다", async ({ page }) => {
    const fx = await setupFixture(page, [character(1)]);
    await openDrawer(page);

    await page.getByLabel("확장 필드 JSON").fill('["a","b"]');
    await page.getByRole("button", { name: "확장 필드 저장" }).click();
    await expect(page.getByRole("alert")).toHaveText(/최상위는 JSON 객체/);
    expect(fx.patches).toHaveLength(0);
  });

  test("변경이 없으면 PATCH를 보내지 않는다", async ({ page }) => {
    const fx = await setupFixture(page, [character(1, { a: 1 })]);
    await openDrawer(page);

    await page.getByRole("button", { name: "확장 필드 저장" }).click();
    await expect(page.getByText("변경된 내용이 없습니다.")).toBeVisible();
    expect(fx.patches).toHaveLength(0);
  });

  test("빈 card_json은 빈 객체로 시작하고 새 키를 추가할 수 있다", async ({ page }) => {
    const fx = await setupFixture(page, [character(1, null)]);
    await openDrawer(page);

    const editor = page.getByLabel("확장 필드 JSON");
    await expect(editor).toHaveValue("{}");
    await editor.fill(JSON.stringify({ scenario: "첫 만남" }));
    await page.getByRole("button", { name: "확장 필드 저장" }).click();

    await expect.poll(() => fx.patches).toHaveLength(1);
    expect(fx.patches[0].patch.scenario).toBe("첫 만남");
    await expect(editor).toHaveValue(/scenario/);
  });
});
