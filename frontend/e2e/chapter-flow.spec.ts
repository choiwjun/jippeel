import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route } from "@playwright/test";
import { expect, test } from "./coverage-test";

/**
 * D03-1 회차 집필 흐름(flow_stage) — fixture-only UI 검증.
 * 모든 /api/v1 트래픽은 이 파일의 인메모리 상태로 응답한다(미모킹 요청은 tripwire가 잡는다).
 */

type FlowStage = "planning" | "writing" | "revising" | "confirmed";

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

type FlowEvent = {
  id: number;
  chapter_id: number;
  from_stage: FlowStage;
  to_stage: FlowStage;
  goal_version: number | null;
  manuscript_revision: number;
  created_at: string;
};

const NOW = "2026-09-13T00:00:00.000Z";
const PROJECT_ID = 1;
const CHAPTER_ID = 10;

const ALLOWED: Record<FlowStage, FlowStage[]> = {
  planning: ["writing"],
  writing: ["revising"],
  revising: ["writing", "confirmed"],
  confirmed: ["revising"],
};

function chapter(): Chapter {
  return {
    id: CHAPTER_ID,
    project_id: PROJECT_ID,
    volume: 1,
    sort_order: 1,
    title: "1화",
    status: "초고",
    word_count_cache: 10,
    memo: null,
    revision: 3,
    content_md: "1화 본문",
    created_at: NOW,
    updated_at: NOW,
  };
}

type FlowFixture = {
  ch: Chapter;
  stage: FlowStage;
  events: FlowEvent[];
  nextEventId: number;
  goalVersion: number | null;
  pendingRefineRuns: number;
  scenes: Array<{ id: number; sort_order: number; title: string; content_md: string }>;
  posts: Array<{ to_stage: FlowStage; expected_flow_stage: FlowStage }>;
  failNextWith409: boolean;
};

function flowOut(fx: FlowFixture) {
  return {
    chapter_id: CHAPTER_ID,
    project_id: PROJECT_ID,
    flow_stage: fx.stage,
    last_event: fx.events.length ? fx.events[fx.events.length - 1] : null,
    current_goal_version: fx.goalVersion,
    current_chapter_revision: fx.ch.revision,
  };
}

