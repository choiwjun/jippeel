import { test, expect, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const now = '2026-10-05T00:00:00Z';
type Chapter = ReturnType<typeof chapter>;
function chapter(id: number, project_id = 1) {
  return { id, project_id, title: `회차 ${id}`, volume: 1 as number | null, sort_order: id,
    content_md: `저장 본문 ${id}`, word_count_cache: 5, revision: 1, status: '초고',
    flow_stage: 'planning', memo: '', created_at: now, updated_at: now };
}
function counts(rows: Chapter[]) {
  return { total: rows.length, written: rows.filter(c => c.word_count_cache > 0).length,
    confirmed: rows.filter(c => c.flow_stage === 'confirmed').length };
}
const unexpected = new WeakMap<Page, string[]>();
test.afterEach(async ({ page }) => expect(unexpected.get(page) ?? []).toEqual([]));

async function fixture(page: Page, count = 60) {
  const fx = {
    chapters: Array.from({ length: count }, (_, i) => chapter(i + 1)),
    writes: [] as { id: number; body: { content_md: string; expected_revision: number } }[],
    saveMode: 'ok' as 'ok' | 'hold' | 'error' | 'conflict',
    heldWrites: [] as (() => Promise<void>)[],
    holdMap: false, heldMaps: [] as (() => Promise<void>)[], mapRequests: 0,
    holdTarget: false, heldTargets: [] as (() => Promise<void>)[],
    evidenceRequests: [] as { chapter: number; view: string }[],
  };
  unexpected.set(page, []);
  await page.route('**/api/v1/**', async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    const method = route.request().method();
    const json = (status: number, body: unknown) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/auth/status') return json(200, { enabled: false, configured: false });
    if (path === '/projects') return json(200, [1, 2].map(id => ({ id, title: `작품 ${id}`, created_at: now, updated_at: now })));
    if (/^\/projects\/\d+$/.test(path)) return json(200, { id: Number(path.split('/')[2]), title: '합성 작품' });
    if (path === '/projects/1/chapters') return json(200, fx.chapters);
    if (path === '/projects/2/chapters') return json(200, [chapter(501, 2)]);
    if (/^\/projects\/\d+\/plus-status$/.test(path)) return json(200, {
      eligible: false, chapter_count: 1, chapter_count_met: false,
      done_chapter_count: 0, done_chapters_3000: 0, done_chars_met: false,
    });
    if (path === '/projects/1/story-map/evidence') {
      const cid = Number(url.searchParams.get('chapter_id'));
      const view = url.searchParams.get('view')!;
      fx.evidenceRequests.push({ chapter: cid, view });
      const c = fx.chapters.find(c => c.id === cid)!;
      const ref = (id: number) => ({ id, title: `회차 ${id}`, position: id, revision: 1, future: id > cid });
      const defaults = { from_name: null, to_name: null, planted: null, resolved: null,
        registered_status: null, disposition: null, visibility: null, source_revision: null, source: null };
      const items = view === 'relations' ? [
        { ...defaults, id: 'relation-1', kind: 'relation', label: '동료', from_name: '해온', to_name: '서리',
          excerpt: '현재 작가 설정', basis: '시점 정보 없음 · 현재 작가 설정' },
        { ...defaults, id: 'event-1-0', kind: 'relationship_change', label: '함께 싸움', from_name: '해온', to_name: '서리',
          excerpt: '대립 → 협력', basis: '작가 승인 변화 기록 · 현재 원문 해시 일치', source: ref(51) },
      ] : view === 'foreshadows' ? [
        { ...defaults, id: 'foreshadow-1', kind: 'foreshadow', label: '금빛 동전', excerpt: '등록된 설치와 실제 회수',
          basis: '작가 등록 기록', registered_status: '회수', disposition: 'resolved', planted: ref(51), resolved: ref(60) },
        { ...defaults, id: 'foreshadow-2', kind: 'foreshadow', label: '남겨진 약속', excerpt: '',
          basis: '작가 등록 기록', registered_status: '회수', disposition: 'intentional_unresolved', planted: ref(51), resolved: ref(60) },
        { ...defaults, id: 'foreshadow-3', kind: 'foreshadow', label: '별도 이야기', excerpt: '',
          basis: '작가 등록 기록', registered_status: '보류', disposition: 'side_story', planted: ref(51), resolved: ref(60) },
      ] : c.revision > 1 ? [
        { ...defaults, id: 'memory-1', kind: 'stale_memory', label: '회차 요약 #1', excerpt: '기존 요약 본문',
          basis: '근거 원고 버전·내용 변경', visibility: 'approved', source_revision: 1, source: { ...ref(cid), revision: c.revision } },
        { ...defaults, id: 'memory-2', kind: 'stale_memory', label: '요약 초안 #2', excerpt: '아직 승인하지 않은 초안',
          basis: '연결 근거 불일치', visibility: 'draft', source_revision: null },
      ] : [];
      return json(200, { project_id: 1, chapter_id: cid, chapter_revision: c.revision, view,
        total: items.length, items, offset: 0, next_offset: null });
    }
    if (path === '/projects/1/story-map') {
      fx.mapRequests++;
      const rows = [...fx.chapters].sort((a, b) => (a.volume ?? Infinity) - (b.volume ?? Infinity) || a.sort_order - b.sort_order || a.id - b.id);
      const anchorId = url.searchParams.has('anchor_id') ? Number(url.searchParams.get('anchor_id')) : rows[0]?.id;
      const index = rows.findIndex(c => c.id === anchorId);
      if (anchorId != null && index < 0) return json(404, { detail: 'chapter not found in project' });
      const scope = url.searchParams.get('scope') ?? 'near';
      const selected = scope === 'near' ? rows.slice(Math.max(0, index - 2), index + 6)
        : scope === 'volume' ? rows.filter(c => c.volume === rows[index]?.volume) : rows;
      const anchorIndex = Math.max(0, selected.findIndex(c => c.id === anchorId));
      const offset = scope === 'near' ? 0 : url.searchParams.has('offset') ? Number(url.searchParams.get('offset')) : Math.floor(anchorIndex / 25) * 25;
      const payload = { project_id: 1, anchor_id: anchorId ?? null, scope, counts: counts(selected), offset,
        next_offset: offset + 25 < selected.length ? offset + 25 : null,
        volumes: [...new Set(rows.map(c => c.volume))].map(volume => {
          const group = rows.filter(c => c.volume === volume);
          return { volume, first_chapter_id: group[0].id, ...counts(group) };
        }),
        nodes: selected.slice(offset, offset + 25).map(c => ({ id: c.id, position: rows.indexOf(c) + 1,
          volume: c.volume, title: c.title, flow_stage: c.flow_stage, word_count: c.word_count_cache,
          revision: c.revision, goal: { core_events: [`예정 사건 ${c.id}`] }, goal_version: 1,
          goal_base_revision: 1, scene_count: 0 })) };
      if (fx.holdMap) { fx.holdMap = false; fx.heldMaps.push(() => json(200, payload)); return; }
      return json(200, payload);
    }
    const content = path.match(/^\/chapters\/(\d+)\/content$/);
    if (method === 'PUT' && content) {
      const id = Number(content[1]); const c = fx.chapters.find(c => c.id === id)!;
      const body = JSON.parse(route.request().postData()!); fx.writes.push({ id, body });
      if (fx.saveMode === 'error') return json(500, { detail: '합성 저장 실패' });
      if (fx.saveMode === 'conflict') {
        c.revision++; c.content_md = '다른 창의 본문';
        return json(409, { detail: { code: 'revision_conflict', current_revision: c.revision, message: '다른 창에서 변경됨' } });
      }
      const save = async () => { c.content_md = body.content_md; c.revision++; c.word_count_cache = body.content_md.length; await json(200, c); };
      if (fx.saveMode === 'hold') { fx.heldWrites.push(save); return; }
      return save();
    }
    const detail = path.match(/^\/chapters\/(\d+)$/);
    if (method === 'GET' && detail) {
      const c = Number(detail[1]) === 501 ? chapter(501, 2) : fx.chapters.find(c => c.id === Number(detail[1]));
      if (fx.holdTarget && c?.id === 53) { fx.holdTarget = false; fx.heldTargets.push(() => json(200, c)); return; }
      return c ? json(200, c) : json(404, { detail: 'not found' });
    }
    const related = path.match(/^\/chapters\/(\d+)\/(flow|resume|goal|evidence-links)$/);
    if (method === 'GET' && related) {
      const c = fx.chapters.find(c => c.id === Number(related[1])) ?? chapter(Number(related[1]), 2);
      return json(200, { chapter_id: c.id, project_id: c.project_id, flow_stage: c.flow_stage,
        current_chapter_revision: c.revision, current_goal_version: null, last_event: null,
        goal: null, history_count: 0, links: [], pending_refine_runs: 0, scene_count: 0, next_scene: null,
        goal_changed_since_transition: false, manuscript_changed_since_transition: false });
    }
    if (method === 'GET' && (/^\/chapters\/\d+\/(scenes|generation-runs)$/.test(path)
      || /^\/projects\/\d+\/(characters|foreshadows(?:\/match)?|memories|summary-jobs|improvement-rules)$/.test(path)
      || path === '/ai/presets')) return json(200, []);
    if (method === 'GET' && /^\/projects\/\d+\/trend-pack$/.test(path)) return json(200, null);
    unexpected.get(page)!.push(`${method} ${path}`);
    return json(599, { detail: `Unexpected fixture API: ${method} ${path}` });
  });
  return fx;
}

