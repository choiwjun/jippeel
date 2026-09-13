import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * D01 회차 목표 영속화 — fixture-only UI 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

type Chapter = {
  id: number;
  project_id: number;
  volume: number | null;
  sort_order: number;
  title: string;
  status: "초고" | "수정중" | "완료";
  word_count_cache: number;
  memo: string | null;
  revision: number;
  content_md: string;
  created_at: string;
  updated_at: string;
};

type GoalPayload = Record<string, unknown>;
type GoalRow = {
  goal_version: number;
  goal: GoalPayload;
  episode_purpose: string;
  base_manuscript_revision: number | null;
};
type GoalRevisionRow = GoalRow & { id: number; restored_from: number | null; created_at: string };

const NOW = "2026-09-13T00:00:00.000Z";
const PROJECT_ID = 1;
const CHAPTER_A = 10;
const CHAPTER_B = 11;

function chapter(id: number, title: string, revision: number): Chapter {
  return {
    id,
    project_id: PROJECT_ID,
    volume: 1,
    sort_order: id === CHAPTER_A ? 1 : 2,
    title,
    status: "초고",
    word_count_cache: 10,
    memo: null,
    revision,
    content_md: `${title} 본문`,
    created_at: NOW,
    updated_at: NOW,
  };
}

type GoalStore = {
  current: (GoalRow & { created_at: string; updated_at: string }) | null;
  revisions: GoalRevisionRow[];
  nextId: number;
};

function goalOut(cid: number, store: GoalStore, chapters: Map<number, Chapter>) {
  return {
    chapter_id: cid,
    project_id: PROJECT_ID,
    goal: store.current
      ? {
          goal_version: store.current.goal_version,
          goal: store.current.goal,
          episode_purpose: store.current.episode_purpose,
          base_manuscript_revision: store.current.base_manuscript_revision,
          created_at: store.current.created_at,
          updated_at: store.current.updated_at,
        }
      : null,
    current_chapter_revision: chapters.get(cid)?.revision ?? 0,
    history_count: store.revisions.length,
  };
}

type GoalFixture = {
  chapters: Map<number, Chapter>;
  goals: Map<number, GoalStore>;
  puts: Array<{ cid: number; body: any }>;
  deletes: number[];
  restores: Array<{ cid: number; body: any }>;
  heldGoalPut: { route: Route; cid: number; body: any } | null;
};

