import { expect, test, type Page, type Route } from '@playwright/test';

type Chapter = {
  id: number;
  project_id: number;
  volume: number | null;
  sort_order: number;
  title: string;
  status: '초고' | '수정중' | '완료';
  word_count_cache: number;
  memo: string | null;
  revision: number;
  content_md: string;
  created_at: string;
  updated_at: string;
};

type HeldRoute = { route: Route; body: any; chapterId: number };
type HeldCanon = { route: Route; body: any };

type FixtureState = {
  chapters: Map<number, Chapter>;
  writes: Array<{ chapterId: number; body: any }>;
  heldWrites: HeldRoute[];
  generateRequests: any[];
  parallelRequests: any[];
  canonRequests: any[];
  heldCanons: HeldCanon[];
  holdCanon: boolean;
  qualityRequests: string[];
  failNextWrite: boolean;
};

const PROJECT_ID = 1;
const FIRST_CHAPTER_ID = 10;
const SECOND_CHAPTER_ID = 11;
const FIRST_REVISION = 3;
const CHAR_A = 201;
const CHAR_B = 202;
const FORESHADOW_ID = 301;

function now() { return '2026-09-08T00:00:00.000Z'; }

function chapter(id: number, title: string, content_md: string, revision: number): Chapter {
  return {
    id,
    project_id: PROJECT_ID,
    volume: 1,
    sort_order: id === FIRST_CHAPTER_ID ? 1 : 2,
    title,
    status: '초고',
    word_count_cache: content_md.replace(/\s/g, '').length,
    memo: null,
    revision,
    content_md,
    created_at: now(),
    updated_at: now(),
  };
}

function meta(c: Chapter) {
  const { content_md: _content, ...rest } = c;
  return rest;
}

function sse(events: Array<[string, unknown | string]>) {
  return events
    .map(([event, data]) => `event: ${event}\ndata: ${typeof data === 'string' ? data : JSON.stringify(data)}\n\n`)
    .join('');
}

async function installStoreHandle(page: Page) {
  await page.addScriptTag({
    type: 'module',
    content: `import { useAiPanelStore } from '/src/stores/aiPanelStore.ts'; window.__aiPanelStore = useAiPanelStore;`,
  });
}

async function selectTwoCharactersForAi(page: Page) {
  await installStoreHandle(page);
  await page.evaluate(([a, b]) => {
    const store = (window as any).__aiPanelStore;
    store.getState().setContext({ characterIds: [a, b], includeCharacters: true });
  }, [CHAR_A, CHAR_B]);
}