async function open(page: Page, id = 52) {
  await page.goto(`/projects/1/write?chapter=${id}`);
  await expect(page.locator('.cm-content')).toHaveText(`저장 본문 ${id}`);
  await page.getByRole('button', { name: '스토리 지도 열기', exact: true }).click();
}
const panel = (page: Page) => page.getByRole('complementary', { name: '스토리 지도' });
async function selectNext(page: Page) {
  await panel(page).getByRole('button').filter({ hasText: '53. 회차 53' }).click();
}

test('권·전체 보기 전환은 현재 회차가 포함된 페이지를 연다', async ({ page }) => {
  await fixture(page); await open(page);
  for (const name of ['선택 권', '작품 전체']) {
    await panel(page).getByRole('button', { name, exact: true }).click();
    await expect(panel(page).locator('[aria-current="step"]')).toContainText('회차 52');
    await expect(panel(page).getByText('51–60 / 60회', { exact: true })).toBeVisible();
  }
  await panel(page).getByRole('button', { name: '이전', exact: true }).click();
  await expect(panel(page).getByText('26–50 / 60회', { exact: true })).toBeVisible();
});

test('한 번 저장하면 지도도 한 번만 다시 조회한다', async ({ page }) => {
  const fx = await fixture(page); await open(page);
  await expect(panel(page).locator('[aria-current="step"]')).toBeVisible();
  const initial = fx.mapRequests;
  await page.locator('.cm-content').fill('새 원고 한 번');
  await expect.poll(() => fx.writes.length).toBe(1);
  await expect(panel(page).locator('[aria-current="step"]')).toContainText('원고 v2');
  expect(fx.mapRequests - initial).toBe(1);
});