/** fixture 서버 CAS — 백엔드와 동일 규칙(생성=null 기대, 갱신=버전 일치). */
async function setupFixture(page: Page, seed?: Map<number, GoalRow[]>): Promise<GoalFixture> {
  const chapters = new Map<number, Chapter>([
    [CHAPTER_A, chapter(CHAPTER_A, "1화", 3)],
    [CHAPTER_B, chapter(CHAPTER_B, "2화", 1)],
  ]);
  const goals = new Map<number, GoalStore>();
  for (const cid of [CHAPTER_A, CHAPTER_B]) {
    const rows = seed?.get(cid) ?? [];
    goals.set(cid, {
      current: rows.length
        ? { ...rows[rows.length - 1], created_at: NOW, updated_at: NOW }
        : null,
      revisions: rows.map((row, i) => ({
        ...row,
        id: i + 1,
        restored_from: null,
        created_at: NOW,
      })),
      nextId: rows.length + 1,
    });
  }
  const fixture: GoalFixture = { chapters, goals, puts: [], deletes: [], restores: [], heldGoalPut: null };

  await page.context().route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    const body = () => JSON.parse(route.request().postData() ?? "{}");

    if (method === "GET" && path === `/projects/${PROJECT_ID}/chapters`)
      return json(200, [...chapters.values()].map(({ content_md: _c, ...rest }) => rest));
    const chapterMatch = path.match(/^\/chapters\/(\d+)$/);
    if (method === "GET" && chapterMatch) {
      const c = chapters.get(Number(chapterMatch[1]));
      return c ? json(200, c) : json(404, { detail: "not found" });
    }
    const contentMatch = path.match(/^\/chapters\/(\d+)\/content$/);
    if (method === "PUT" && contentMatch) {
      const c = chapters.get(Number(contentMatch[1]));
      if (!c) return json(404, { detail: "not found" });
      const next = { ...c, content_md: body().content_md ?? c.content_md, revision: c.revision + 1, updated_at: NOW };
      chapters.set(c.id, next);
      return json(200, next);
    }
    const goalMatch = path.match(/^\/chapters\/(\d+)\/goal$/);
    if (goalMatch) {
      const cid = Number(goalMatch[1]);
      const store = goals.get(cid);
      if (!store) return json(404, { detail: "not found" });
      if (method === "GET") return json(200, goalOut(cid, store, chapters));
      if (method === "PUT") {
        const req = body();
        fixture.puts.push({ cid, body: req });
        const expected = req.expected_goal_version ?? null;
        if ((expected === null) !== (store.current === null) || (expected !== null && store.current?.goal_version !== expected)) {
          return json(409, {
            detail: {
              code: "goal_version_conflict",
              message: "목표가 다른 곳에서 먼저 저장되었습니다.",
              current_goal_version: store.current?.goal_version ?? null,
            },
          });
        }
        const nextVersion = Math.max(
          store.current?.goal_version ?? 0,
          ...store.revisions.map((r) => r.goal_version),
          0,
        ) + 1;
        const row = {
          goal_version: nextVersion,
          goal: req.goal,
          episode_purpose: req.episode_purpose ?? "serial",
          base_manuscript_revision: req.base_manuscript_revision ?? chapters.get(cid)?.revision ?? null,
        };
        store.current = { ...row, created_at: NOW, updated_at: NOW };
        store.revisions.push({ ...row, id: store.nextId++, restored_from: null, created_at: NOW });
        return json(200, goalOut(cid, store, chapters));
      }
      if (method === "DELETE") {
        fixture.deletes.push(cid);
        if (!store.current) return json(404, { detail: "goal not found" });
        store.current = null;
        return route.fulfill({ status: 204 });
      }
    }
    const historyMatch = path.match(/^\/chapters\/(\d+)\/goal\/history$/);
    if (method === "GET" && historyMatch) {
      const store = goals.get(Number(historyMatch[1]));
      if (!store) return json(404, { detail: "not found" });
      return json(200, [...store.revisions].sort((a, b) => b.goal_version - a.goal_version));
    }
    const restoreMatch = path.match(/^\/chapters\/(\d+)\/goal\/restore$/);
    if (method === "POST" && restoreMatch) {
      const cid = Number(restoreMatch[1]);
      const store = goals.get(cid);
      if (!store) return json(404, { detail: "not found" });
      const req = body();
      fixture.restores.push({ cid, body: req });
      const source = store.revisions.find((r) => r.goal_version === req.goal_version);
      if (!source) return json(404, { detail: "goal revision not found" });
      const expected = req.expected_goal_version ?? null;
      if ((expected === null) !== (store.current === null) || (expected !== null && store.current?.goal_version !== expected)) {
        return json(409, { detail: { code: "goal_version_conflict", message: "conflict", current_goal_version: store.current?.goal_version ?? null } });
      }
      const nextVersion = Math.max(store.current?.goal_version ?? 0, ...store.revisions.map((r) => r.goal_version), 0) + 1;
      const row = {
        goal_version: nextVersion,
        goal: source.goal,
        episode_purpose: source.episode_purpose,
        base_manuscript_revision: req.base_manuscript_revision ?? chapters.get(cid)?.revision ?? null,
      };
      store.current = { ...row, created_at: NOW, updated_at: NOW };
      store.revisions.push({ ...row, id: store.nextId++, restored_from: source.goal_version, created_at: NOW });
      return json(200, goalOut(cid, store, chapters));
    }

    if (method === "GET" && path === "/ai/presets") return json(200, []);
    if (method === "GET" && /^\/chapters\/\d+\/scenes$/.test(path)) return json(200, []);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/foreshadows/match`) return json(200, []);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/foreshadows`) return json(200, []);
    // D03-4: 브리프 섹션이 열리면 근거 링크를 조회한다.
    if (method === "GET" && /^\/chapters\/\d+\/evidence-links$/.test(path))
      return json(200, { chapter_id: Number(path.match(/\d+/)?.[0]), links: [] });

    return json(599, { detail: `Unexpected API request in chapter-goal fixture: ${method} ${path}${url.search}` });
  });

  return fixture;
}