async function setupFixture(page: Page): Promise<FixtureState> {
  const state: FixtureState = {
    chapters: new Map<number, Chapter>([
      [FIRST_CHAPTER_ID, chapter(FIRST_CHAPTER_ID, '1화', '첫 회차 서버 원고는 본문 opt-out 때 보내면 안 된다.', FIRST_REVISION)],
      [SECOND_CHAPTER_ID, chapter(SECOND_CHAPTER_ID, '2화', '두 번째 회차 원고', 1)],
    ]),
    writes: [],
    heldWrites: [],
    generateRequests: [],
    parallelRequests: [],
    canonRequests: [],
    heldCanons: [],
    holdCanon: false,
    qualityRequests: [],
    failNextWrite: false,
  };

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    const method = route.request().method();
    const json = (status: number, body: unknown) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    const requestBody = () => JSON.parse(route.request().postData() ?? '{}');

    if (method === 'GET' && path === '/projects') {
      return json(200, [{
        id: PROJECT_ID,
        title: 'AI 컨텍스트 UI 픽스처',
        genre: null,
        synopsis: null,
        platform_note: null,
        created_at: now(),
        updated_at: now(),
        chapter_count: 2,
        total_chars: 0,
      }]);
    }
    if (method === 'GET' && path === `/projects/${PROJECT_ID}/chapters`) {
      return json(200, [...state.chapters.values()].map(meta));
    }
    const chapterMatch = path.match(/^\/chapters\/(\d+)$/);
    if (method === 'GET' && chapterMatch) {
      const c = state.chapters.get(Number(chapterMatch[1]));
      return c ? json(200, c) : json(404, { detail: 'not found' });
    }
    if (method === 'PATCH' && chapterMatch) {
      const id = Number(chapterMatch[1]);
      const current = state.chapters.get(id);
      if (!current) return json(404, { detail: 'not found' });
      const next = { ...current, ...requestBody(), updated_at: now() };
      state.chapters.set(id, next);
      return json(200, next);
    }
    const contentMatch = path.match(/^\/chapters\/(\d+)\/content$/);
    if (method === 'PUT' && contentMatch) {
      const chapterId = Number(contentMatch[1]);
      const body = requestBody();
      state.writes.push({ chapterId, body });
      if (state.failNextWrite) {
        state.failNextWrite = false;
        return json(503, { detail: 'save failed before provider' });
      }
      state.heldWrites.push({ route, body, chapterId });
      return;
    }
    if (method === 'GET' && path === '/ai/endpoints') {
      return json(200, [{
        id: 1,
        name: 'FixtureLLM',
        base_url: 'http://fixture.invalid/v1',
        api_key: '********',
        default_model: 'fixture-model',
        temperature: 0.7,
        reasoning_effort: null,
        is_default: true,
        created_at: now(),
        updated_at: now(),
      }]);
    }
    if (method === 'GET' && path === '/ai/endpoints/1/models') {
      return json(200, { data: [{ id: 'fixture-model' }] });
    }
    if (method === 'GET' && path === '/ai/presets') return json(200, []);
    if (method === 'GET' && path === `/chapters/${FIRST_CHAPTER_ID}/scenes`) return json(200, []);
    if (method === 'GET' && path === `/chapters/${SECOND_CHAPTER_ID}/scenes`) return json(200, []);
    if (method === 'GET' && path === `/projects/${PROJECT_ID}/foreshadows/match`) return json(200, []);
    if (method === 'GET' && path === `/projects/${PROJECT_ID}/foreshadows`) {
      expect(url.searchParams.get('status_filter')).toBe('설치');
      return json(200, [{ id: FORESHADOW_ID, title: '검의 진짜 주인', status: '설치' }]);
    }
    if (method === 'POST' && path === '/ai/generate') {
      state.generateRequests.push(requestBody());
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: sse([
          ['start', { model: 'fixture-model', injected_lore: [], injected_foreshadows: [], injected_outline: null, context_metadata: { project_id: PROJECT_ID, chapter_id: FIRST_CHAPTER_ID } }],
          ['message', { delta: 'AI_CONTEXT_UI_DRAFT' }],
          ['done', '[DONE]'],
        ]),
      });
    }
    if (method === 'POST' && path === '/ai/generate-parallel') {
      state.parallelRequests.push(requestBody());
      return route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream' }, body: sse([['parallel_start', { model: 'fixture-model', worker_limit: 2, injected_lore: [], injected_foreshadows: [], injected_outline: null, context_metadata: {} }], ['message', { delta: 'AI_CONTEXT_UI_PARALLEL' }], ['done', '[DONE]']]) });
    }
    if (method === 'POST' && path === '/canon-check') {
      const body = requestBody();
      state.canonRequests.push(body);
      if (state.holdCanon) {
        state.heldCanons.push({ route, body });
        return;
      }
      return json(200, {
        run_id: 501 + state.canonRequests.length,
        chapter_id: body.chapter_id,
        model: 'fixture-model',
        issues: [{ quote: `CURRENT_CANON_QUOTE_${body.chapter_id}`, reason: 'current result', severity: 'warn' }],
        checked_context: {
          characters: 2,
          lore: 0,
          foreshadows: 1,
          audience_known: 0,
          checked_input_revision: body.expected_revision,
          checked_input_hash: `hash-${body.chapter_id}-${body.expected_revision}`,
        },
      });
    }
    if (method === 'GET' && path === '/canon-check/runs') return json(200, []);
    if (method === 'GET' && path === `/chapters/${FIRST_CHAPTER_ID}/quality`) {
      state.qualityRequests.push(url.search);
      return json(200, {
        chapter_id: FIRST_CHAPTER_ID,
        score: 91,
        metrics: {
          chars_novelpia: 100,
          dialogue_ratio: 0,
          avg_para_chars: 100,
          ending_repeat_per_1k: 0,
          connector_per_1k: 0,
          para_opener_variety: 1,
          hook_present: false,
          hook_score_applicable: false,
          para_count: 1,
        },
        suggestions: [],
        suggested_preset_names: [],
      });
    }
    if (method === 'GET' && path === `/chapters/${FIRST_CHAPTER_ID}/quality/history`) return json(200, []);

    return json(599, { detail: `Unexpected API request in ai-context fixture: ${method} ${path}${url.search}` });
  });

  return state;
}

async function fulfillNextSave(state: FixtureState, revision: number) {
  await expect.poll(() => state.heldWrites.length).toBeGreaterThan(0);
  const held = state.heldWrites.shift()!;
  const current = state.chapters.get(held.chapterId)!;
  const next = { ...current, content_md: held.body.content_md, revision, updated_at: now() };
  state.chapters.set(held.chapterId, next);
  await held.route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(next) });
}