test('미리보기에서도 저장 완료 상태를 직접 반영한다', async ({ page }) => {
  const fx = await fixture(page); fx.saveMode = 'hold'; await open(page);
  await page.locator('.cm-content').fill('저장 대기 중인 새 원고');
  await expect.poll(() => fx.heldWrites.length).toBe(1);
  await page.getByRole('tab', { name: '미리보기', exact: true }).click();
  await fx.heldWrites.shift()!();
  await expect(panel(page).getByRole('status')).toHaveText('저장된 원고 기준');
  await expect(panel(page).locator('[aria-current="step"]')).toContainText('원고 v2');
});

test('늦은 최초 조회가 저장 후 지도를 덮지 않는다', async ({ page }) => {
  const fx = await fixture(page); fx.holdMap = true; await open(page);
  await expect.poll(() => fx.heldMaps.length).toBe(1);
  await page.locator('.cm-content').fill('최초 조회 중 바뀐 원고');
  await expect.poll(() => fx.writes.length).toBe(1);
  await fx.heldMaps.shift()!().catch(() => {});
  await expect(panel(page).locator('[aria-current="step"]')).toContainText('원고 v2');
});

test('미래 계획 선택은 집필 회차를 바꾸지 않으며 명시 이동만 저장 후 반영한다', async ({ page }) => {
  const fx = await fixture(page); fx.saveMode = 'hold'; await open(page);
  await page.locator('.cm-content').fill('이동 직전 집필 내용');
  await selectNext(page);
  await expect(page.getByPlaceholder('회차 제목')).toHaveValue('회차 52');
  expect(await page.evaluate(async () => {
    const { useAiPanelStore } = await import('/src/stores/aiPanelStore.ts');
    const state = useAiPanelStore.getState();
    return { active: state.activeEditorIdentity, requestChapter: state.contextSelection.chapterId };
  })).toEqual({ active: { projectId: 1, chapterId: 52 }, requestChapter: 52 });
  await panel(page).getByRole('button', { name: '이 회차 집필', exact: true }).click();
  await expect.poll(() => fx.heldWrites.length).toBe(1);
  await expect(page.getByPlaceholder('회차 제목')).toHaveValue('회차 52');
  await fx.heldWrites.shift()!();
  await expect(page.getByPlaceholder('회차 제목')).toHaveValue('회차 53');
  expect(fx.chapters[51].content_md).toBe('이동 직전 집필 내용');
  expect(fx.writes.every(w => w.id === 52)).toBe(true);
});

