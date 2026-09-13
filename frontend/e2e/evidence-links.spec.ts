import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * D03-4 근거 연결 — fixture-only UI 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

type EvidenceLinkField = "core_events" | "character_choices" | "cost";
type Link = {
  id: number;
  chapter_id: number;
  goal_field: EvidenceLinkField;
  item_index: number | null;
  goal_item_text: string;
  excerpt: string;
  goal_version: number;
  created_at: string;
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
  flow_stage: string;
  content_md: string;
  created_at: string;
  updated_at: string;
};

const NOW = "2026-09-13T00:00:00.000Z";
const PROJECT_ID = 1;
const CHAPTER_ID = 10;
const EXCERPT = "주인공이 검을 뽑았다";
const CONTENT = `첫 문단이다. ${EXCERPT} 그리고 달렸다.`;

const GOAL = {
  goal_version: 1,
  goal: {
    emotion_goal: "긴장감",
    core_events: ["검을 뽑는다", "도망친다"],
    character_choices: ["공주를 구한다"],
    cost: "왼팔을 잃는다",
  },
  episode_purpose: "serial",
  base_manuscript_revision: 0,
  created_at: NOW,
  updated_at: NOW,
};

function chapter(): Chapter {
  return {
    id: CHAPTER_ID,
    project_id: PROJECT_ID,
    volume: 1,
    sort_order: 1,
    title: "1화",
    status: "초고",
    word_count_cache: CONTENT.length,
    memo: null,
    revision: 1,
    flow_stage: "writing",
    content_md: CONTENT,
    created_at: NOW,
    updated_at: NOW,
  };
}

type Fixture = {
  ch: Chapter;
  links: Link[];
  nextLinkId: number;
  posts: Array<Record<string, unknown>>;
  deletes: number[];
  goalPresent: boolean;
};

/** fixture 서버 — 백엔드 계약 재현: 생성 검증 + 읽기 시 파생 상태 계산. */
async function setupFixture(page: Page, seedLinks: Link[] = []): Promise<Fixture> {
  const ch = chapter();
  const fixture: Fixture = {
    ch,
    links: seedLinks.map((l, i) => ({ ...l, id: i + 1, chapter_id: CHAPTER_ID })),
    nextLinkId: seedLinks.length + 1,
    posts: [],
    deletes: [],
    goalPresent: true,
  };

  const goalItemAt = (field: string, index: number | null): string | null => {
    const value = (GOAL.goal as Record<string, unknown>)[field];
    if (index === null)
      return typeof value === "string" && value.trim() ? value : null;
    if (!Array.isArray(value) || index < 0 || index >= value.length) return null;
    const item = value[index];
    return typeof item === "string" && item.trim() ? item : null;
  };
  const linkOut = (link: Link) => ({
    ...link,
    current_goal_version: GOAL.goal_version,
    manuscript_status: ch.content_md.includes(link.excerpt) ? "intact" : "broken",
    goal_status: !fixture.goalPresent
      ? "goal_deleted"
      : goalItemAt(link.goal_field, link.item_index) === link.goal_item_text
        ? "unchanged"
        : "drifted",
  });

  await page.context().route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    const body = () => JSON.parse(route.request().postData() ?? "{}");

    if (method === "GET" && path === `/projects/${PROJECT_ID}/chapters`)
      return json(200, [{ ...ch, content_md: undefined }]);
    if (method === "GET" && path === `/chapters/${CHAPTER_ID}`)
      return json(200, ch);
    if (method === "GET" && path === `/chapters/${CHAPTER_ID}/goal`)
      return json(200, {
        chapter_id: CHAPTER_ID,
        project_id: PROJECT_ID,
        goal: GOAL,
        current_chapter_revision: ch.revision,
        history_count: 1,
      });
    if (method === "GET" && path === `/chapters/${CHAPTER_ID}/goal/history`)
      return json(200, [GOAL]);
    if (method === "GET" && path === `/chapters/${CHAPTER_ID}/flow`)
      return json(200, {
        chapter_id: CHAPTER_ID,
        project_id: PROJECT_ID,
        flow_stage: ch.flow_stage,
        last_event: null,
        current_goal_version: GOAL.goal_version,
        current_chapter_revision: ch.revision,
      });
    // 생성 전 draft flush용 원고 PUT — revision CAS + 동일 본문이면 revision 유지
    if (method === "PUT" && path === `/chapters/${CHAPTER_ID}/content`) {
      const req = body();
      if (req.expected_revision !== ch.revision)
        return json(409, {
          detail: {
            code: "revision_conflict",
            message: "서버에 더 최신 원고가 있습니다.",
            current_revision: ch.revision,
          },
        });
      if (req.content_md !== ch.content_md) {
        ch.content_md = String(req.content_md);
        ch.revision += 1;
        ch.updated_at = NOW;
      }
      return json(200, ch);
    }

    if (method === "GET" && path === `/chapters/${CHAPTER_ID}/resume`)
      return json(200, {
        chapter_id: CHAPTER_ID,
        project_id: PROJECT_ID,
        flow_stage: ch.flow_stage,
        last_event: null,
        current_goal_version: GOAL.goal_version,
        current_chapter_revision: ch.revision,
        goal_changed_since_transition: false,
        manuscript_changed_since_transition: false,
        pending_refine_runs: 0,
        next_scene: null,
        scene_count: 0,
      });

    const linksMatch = path.match(/^\/chapters\/(\d+)\/evidence-links$/);
    if (linksMatch) {
      if (Number(linksMatch[1]) !== CHAPTER_ID) return json(404, { detail: "not found" });
      if (method === "GET")
        return json(200, { chapter_id: CHAPTER_ID, links: fixture.links.map(linkOut) });
      if (method === "POST") {
        const req = body();
        fixture.posts.push(req);
        const field = req.goal_field;
        if (!["core_events", "character_choices", "cost"].includes(String(field)))
          return json(422, { detail: [{ type: "literal_error", loc: ["body", "goal_field"], msg: "invalid" }] });
        const isList = field !== "cost";
        const index = req.item_index ?? null;
        if (isList && index === null)
          return json(422, { detail: "item_index required for list goal field" });
        if (!isList && index !== null)
          return json(422, { detail: "item_index not allowed for scalar goal field" });
        const itemText = goalItemAt(field, index);
        if (itemText === null) return json(422, { detail: "goal item not found" });
        const excerpt = String(req.excerpt ?? "");
        if (!excerpt.trim()) return json(422, { detail: "excerpt must not be blank" });
        if (!ch.content_md.includes(excerpt))
          return json(422, { detail: "excerpt not found in manuscript" });
        const link: Link = {
          id: fixture.nextLinkId++,
          chapter_id: CHAPTER_ID,
          goal_field: field,
          item_index: index,
          goal_item_text: itemText,
          excerpt,
          goal_version: GOAL.goal_version,
          created_at: NOW,
        };
        fixture.links.push(link);
        return json(201, linkOut(link));
      }
    }
    const deleteMatch = path.match(/^\/chapters\/(\d+)\/evidence-links\/(\d+)$/);
    if (method === "DELETE" && deleteMatch) {
      const lid = Number(deleteMatch[2]);
      const idx = fixture.links.findIndex((l) => l.id === lid);
      if (idx < 0) return json(404, { detail: "not found" });
      fixture.deletes.push(lid);
      fixture.links.splice(idx, 1);
      return json(204, null);
    }

    if (method === "GET" && path === "/ai/presets") return json(200, []);
    if (method === "GET" && /^\/chapters\/\d+\/scenes$/.test(path)) return json(200, []);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/foreshadows/match`)
      return json(200, []);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/foreshadows`)
      return json(200, []);
    if (method === "GET" && path === `/projects/${PROJECT_ID}`) return json(200, { id: PROJECT_ID, title: "근거 작품" });
    if (method === "GET" && `/projects/${PROJECT_ID}/memories` === path) return json(200, []);

    return json(599, { detail: `Unexpected API request in evidence-links fixture: ${method} ${path}${url.search}` });
  });
  return fixture;
}