async function fulfillNextCanon(state: FixtureState, quote: string) {
  await expect.poll(() => state.heldCanons.length).toBeGreaterThan(0);
  const held = state.heldCanons.shift()!;
  await held.route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
    run_id: 900 + state.heldCanons.length,
    chapter_id: held.body.chapter_id,
    model: 'fixture-model',
    issues: [{ quote, reason: 'delayed result', severity: 'warn' }],
    checked_context: {
      characters: 0,
      lore: 0,
      foreshadows: 0,
      audience_known: 0,
      checked_input_revision: held.body.expected_revision,
      checked_input_hash: `hash-${held.body.chapter_id}-${held.body.expected_revision}`,
    },
  }) });
}

async function fulfillNextCanonFailure(state: FixtureState, detail: string) {
  await expect.poll(() => state.heldCanons.length).toBeGreaterThan(0);
  const held = state.heldCanons.shift()!;
  await held.route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail }) });
}

async function openEditorAndPanel(page: Page) {
  await page.goto(`/projects/${PROJECT_ID}/write`);
  await expect(page.locator('.cm-content')).toBeVisible();
  await page.getByRole('button', { name: 'AI 패널' }).click();
  await expect(page.getByText('호출 컨텍스트')).toBeVisible();
}

test.describe.serial('AI-context Task3 fixture UI boundaries', () => {
  test('generation waits for flush and sends one complete pre-await snapshot with saved revision', async ({ page }) => {
    const state = await setupFixture(page);
    await page.goto(`/projects/${PROJECT_ID}/write`);
    await expect(page.locator('.cm-content')).toBeVisible();
    await page.locator('.cm-content').click();
    await page.locator('.cm-content').fill('flush 전 로컬 원고');
    await page.getByRole('button', { name: 'AI 패널' }).click();
    await expect(page.getByText('호출 컨텍스트')).toBeVisible();
    await selectTwoCharactersForAi(page);
    await page.getByLabel('프롬프트 직접 입력').fill('원래 프롬프트');
    await page.getByLabel(/현재 회차 본문 포함/).uncheck();
    await page.getByLabel('회차 목적').selectOption('series_finale');
    await page.getByLabel('선택 인물 관계 포함').check();
    await page.getByRole('button', { name: /복선 회수 승인 선택/ }).click();
    await page.getByLabel(/이번 요청에서 회수\/공개 허용/).check();
    await page.getByRole('button', { name: /이번 화 브리프/ }).click();
    await page.getByLabel('감정 목표').fill('닫힘의 정서');
    await page.getByLabel(/핵심 사건/).fill('왕좌 포기');
    await page.getByLabel(/인물 선택/).fill('복수보다 구출을 택한다');
    await page.getByLabel('대가').fill('왕좌를 포기한다');
    await page.getByLabel(/금지사항/).fill('새 갈등을 열지 않는다');
    await page.getByLabel('엔딩 의도').fill('두 인물이 선택의 대가를 받아들이고 끝낸다');

    await page.getByRole('button', { name: '✨ 생성 시작' }).click();
    await page.getByRole('button', { name: '✨ 생성 시작' }).click();
    await expect.poll(() => state.heldWrites.length).toBe(1);
    expect(state.generateRequests).toHaveLength(0);

    await page.getByLabel('프롬프트 직접 입력').fill('변경된 프롬프트');
    await page.getByLabel('회차 목적').selectOption('serial');
    await page.getByLabel(/현재 회차 본문 포함/).check();
    await fulfillNextSave(state, 4);
    await expect(page.locator('pre')).toContainText('AI_CONTEXT_UI_DRAFT');

    expect(state.generateRequests).toHaveLength(1);
    const request = state.generateRequests[0];
    expect(request.prompt_override).toBe('원래 프롬프트');
    expect(request.context).toMatchObject({
      project_id: PROJECT_ID,
      chapter_id: FIRST_CHAPTER_ID,
      include_chapter_content: false,
      expected_revision: 4,
      episode_purpose: 'series_finale',
      approved_foreshadow_ids: [FORESHADOW_ID],
      include_relationships: true,
      character_ids: [CHAR_A, CHAR_B],
    });
    expect(request.context.brief).toMatchObject({
      ending_intent: '두 인물이 선택의 대가를 받아들이고 끝낸다',
    });
    expect(request.context.brief.next_hook).toBeUndefined();
  });

  test('failed flush, close, and navigation cancel pending provider starts', async ({ page }) => {
    const state = await setupFixture(page);
    await page.goto(`/projects/${PROJECT_ID}/write`);
    await expect(page.locator('.cm-content')).toBeVisible();
    await page.locator('.cm-content').click();
    await page.locator('.cm-content').fill('저장 실패 원고');
    await page.getByRole('button', { name: 'AI 패널' }).click();
    await expect(page.getByText('호출 컨텍스트')).toBeVisible();
    await page.getByLabel('프롬프트 직접 입력').fill('실패 시 시작 금지');
    state.failNextWrite = true;
    await page.getByRole('button', { name: '✨ 생성 시작' }).click();
    await expect.poll(() => state.writes.length).toBe(1);
    await expect.poll(() => state.generateRequests.length).toBe(0);

    await page.getByRole('button', { name: '패널 닫기' }).click();
    await page.locator('.cm-content').click();
    await page.locator('.cm-content').fill('닫기 취소 원고');
    await page.getByRole('button', { name: 'AI 패널' }).click();
    await page.getByRole('button', { name: '✨ 생성 시작' }).click();
    await expect.poll(() => state.heldWrites.length).toBe(1);
    await page.getByRole('button', { name: '패널 닫기' }).click();
    await fulfillNextSave(state, 5);
    await expect.poll(() => state.generateRequests.length).toBe(0);

    await page.getByRole('button', { name: 'AI 패널' }).click();
    await page.getByLabel('프롬프트 직접 입력').fill('네비게이션 취소');
    await page.getByRole('button', { name: '패널 닫기' }).click();
    await page.locator('.cm-content').click();
    await page.locator('.cm-content').fill('이동 취소 원고');
    await page.getByRole('button', { name: 'AI 패널' }).click();
    await page.getByRole('button', { name: '✨ 생성 시작' }).click();
    await expect.poll(() => state.heldWrites.length).toBe(1);
    await page.goto('/');
    await fulfillNextSave(state, 6);
    await expect.poll(() => state.generateRequests.length).toBe(0);
  });

  test('result from another chapter blocks insert and replace but keeps copy enabled', async ({ page }) => {
    const state = await setupFixture(page);
    await openEditorAndPanel(page);
    await page.getByLabel('프롬프트 직접 입력').fill('origin guard');
    await page.getByRole('button', { name: '✨ 생성 시작' }).click();
    await expect(page.locator('pre')).toContainText('AI_CONTEXT_UI_DRAFT');
    expect(state.generateRequests).toHaveLength(1);

    await page.getByRole('button', { name: '패널 닫기' }).click();
    await page.getByRole('button', { name: /2화/ }).click();
    await expect(page.locator('.cm-content')).toBeVisible();
    await page.getByRole('button', { name: 'AI 패널' }).click();
    await expect(page.getByRole('button', { name: /⧉ 복사/ })).toBeEnabled();
    await expect(page.getByRole('button', { name: /↪ 끼워넣기/ })).toBeDisabled();
    await expect(page.getByRole('button', { name: /⤳ 선택 교체/ })).toBeDisabled();
  });

  test('canon and quality use shared purpose, payoff, relationship, flush revision, and hook applicability', async ({ page }) => {
    const state = await setupFixture(page);
    await openEditorAndPanel(page);
    await selectTwoCharactersForAi(page);
    await page.getByLabel('회차 목적').selectOption('series_finale');
    await page.getByLabel('선택 인물 관계 포함').check();
    await page.getByRole('button', { name: /복선 회수 승인 선택/ }).click();
    await page.getByLabel(/이번 요청에서 회수\/공개 허용/).check();
    await page.getByRole('button', { name: '패널 닫기' }).click();

    await page.getByRole('button', { name: '품질 진단' }).click();
    await expect(page.getByText('해당 없음')).toBeVisible();
    expect(state.qualityRequests.some((q) => q.includes('episode_purpose=series_finale'))).toBeTruthy();
    await page.keyboard.press('Escape');

    await page.locator('.cm-content').click();
    await page.locator('.cm-content').fill('canon flush 원고');
    await page.getByRole('button', { name: '모순 검사' }).click();
    await page.getByRole('button', { name: /검사 실행/ }).click();
    await expect.poll(() => state.heldWrites.length).toBe(1);
    expect(state.canonRequests).toHaveLength(0);
    await fulfillNextSave(state, 7);
    await expect(page.getByText(/검사 대상/)).toBeVisible();

    expect(state.canonRequests).toHaveLength(1);
    expect(state.canonRequests[0]).toMatchObject({
      chapter_id: FIRST_CHAPTER_ID,
      expected_revision: 7,
      episode_purpose: 'series_finale',
      approved_foreshadow_ids: [FORESHADOW_ID],
      include_relationships: true,
    });
  });

  test('delayed canon result from chapter A is ignored after navigating to chapter B', async ({ page }) => {
    const state = await setupFixture(page);
    state.holdCanon = true;
    await page.goto(`/projects/${PROJECT_ID}/write`);
    await expect(page.locator('.cm-content')).toBeVisible();
    await page.getByRole('button', { name: '모순 검사' }).click();
    await page.getByRole('button', { name: /검사 실행/ }).click();
    await expect.poll(() => state.canonRequests.length).toBe(1);
    expect(state.canonRequests[0].chapter_id).toBe(FIRST_CHAPTER_ID);
    expect(state.canonRequests[0].expected_revision).toBe(FIRST_REVISION);

    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: /2화/ }).click();
    await expect(page.locator('.cm-content')).toContainText('두 번째 회차 원고');
    await fulfillNextCanon(state, 'OLD_STALE_QUOTE');

    await page.getByRole('button', { name: '모순 검사' }).click();
    await expect(page.getByText('OLD_STALE_QUOTE')).not.toBeVisible();
  });

  test('closing A, visiting B, and returning A does not revive a cancelled canon result', async ({ page }) => {
    const state = await setupFixture(page);
    state.holdCanon = true;
    await page.goto(`/projects/${PROJECT_ID}/write`);
    await expect(page.locator('.cm-content')).toBeVisible();
    await page.getByRole('button', { name: '모순 검사' }).click();
    await page.getByRole('button', { name: /검사 실행/ }).click();
    await expect.poll(() => state.heldCanons.length).toBe(1);
    await page.keyboard.press('Escape');

    await page.getByRole('button', { name: /2화/ }).click();
    await expect(page.locator('.cm-content')).toContainText('두 번째 회차 원고');
    await page.getByRole('button', { name: /1화/ }).click();
    await expect(page.locator('.cm-content')).toContainText('첫 회차 서버 원고');
    await fulfillNextCanon(state, 'A_RETURN_STALE_QUOTE');

    await page.getByRole('button', { name: '모순 검사' }).click();
    await expect(page.getByText('A_RETURN_STALE_QUOTE')).not.toBeVisible();
  });

  test('older delayed canon success or failure cannot override a newer completed canon result', async ({ page }) => {
    const state = await setupFixture(page);
    state.holdCanon = true;
    await page.goto(`/projects/${PROJECT_ID}/write`);
    await expect(page.locator('.cm-content')).toBeVisible();
    await page.getByRole('button', { name: '모순 검사' }).click();
    await page.getByRole('button', { name: /검사 실행/ }).click();
    await expect.poll(() => state.heldCanons.length).toBe(1);
    await page.keyboard.press('Escape');

    state.holdCanon = false;
    await page.getByRole('button', { name: /2화/ }).click();
    await page.getByRole('button', { name: '모순 검사' }).click();
    await page.getByRole('button', { name: /검사 실행/ }).click();
    await expect(page.getByText(`CURRENT_CANON_QUOTE_${SECOND_CHAPTER_ID}`)).toBeVisible();
    await expect(page.getByText(/검사 기준/)).toContainText('rev 1');
    expect(state.canonRequests[1]).toMatchObject({ chapter_id: SECOND_CHAPTER_ID, expected_revision: 1 });

    await fulfillNextCanon(state, 'OLDER_SUCCESS_AFTER_NEWER');
    await expect(page.getByText(`CURRENT_CANON_QUOTE_${SECOND_CHAPTER_ID}`)).toBeVisible();
    await expect(page.getByText('OLDER_SUCCESS_AFTER_NEWER')).not.toBeVisible();

    state.holdCanon = true;
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: /1화/ }).click();
    await page.getByRole('button', { name: '모순 검사' }).click();
    await page.getByRole('button', { name: /검사 실행/ }).click();
    await expect.poll(() => state.heldCanons.length).toBe(1);
    await page.keyboard.press('Escape');
    state.holdCanon = false;
    await page.getByRole('button', { name: /2화/ }).click();
    await page.getByRole('button', { name: '모순 검사' }).click();
    await page.getByRole('button', { name: /검사 실행/ }).click();
    await expect(page.getByText(`CURRENT_CANON_QUOTE_${SECOND_CHAPTER_ID}`)).toBeVisible();
    await fulfillNextCanonFailure(state, 'OLDER_FAILURE_AFTER_NEWER');
    await expect(page.getByText(`CURRENT_CANON_QUOTE_${SECOND_CHAPTER_ID}`)).toBeVisible();
    await expect(page.getByText(/OLDER_FAILURE_AFTER_NEWER/)).not.toBeVisible();
  });

});