for (const saveMode of ['error', 'conflict'] as const) test(`${saveMode} 저장은 이동을 막고 작업본을 보존한다`, async ({ page }) => {
  const fx = await fixture(page); fx.saveMode = saveMode; await open(page);
  await expect(panel(page).locator('[aria-current="step"]')).toBeVisible();
  const initial = fx.mapRequests;
  await page.locator('.cm-content').fill('실패해도 남아야 할 원고');
  await selectNext(page);
  await panel(page).getByRole('button', { name: '이 회차 집필', exact: true }).click();
  await expect(panel(page).getByRole('alert')).toBeVisible();
  await expect(page.getByPlaceholder('회차 제목')).toHaveValue('회차 52');
  await expect(page.locator('.cm-content')).toHaveText('실패해도 남아야 할 원고');
  expect(fx.writes.every(w => w.id === 52)).toBe(true);
  expect(fx.mapRequests).toBe(initial);
});

test('이동 대기 중 다른 작품을 열면 이전 응답이 회차를 바꾸지 않는다', async ({ page }) => {
  const fx = await fixture(page); await open(page); fx.holdTarget = true;
  await selectNext(page);
  await panel(page).getByRole('button', { name: '이 회차 집필', exact: true }).click();
  await expect.poll(() => fx.heldTargets.length).toBe(1);
  await page.getByRole('link', { name: 'Jippeel', exact: true }).click();
  await page.locator('a[href="/projects/2/write"]').click();
  await expect(page.getByPlaceholder('회차 제목')).toHaveValue('회차 501');
  await fx.heldTargets.shift()!().catch(() => {});
  await expect(page.getByPlaceholder('회차 제목')).toHaveValue('회차 501');
  await expect(page.locator('.cm-content')).toHaveText('저장 본문 501');
  expect(fx.writes).toEqual([]);
});

test('이동 대상 조회를 기다리는 중 추가한 입력을 보존한다', async ({ page }) => {
  const fx = await fixture(page); await open(page); fx.holdTarget = true; fx.saveMode = 'hold';
  await selectNext(page);
  await panel(page).getByRole('button', { name: '이 회차 집필', exact: true }).click();
  await expect.poll(() => fx.heldTargets.length).toBe(1);
  await page.locator('.cm-content').fill('조회 중 추가 입력');
  await fx.heldTargets.shift()!();
  await expect(panel(page).getByRole('alert')).toContainText('새로 입력한 내용');
  await expect(page.getByPlaceholder('회차 제목')).toHaveValue('회차 52');
  await expect(page.locator('.cm-content')).toHaveText('조회 중 추가 입력');
  await expect.poll(() => fx.heldWrites.length).toBe(1); await fx.heldWrites.shift()!();
});

test('선택 권의 기준 회차 삭제 후 처음부터 복구할 수 있다', async ({ page }) => {
  const fx = await fixture(page); fx.chapters[0].volume = 2; await open(page);
  await panel(page).getByRole('button', { name: '선택 권', exact: true }).click();
  await panel(page).getByLabel('권 선택').selectOption('1');
  await expect(panel(page).getByRole('button').filter({ hasText: '회차 1' })).toBeVisible();
  fx.chapters = fx.chapters.filter(c => c.id !== 1);
  await panel(page).getByRole('button', { name: '새로고침', exact: true }).click();
  await expect(panel(page).getByRole('alert')).toBeVisible();
  await panel(page).getByRole('button', { name: '지도 처음부터 열기', exact: true }).click();
  await expect(panel(page).getByRole('alert')).toHaveCount(0);
  await expect(panel(page).getByRole('button').filter({ hasText: '회차 2' })).toBeVisible();
});