const seedLink = (over: Partial<Link> = {}): Link => ({
  id: 0,
  chapter_id: CHAPTER_ID,
  goal_field: "core_events",
  item_index: 0,
  goal_item_text: "검을 뽑는다",
  excerpt: EXCERPT,
  goal_version: 1,
  created_at: NOW,
  ...over,
});

async function openBrief(page: Page) {
  await page.goto(`/projects/${PROJECT_ID}/write`);
  await expect(page.locator(".cm-content")).toBeVisible();
  await page.getByRole("button", { name: "AI 패널" }).click();
  await expect(page.getByText("호출 컨텍스트")).toBeVisible();
  await page.getByRole("button", { name: /이번 화 브리프/ }).click();
}

test.describe("D03-4 근거 연결", () => {
  test("링크 목록과 파생 상태 배지를 표시한다", async ({ page }) => {
    await setupFixture(page, [
      seedLink(), // intact + unchanged → 배지 없음
      seedLink({ goal_field: "cost", item_index: null, goal_item_text: "왼팔을 잃는다", excerpt: "삭제된 문장" }), // broken
      seedLink({ goal_field: "character_choices", item_index: 0, goal_item_text: "왕자를 구한다", excerpt: EXCERPT }), // drifted
    ]);
    await openBrief(page);
    const list = page.getByLabel("목표 근거 연결");
    await expect(list.getByText(/검을 뽑는다 →/)).toBeVisible();
    await expect(list.getByText("원문 파손")).toBeVisible();
    await expect(list.getByText("목표 변경됨")).toBeVisible();
    // intact 링크에는 파손 배지가 하나만(broken 건) 표시된다
    await expect(list.getByText("원문 파손")).toHaveCount(1);
  });

  test("선택 본문을 목표 항목에 연결한다 — POST 본문 계약", async ({ page }) => {
    const fx = await setupFixture(page);
    // 실제 UX: 에디터에서 먼저 본문을 선택한 뒤 패널을 연다(패널 Sheet가 에디터를 가린다)
    await page.goto(`/projects/${PROJECT_ID}/write`);
    await expect(page.locator(".cm-content")).toBeVisible();
    await page.locator(".cm-content").click();
    await page.keyboard.press("End");
    await page.keyboard.press("Shift+Home"); // 한 줄 전체 선택

    await page.getByRole("button", { name: "AI 패널" }).click();
    await expect(page.getByText("호출 컨텍스트")).toBeVisible();
    await page.getByRole("button", { name: /이번 화 브리프/ }).click();
    await page.getByLabel("연결할 목표 항목").selectOption("core_events:0");
    await page.getByRole("button", { name: "선택 본문 연결" }).click();
    await expect.poll(() => fx.posts).toHaveLength(1);
    expect(fx.posts[0]).toMatchObject({
      goal_field: "core_events",
      item_index: 0,
    });
    expect(String(fx.posts[0].excerpt)).toContain(EXCERPT);
    await expect(page.getByLabel("목표 근거 연결").getByText(/검을 뽑는다 →/)).toBeVisible();
  });

  test("스칼라 목표(cost) 연결은 item_index null을 보낸다", async ({ page }) => {
    const fx = await setupFixture(page);
    await page.goto(`/projects/${PROJECT_ID}/write`);
    await expect(page.locator(".cm-content")).toBeVisible();
    await page.locator(".cm-content").click();
    await page.keyboard.press("End");
    await page.keyboard.press("Shift+Home");

    await page.getByRole("button", { name: "AI 패널" }).click();
    await page.getByRole("button", { name: /이번 화 브리프/ }).click();
    await page.getByLabel("연결할 목표 항목").selectOption("cost");
    await page.getByRole("button", { name: "선택 본문 연결" }).click();
    await expect.poll(() => fx.posts).toHaveLength(1);
    expect(fx.posts[0]).toMatchObject({ goal_field: "cost", item_index: null });
  });

  test("목표 삭제된 링크는 '목표 삭제됨' 배지를 표시한다", async ({ page }) => {
    const fx = await setupFixture(page, [seedLink()]);
    fx.goalPresent = false;
    await page.context().route(`**/api/v1/chapters/${CHAPTER_ID}/goal`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          chapter_id: CHAPTER_ID,
          project_id: PROJECT_ID,
          goal: null,
          current_chapter_revision: fx.ch.revision,
          history_count: 0,
        }),
      }),
    );
    await openBrief(page);
    const list = page.getByLabel("목표 근거 연결");
    await expect(list.getByText(/검을 뽑는다 →/)).toBeVisible();
    await expect(list.getByText("목표 삭제됨")).toBeVisible();
  });

  test("선택 없이 연결하면 경고 toast만 띄우고 요청하지 않는다", async ({ page }) => {
    const fx = await setupFixture(page);
    await openBrief(page);
    await page.getByLabel("연결할 목표 항목").selectOption("cost");
    await page.getByRole("button", { name: "선택 본문 연결" }).click();
    await expect(page.getByText("에디터에서 연결할 본문을 먼저 선택하세요.")).toBeVisible();
    await new Promise((r) => setTimeout(r, 300));
    expect(fx.posts).toEqual([]);
  });

  test("링크 삭제는 DELETE 후 목록을 비운다", async ({ page }) => {
    const fx = await setupFixture(page, [seedLink()]);
    await openBrief(page);
    const list = page.getByLabel("목표 근거 연결");
    await expect(list.getByText(/검을 뽑는다 →/)).toBeVisible();
    await list.getByRole("button", { name: /근거 링크 삭제/ }).click();
    await expect.poll(() => fx.deletes).toEqual([1]);
    await expect(list.getByText("연결된 근거가 없습니다.")).toBeVisible();
  });

  test("목표 항목이 없으면 항목 선택기가 없다", async ({ page }) => {
    // goal 없는 회차 — fixture의 GOAL 응답을 덮어쓴다
    const fx = await setupFixture(page);
    await page.context().route(`**/api/v1/chapters/${CHAPTER_ID}/goal`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          chapter_id: CHAPTER_ID,
          project_id: PROJECT_ID,
          goal: null,
          current_chapter_revision: fx.ch.revision,
          history_count: 0,
        }),
      }),
    );
    await openBrief(page);
    await expect(page.getByLabel("연결할 목표 항목")).toHaveCount(0);
    await expect(page.getByText("연결된 근거가 없습니다.")).toBeVisible();
  });

  test("접근성 — axe serious/critical 위반 0", async ({ page }) => {
    await setupFixture(page, [seedLink()]);
    await openBrief(page);
    await expect(page.getByText(/검을 뽑는다 →/)).toBeVisible();
    const results = await new AxeBuilder({ page }).analyze();
    const serious = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(serious).toEqual([]);
  });
});