async function setupFixture(
  page: Page,
  seed?: {
    stage?: FlowStage;
    goalVersion?: number | null;
    event?: Partial<FlowEvent>;
    pendingRefineRuns?: number;
    scenes?: Array<{ id: number; sort_order: number; title: string; content_md: string }>;
    revision?: number;
  },
): Promise<FlowFixture> {
  const fx: FlowFixture = {
    ch: chapter(),
    stage: seed?.stage ?? "planning",
    events: seed?.event
      ? [{
          id: 1,
          chapter_id: CHAPTER_ID,
          from_stage: "planning",
          to_stage: seed.stage ?? "writing",
          goal_version: null,
          manuscript_revision: 3,
          created_at: NOW,
          ...seed.event,
        }]
      : [],
    nextEventId: 1,
    goalVersion: seed?.goalVersion ?? null,
    pendingRefineRuns: seed?.pendingRefineRuns ?? 0,
    scenes: seed?.scenes ?? [],
    posts: [],
    failNextWith409: false,
  };
  if (seed?.revision !== undefined) fx.ch.revision = seed.revision;
  if (fx.events.length) fx.nextEventId = 2;

  await page.context().route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    const body = () => JSON.parse(route.request().postData() ?? "{}");

    if (method === "GET" && path === `/projects/${PROJECT_ID}/chapters`) {
      const { content_md: _c, ...meta } = fx.ch;
      return json(200, [meta]);
    }
    if (method === "GET" && path === `/chapters/${CHAPTER_ID}`) return json(200, fx.ch);

    const flowMatch = path.match(/^\/chapters\/(\d+)\/flow$/);
    if (method === "GET" && flowMatch) {
      return Number(flowMatch[1]) === CHAPTER_ID ? json(200, flowOut(fx)) : json(404, { detail: "not found" });
    }
    const transitionMatch = path.match(/^\/chapters\/(\d+)\/flow\/transition$/);
    if (method === "POST" && transitionMatch) {
      if (Number(transitionMatch[1]) !== CHAPTER_ID) return json(404, { detail: "not found" });
      const req = body();
      fx.posts.push(req);
      if (!("expected_flow_stage" in req) || !("to_stage" in req)) {
        return json(422, { detail: "expected_flow_stage와 to_stage는 필수입니다." });
      }
      if (fx.failNextWith409) {
        fx.failNextWith409 = false;
        fx.stage = "writing"; // 다른 곳에서 먼저 전이된 상태
        return json(409, {
          detail: { code: "flow_stage_conflict", message: "conflict", current_flow_stage: fx.stage },
        });
      }
      if (req.expected_flow_stage !== fx.stage) {
        return json(409, {
          detail: { code: "flow_stage_conflict", message: "conflict", current_flow_stage: fx.stage },
        });
      }
      if (!ALLOWED[fx.stage].includes(req.to_stage)) {
        return json(422, { detail: "허용되지 않는 흐름 전이입니다." });
      }
      const event: FlowEvent = {
        id: fx.nextEventId++,
        chapter_id: CHAPTER_ID,
        from_stage: fx.stage,
        to_stage: req.to_stage,
        goal_version: fx.goalVersion,
        manuscript_revision: fx.ch.revision,
        created_at: NOW,
      };
      fx.events.push(event);
      fx.stage = req.to_stage;
      return json(200, flowOut(fx));
    }
    const eventsMatch = path.match(/^\/chapters\/(\d+)\/flow\/events$/);
    if (method === "GET" && eventsMatch) {
      return Number(eventsMatch[1]) === CHAPTER_ID
        ? json(200, [...fx.events].reverse())
        : json(404, { detail: "not found" });
    }
    const resumeMatch = path.match(/^\/chapters\/(\d+)\/resume$/);
    if (method === "GET" && resumeMatch) {
      if (Number(resumeMatch[1]) !== CHAPTER_ID) return json(404, { detail: "not found" });
      const last = fx.events.length ? fx.events[fx.events.length - 1] : null;
      const nextScene = [...fx.scenes]
        .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
        .find((s) => !(s.content_md ?? "").trim()) ?? null;
      return json(200, {
        chapter_id: CHAPTER_ID,
        project_id: PROJECT_ID,
        flow_stage: fx.stage,
        last_event: last,
        current_goal_version: fx.goalVersion,
        current_chapter_revision: fx.ch.revision,
        goal_changed_since_transition: last !== null && fx.goalVersion !== last.goal_version,
        manuscript_changed_since_transition:
          last !== null && fx.ch.revision !== last.manuscript_revision,
        pending_refine_runs: fx.pendingRefineRuns,
        next_scene: nextScene
          ? { id: nextScene.id, sort_order: nextScene.sort_order, title: nextScene.title }
          : null,
        scene_count: fx.scenes.length,
      });
    }

    if (method === "GET" && path === "/ai/presets") return json(200, []);
    if (method === "GET" && /^\/chapters\/\d+\/scenes$/.test(path)) return json(200, []);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/foreshadows/match`) return json(200, []);
    if (method === "GET" && path === `/projects/${PROJECT_ID}/foreshadows`) return json(200, []);
    if (method === "GET" && /^\/chapters\/\d+\/goal$/.test(path)) {
      return json(200, {
        chapter_id: CHAPTER_ID,
        project_id: PROJECT_ID,
        goal: null,
        current_chapter_revision: fx.ch.revision,
        history_count: 0,
      });
    }
    // D03-4: 브리프 섹션이 열리면 근거 링크를 조회한다.
    if (method === "GET" && /^\/chapters\/\d+\/evidence-links$/.test(path))
      return json(200, { chapter_id: CHAPTER_ID, links: [] });

    return json(599, { detail: `Unexpected API request in chapter-flow fixture: ${method} ${path}${url.search}` });
  });

  return fx;
}

async function openEditor(page: Page) {
  await page.goto(`/projects/${PROJECT_ID}/write`);
  await expect(page.locator(".cm-content")).toBeVisible();
}

test.describe.serial("D03-1 회차 집필 흐름 fixture", () => {
  test("기획 단계 배지와 허용 전이(집필로)만 표시된다", async ({ page }) => {
    await setupFixture(page);
    await openEditor(page);

    await expect(page.getByLabel("집필 흐름 단계: 기획")).toBeVisible();
    const select = page.getByLabel("집필 흐름 단계 전이");
    await expect(select).toBeVisible();
    const options = await select.locator("option").allTextContents();
    expect(options).toContain("집필(으)로");
    expect(options).not.toContain("퇴고(으)로");
    expect(options).not.toContain("집필 확정(으)로");
  });

  test("전이 선택은 expected_flow_stage와 함께 POST하고 배지·앵커를 갱신한다", async ({ page }) => {
    const fx = await setupFixture(page, { goalVersion: 2 });
    await openEditor(page);

    await page.getByLabel("집필 흐름 단계 전이").selectOption("writing");
    await expect(page.getByLabel("집필 흐름 단계: 집필")).toBeVisible();
    // 앵커: 목표 v2 · 원고 r3 기준
    await expect(page.getByText("목표 v2 · 원고 r3 기준")).toBeVisible();
    expect(fx.posts).toEqual([{ to_stage: "writing", expected_flow_stage: "planning" }]);
  });

  test("목표 저장본이 없으면 앵커에 원고 revision만 표시한다", async ({ page }) => {
    await setupFixture(page);
    await openEditor(page);
    await page.getByLabel("집필 흐름 단계 전이").selectOption("writing");
    await expect(page.getByText("원고 r3 기준")).toBeVisible();
    await expect(page.getByText(/목표 v/)).not.toBeVisible();
  });

  test("409 충돌은 toast를 띄우고 최신 상태를 다시 불러온다", async ({ page }) => {
    const fx = await setupFixture(page);
    await openEditor(page);
    fx.failNextWith409 = true;

    await page.getByLabel("집필 흐름 단계 전이").selectOption("writing");
    await expect(page.getByText(/먼저 변경되었습니다/)).toBeVisible();
    // refetch 후 실제 단계(집필)로 배지 갱신
    await expect(page.getByLabel("집필 흐름 단계: 집필")).toBeVisible();
  });

  test("confirmed는 재개(퇴고로)만 허용한다", async ({ page }) => {
    await setupFixture(page, { stage: "confirmed" });
    await openEditor(page);
    await expect(page.getByLabel("집필 흐름 단계: 집필 확정")).toBeVisible();
    const options = await page.getByLabel("집필 흐름 단계 전이").locator("option").allTextContents();
    expect(options).toContain("퇴고(으)로");
    expect(options).not.toContain("집필(으)로");
    expect(options).not.toContain("기획(으)로");
  });

  test("에디터 헤더의 접근성 위반(serious/critical)이 없다 — 배지 표시 상태 포함", async ({ page }) => {
    await setupFixture(page, {
      stage: "writing",
      goalVersion: 2,
      event: { goal_version: 1, manuscript_revision: 3 },
      revision: 5,
      pendingRefineRuns: 1,
      scenes: [{ id: 1, sort_order: 1, title: "다음", content_md: "" }],
    });
    await openEditor(page);
    await expect(page.getByLabel("집필 흐름 단계: 집필")).toBeVisible();
    await expect(page.getByText("미해결 감수 1")).toBeVisible();
    const results = await new AxeBuilder({ page }).analyze();
    const violations = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(violations).toEqual([]);
  });
});

test.describe.serial("D03-2 회차 재개 정보 fixture", () => {
  test("전이 이력이 없으면 드리프트 배지 없이 재개 정보만 표시한다", async ({ page }) => {
    await setupFixture(page);
    await openEditor(page);
    await expect(page.getByLabel("집필 흐름 단계: 기획")).toBeVisible();
    await expect(page.getByText("목표 변경됨")).not.toBeVisible();
    await expect(page.getByText("원고 변경됨")).not.toBeVisible();
    await expect(page.getByText(/미해결 감수/)).not.toBeVisible();
    await expect(page.getByText(/다음 장면:/)).not.toBeVisible();
  });

  test("목표·원고 드리프트와 미해결 감수, 다음 빈 장면을 표시한다", async ({ page }) => {
    await setupFixture(page, {
      stage: "writing",
      goalVersion: 2,
      event: { goal_version: 1, manuscript_revision: 3 },
      revision: 5,
      pendingRefineRuns: 2,
      scenes: [
        { id: 1, sort_order: 1, title: "도입", content_md: "본문" },
        { id: 2, sort_order: 2, title: "반격", content_md: "" },
      ],
    });
    await openEditor(page);

    await expect(page.getByText("목표 변경됨")).toBeVisible();
    await expect(page.getByText("원고 변경됨")).toBeVisible();
    await expect(page.getByText("미해결 감수 2")).toBeVisible();
    await expect(page.getByText("다음 장면: 반격")).toBeVisible();
  });

  test("전이 후 재개 정보가 refetch되어 드리프트가 해소된다", async ({ page }) => {
    await setupFixture(page, {
      stage: "planning",
      goalVersion: 1,
      event: { goal_version: 2, manuscript_revision: 3, to_stage: "planning" },
    });
    await openEditor(page);
    // seeded event(goal_version 2) ≠ current(1) → 드리프트 표시
    await expect(page.getByText("목표 변경됨")).toBeVisible();

    await page.getByLabel("집필 흐름 단계 전이").selectOption("writing");
    // 새 이벤트는 goal_version 1로 앵커 → invalidate 후 드리프트 해소
    await expect(page.getByText("목표 변경됨")).not.toBeVisible();
    await expect(page.getByText("목표 v1 · 원고 r3 기준")).toBeVisible();
  });

  test("장면 제목이 없으면 '무제'로 표시한다", async ({ page }) => {
    await setupFixture(page, {
      scenes: [{ id: 1, sort_order: 1, title: "", content_md: "" }],
    });
    await openEditor(page);
    await expect(page.getByText("다음 장면: 무제")).toBeVisible();
  });
});