test('좁은 화면 전환과 키보드 선택은 원고를 보존한다', async ({ page }) => {
  await fixture(page); await page.setViewportSize({ width: 780, height: 900 });
  await page.goto('/projects/1/write?chapter=52');
  await page.locator('.cm-content').fill('좁은 화면 원고');
  await page.getByRole('button', { name: '스토리 지도 열기', exact: true }).click();
  const next = panel(page).getByRole('button').filter({ hasText: '53. 회차 53' });
  await next.focus(); await page.keyboard.press('Enter');
  await expect(panel(page).getByRole('heading', { name: '회차 53 · 살펴보는 회차' })).toBeVisible();
  const violations = (await new AxeBuilder({ page }).include('#story-map').analyze()).violations;
  expect(violations.filter(v => ['serious', 'critical'].includes(v.impact ?? ''))).toEqual([]);
  await page.getByRole('button', { name: '지도를 접고 원고 보기', exact: true }).click();
  await expect(page.locator('.cm-content')).toHaveText('좁은 화면 원고');
});

test('관계 설정의 시점 한계와 승인 변화 근거를 구분한다', async ({ page }) => {
  const fx = await fixture(page); await open(page);
  expect(fx.evidenceRequests).toEqual([]);
  await panel(page).getByRole('button', { name: '관계', exact: true }).click();
  await expect(panel(page).getByText('시점 정보 없음 · 현재 작가 설정', { exact: true })).toBeVisible();
  await expect(panel(page).getByText('작가 승인 변화 기록 · 현재 원문 해시 일치', { exact: true })).toBeVisible();
  const violations = (await new AxeBuilder({ page }).include('#story-map').analyze()).violations;
  expect(violations.filter(v => ['serious', 'critical'].includes(v.impact ?? ''))).toEqual([]);
  await panel(page).getByRole('button', { name: /근거 살펴보기: 51/ }).click();
  await expect(panel(page).getByRole('heading', { name: '회차 51 · 살펴보는 회차' })).toBeVisible();
  await expect(page.getByPlaceholder('회차 제목')).toHaveValue('회차 52');
  expect(fx.evidenceRequests.every(r => r.chapter === 52)).toBe(true);
});

test('복선 미래 실제 회수 기록을 계획으로 바꾸지 않고 살펴본다', async ({ page }) => {
  await fixture(page); await open(page);
  await panel(page).getByRole('button', { name: '복선', exact: true }).click();
  await expect(panel(page).getByRole('list', { name: '복선 설치·회수 타임라인' })).toHaveCount(3);
  await expect(panel(page).getByText('처분: 의도적 미해결', { exact: true })).toBeVisible();
  await expect(panel(page).getByText('처분: 외전 이관', { exact: true })).toBeVisible();
  await expect(panel(page).getByRole('button', { name: /처분 기록 회차:/ })).toHaveCount(2);
  const future = panel(page).getByRole('button', { name: /실제 회수: 60.*선택 회차 이후/ });
  await future.click();
  await expect(panel(page).getByRole('heading', { name: '회차 60 · 살펴보는 회차' })).toBeVisible();
  await expect(page.getByPlaceholder('회차 제목')).toHaveValue('회차 52');
  expect(await page.evaluate(async () => {
    const { useAiPanelStore } = await import('/src/stores/aiPanelStore.ts');
    return useAiPanelStore.getState().contextSelection.chapterId;
  })).toBe(52);
});

test('원고 저장 후 변경 검토 목록에 근거 버전 차이를 표시한다', async ({ page }) => {
  await fixture(page); await open(page);
  await panel(page).getByRole('button', { name: '변경 검토', exact: true }).click();
  await expect(panel(page).getByText('이 범위에서 표시할 근거가 없습니다.')).toBeVisible();
  await page.locator('.cm-content').fill('요약의 근거가 바뀐 원고');
  await expect(panel(page).getByText('근거 원고 버전·내용 변경', { exact: true })).toBeVisible();
  await expect(panel(page).getByText('기준 원고 v1 → 현재 v2', { exact: true })).toBeVisible();
  await expect(panel(page).getByText('기존 요약 본문', { exact: true })).toBeVisible();
  await expect(panel(page).getByText('승인 기억 · 재검토 필요', { exact: true })).toBeVisible();
  await expect(panel(page).getByText('미승인 초안 · 재검토 필요', { exact: true })).toBeVisible();
  await expect(panel(page).getByRole('link', { name: '기억 관리에서 검토하기' })).toHaveAttribute('href', '/projects/1/memory');
});