async function openEditorAndPanel(page: Page) {
  await page.goto(`/projects/${PROJECT_ID}/write`);
  await expect(page.locator(".cm-content")).toBeVisible();
  await page.getByRole("button", { name: "AI 패널" }).click();
  await expect(page.getByText("호출 컨텍스트")).toBeVisible();
  await page.getByRole("button", { name: /이번 화 브리프/ }).click();
}

/** 패널 Sheet가 사이드바를 가리므로 닫고 회차를 바꾼 뒤 다시 연다 (브리프 작업본은 store에 유지). */
async function switchChapter(page: Page, name: RegExp) {
  await page.getByRole("button", { name: "패널 닫기" }).click();
  await page.getByRole("button", { name }).click();
  await expect(page.locator(".cm-content")).toBeVisible();
  await page.getByRole("button", { name: "AI 패널" }).click();
  await expect(page.getByText("호출 컨텍스트")).toBeVisible();
  await page.getByRole("button", { name: /이번 화 브리프/ }).click();
}

test.describe.serial("D01 회차 목표 영속화 fixture", () => {
  test("목표 저장은 정규화된 payload·expected 버전으로 PUT하고 저장본 배지를 표시한다", async ({ page }) => {
    const fixture = await setupFixture(page);
    await openEditorAndPanel(page);
    await expect(page.getByLabel("저장된 회차 목표 없음")).toBeVisible();

    await page.getByLabel("감정 목표").fill("  굴욕을 뒤집는 통쾌함  ");
    await page.getByLabel(/핵심 사건/).fill("파문 통보\n\n흑요검의 첫 반응");
    const saveRequest = page.waitForRequest((req) => req.method() === "PUT" && req.url().includes("/goal"));
    await page.getByRole("button", { name: "목표 저장" }).click();
    const request = await saveRequest;
    expect(new URL(request.url()).pathname).toBe(`/api/v1/chapters/${CHAPTER_A}/goal`);
    expect(request.postDataJSON()).toMatchObject({
      project_id: PROJECT_ID,
      expected_goal_version: null,
      episode_purpose: "serial",
      goal: {
        emotion_goal: "굴욕을 뒤집는 통쾌함",
        core_events: ["파문 통보", "흑요검의 첫 반응"],
      },
    });
    await expect(page.getByLabel("저장된 회차 목표 v1")).toBeVisible();
  });

  test("재진입 시 저장본이 폼에 hydrate되고 저장된 purpose가 directive에 되돌아간다", async ({ page }) => {
    await setupFixture(
      page,
      new Map([
        [
          CHAPTER_A,
          [
            {
              goal_version: 2,
              goal: {
                emotion_goal: "저장된 감정 목표",
                core_events: ["저장 사건"],
                character_choices: null,
                cost: "저장된 대가",
                prohibitions: null,
                next_hook: null,
                ending_intent: "저장된 엔딩",
                scene_type: "대립",
                target_chars_novelpia: 5500,
              },
              episode_purpose: "volume_end",
              base_manuscript_revision: 3,
            },
          ],
        ],
      ]),
    );
    await openEditorAndPanel(page);
    await expect(page.getByLabel("감정 목표")).toHaveValue("저장된 감정 목표");
    await expect(page.getByLabel(/핵심 사건/)).toHaveValue("저장 사건");
    await expect(page.getByLabel("엔딩 의도")).toHaveValue("저장된 엔딩");
    await expect(page.getByLabel("회차 목적")).toHaveValue("volume_end");
    await expect(page.getByLabel("저장된 회차 목표 v2")).toBeVisible();
  });

  test("회차 전환은 미저장 입력을 회차별 작업본으로 보존한다", async ({ page }) => {
    await setupFixture(page);
    await openEditorAndPanel(page);
    await page.getByLabel("감정 목표").fill("A 회차 미저장 입력");

    await switchChapter(page, /2화/);
    await expect(page.getByLabel("감정 목표")).toHaveValue("");

    await switchChapter(page, /1화/);
    await expect(page.getByLabel("감정 목표")).toHaveValue("A 회차 미저장 입력");
  });

  test("늦은 저장 응답은 다른 회차 폼·저장본을 오염시키지 않는다", async ({ page }) => {
    const fixture = await setupFixture(page);
    await openEditorAndPanel(page);
    await page.getByLabel("감정 목표").fill("A 저장 요청 본문");
    // page.route는 context.route보다 먼저 매칭 — A의 PUT 응답만 지연시킨다
    await page.route(`**/api/v1/chapters/${CHAPTER_A}/goal`, async (route) => {
      if (route.request().method() !== "PUT") return route.fallback();
      fixture.heldGoalPut = { route, cid: CHAPTER_A, body: route.request().postDataJSON() };
    });
    await page.getByRole("button", { name: "목표 저장" }).click();
    await expect.poll(() => fixture.heldGoalPut !== null).toBe(true);

    await switchChapter(page, /2화/);
    await expect(page.getByLabel("감정 목표")).toHaveValue("");

    // A의 지연 응답을 풀어준다 — B 폼은 비어 있어야 하고 B 저장본도 없어야 한다
    const held = fixture.heldGoalPut!;
    const store = fixture.goals.get(CHAPTER_A)!;
    const row = {
      goal_version: 1,
      goal: held.body.goal,
      episode_purpose: "serial",
      base_manuscript_revision: 3,
    };
    store.current = { ...row, created_at: NOW, updated_at: NOW };
    store.revisions.push({ ...row, id: 1, restored_from: null, created_at: NOW });
    await held.route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(goalOut(CHAPTER_A, store, fixture.chapters)),
    });
    await page.waitForTimeout(200);
    await expect(page.getByLabel("감정 목표")).toHaveValue("");
    await expect(page.getByLabel("저장된 회차 목표 없음")).toBeVisible();
  });

  test("409 충돌은 toast를 띄우고 입력을 유지한다", async ({ page }) => {
    const fixture = await setupFixture(
      page,
      new Map([
        [
          CHAPTER_A,
          [{ goal_version: 1, goal: { emotion_goal: "저장본 v1" }, episode_purpose: "serial", base_manuscript_revision: 3 }],
        ],
      ]),
    );
    await openEditorAndPanel(page);
    await expect(page.getByLabel("감정 목표")).toHaveValue("저장본 v1");

    // 다른 탭이 먼저 저장해 서버 버전이 v2가 된 상황을 UI 조회 이후에 시뮬레이션
    const store = fixture.goals.get(CHAPTER_A)!;
    store.current = { goal_version: 2, goal: { emotion_goal: "저장본 v2" }, episode_purpose: "serial", base_manuscript_revision: 3, created_at: NOW, updated_at: NOW };
    store.revisions.push({ id: 2, goal_version: 2, goal: { emotion_goal: "저장본 v2" }, episode_purpose: "serial", base_manuscript_revision: 3, restored_from: null, created_at: NOW });

    await page.getByLabel("감정 목표").fill("사용자 신규 입력");
    const saveRequest = page.waitForRequest((req) => req.method() === "PUT" && req.url().includes("/goal"));
    await page.getByRole("button", { name: "목표 저장" }).click();
    expect((await saveRequest).postDataJSON()).toMatchObject({ expected_goal_version: 1 });
    await expect(page.getByText(/먼저 저장되었습니다/)).toBeVisible();
    await expect(page.getByLabel("감정 목표")).toHaveValue("사용자 신규 입력");
  });

  test("이력 목록에서 복원하면 POST restore로 새 버전이 기록되고 폼이 갱신된다", async ({ page }) => {
    const fixture = await setupFixture(
      page,
      new Map([
        [
          CHAPTER_A,
          [
            { goal_version: 1, goal: { emotion_goal: "과거 목표 v1" }, episode_purpose: "serial", base_manuscript_revision: 1 },
            { goal_version: 2, goal: { emotion_goal: "현재 목표 v2" }, episode_purpose: "serial", base_manuscript_revision: 3 },
          ],
        ],
      ]),
    );
    await openEditorAndPanel(page);
    await expect(page.getByLabel("감정 목표")).toHaveValue("현재 목표 v2");

    await page.getByRole("button", { name: /이력/ }).click();
    await expect(page.getByRole("dialog", { name: "회차 목표 이력" })).toBeVisible();
    await expect(page.getByText("과거 목표 v1")).toBeVisible();
    page.on("dialog", (d) => void d.accept());
    const restoreRequest = page.waitForRequest((req) => req.method() === "POST" && req.url().includes("/goal/restore"));
    // 최신순 정렬 — "과거 목표 v1" 행의 복원 버튼을 클릭한다(현재 v2 행은 비활성)
    await page.locator("li").filter({ hasText: "과거 목표 v1" }).getByRole("button", { name: "이 버전으로 복원" }).click();
    const request = await restoreRequest;
    expect(request.postDataJSON()).toMatchObject({ goal_version: 1, expected_goal_version: 2 });
    await expect(page.getByLabel("저장된 회차 목표 v3")).toBeVisible();
    await expect(page.getByLabel("감정 목표")).toHaveValue("과거 목표 v1");
    expect(fixture.restores).toHaveLength(1);
  });

  test("삭제 확인 후 DELETE가 호출되고 미저장 상태로 돌아간다", async ({ page }) => {
    const fixture = await setupFixture(
      page,
      new Map([
        [CHAPTER_A, [{ goal_version: 1, goal: { emotion_goal: "삭제 대상" }, episode_purpose: "serial", base_manuscript_revision: 3 }]],
      ]),
    );
    await openEditorAndPanel(page);
    await expect(page.getByLabel("저장된 회차 목표 v1")).toBeVisible();

    await page.getByRole("button", { name: "삭제" }).click();
    await page.getByRole("button", { name: "확인" }).click();
    await expect.poll(() => fixture.deletes.length).toBe(1);
    await expect(page.getByLabel("저장된 회차 목표 없음")).toBeVisible();
    // 이력은 보존 — 이력 버튼에 개수가 남는다
    await expect(page.getByRole("button", { name: /이력 \(1\)/ })).toBeVisible();
  });

  test("패널 열림 상태의 접근성 위반(serious/critical)이 없다", async ({ page }) => {
    await setupFixture(
      page,
      new Map([
        [CHAPTER_A, [{ goal_version: 1, goal: { emotion_goal: "a11y 목표" }, episode_purpose: "serial", base_manuscript_revision: 3 }]],
      ]),
    );
    await openEditorAndPanel(page);
    await page.getByRole("button", { name: /이력/ }).click();
    await expect(page.getByRole("dialog", { name: "회차 목표 이력" })).toBeVisible();
    const scan = await new AxeBuilder({ page }).analyze();
    expect(
      scan.violations.filter((v) => v.impact === "critical" || v.impact === "serious"),
    ).toHaveLength(0);
  });
});
