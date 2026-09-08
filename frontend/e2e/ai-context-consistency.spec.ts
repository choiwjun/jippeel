import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';

type Report = {
  run_id: string;
  status: string;
  python_executable: string;
  backend_port: number;
  frontend_port: number;
  provider_port: number;
  work_dir: string;
  db_path: string;
  prompt_log: string;
  backend_log: string;
  provider_log: string;
  alembic_log: string;
  project_id: number;
  chapter_id: number;
  chapter_revision: number;
  second_chapter_id: number;
  second_chapter_revision: number;
  future_chapter_id: number;
  character_ids: number[];
  relationship_id: number;
  lore_id: number;
  scene_id: number;
  foreshadow_id: number;
  future_plant_foreshadow_id: number;
  future_resolution_foreshadow_id: number;
  endpoint_id: number;
  foreign_project_id: number;
  foreign_chapter_id: number;
  foreign_character_id: number;
  foreign_lore_id: number;
  foreign_scene_id: number;
  foreign_foreshadow_id: number;
  bad_ref_foreshadow_id: number;
  missing_id: number;
  sentinels: Record<string, string>;
  owned_pids: Record<string, number>;
};

type PromptEntry = {
  kind: string;
  path: string;
  payload: { messages?: Array<{ role: string; content: string }>; [key: string]: unknown };
  response_content?: string;
};

type CreativeSnapshot = {
  chapters: unknown[];
  characters: unknown[];
  relationships: unknown[];
  lore: unknown[];
  foreshadows: unknown[];
};

const evidence: Record<string, unknown> = {
  uiRequests: [],
  promptChecks: [],
  apiNegatives: [],
};
let creativeBefore: CreativeSnapshot | null = null;

function reportPath() {
  return path.resolve('..', '.eval_tmp', 'ai-context-task-4', 'backend-fixture.json');
}

function evidencePath() {
  return path.resolve('..', '.eval_tmp', 'ai-context-task-4', 'playwright-evidence.json');
}

function readReport(): Report {
  return JSON.parse(fs.readFileSync(reportPath(), 'utf-8')) as Report;
}

async function waitForReadyReport(): Promise<Report> {
  await expect.poll(() => {
    try {
      const report = readReport();
      return report.status === 'holding'
        && typeof report.run_id === 'string'
        && typeof report.project_id === 'number'
        && typeof report.chapter_id === 'number'
        && typeof report.endpoint_id === 'number'
        && typeof report.prompt_log === 'string'
        ? report.run_id
        : '';
    } catch {
      return '';
    }
  }, {
    timeout: 90_000,
    message: 'backend fixture pointer must reach holding status with complete seed IDs before tests read it',
  }).not.toBe('');
  return readReport();
}

function readPrompts(promptLog: string): PromptEntry[] {
  if (!fs.existsSync(promptLog)) return [];
  const text = fs.readFileSync(promptLog, 'utf-8').trim();
  if (!text) return [];
  return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line) as PromptEntry);
}

function promptText(entry: PromptEntry): string {
  return (entry.payload.messages ?? []).map((message) => message.content ?? '').join('\n');
}

function countPrompts(promptLog: string) {
  return readPrompts(promptLog).length;
}

async function waitForKindCount(promptLog: string, kind: string, minimum: number) {
  await expect.poll(() => readPrompts(promptLog).filter((entry) => entry.kind === kind).length, {
    timeout: 20_000,
    message: `provider prompt kind ${kind} should reach ${minimum}`,
  }).toBeGreaterThanOrEqual(minimum);
}

async function apiJson<T = unknown>(request: APIRequestContext, method: string, url: string, data?: unknown, expected = 200): Promise<T> {
  const response = await request.fetch(url, { method, data, headers: { accept: 'application/json' } });
  expect(response.status(), `${method} ${url} body=${await response.text().catch(() => '')}`).toBe(expected);
  return (await response.json()) as T;
}

async function creativeSnapshot(request: APIRequestContext, report: Report): Promise<CreativeSnapshot> {
  const [chapter1, chapter2] = await Promise.all([
    apiJson(request, 'GET', `/api/v1/chapters/${report.chapter_id}`),
    apiJson(request, 'GET', `/api/v1/chapters/${report.second_chapter_id}`),
  ]);
  const [characters, relationships, lore, foreshadows] = await Promise.all([
    apiJson(request, 'GET', `/api/v1/projects/${report.project_id}/characters`),
    apiJson(request, 'GET', `/api/v1/characters/${report.character_ids[0]}/relations`),
    apiJson(request, 'GET', `/api/v1/projects/${report.project_id}/lore`),
    apiJson(request, 'GET', `/api/v1/projects/${report.project_id}/foreshadows`),
  ]);
  return {
    chapters: [chapter1, chapter2],
    characters: characters as unknown[],
    relationships: relationships as unknown[],
    lore: lore as unknown[],
    foreshadows: foreshadows as unknown[],
  };
}

async function prepareEditorPage(page: Page, report: Report, options?: { second?: boolean }) {
  await page.goto(`/projects/${report.project_id}/write`);
  await expect(page.locator('.cm-content')).toBeVisible();
  if (options?.second) {
    await page.getByRole('button', { name: /AI Context Task4 2화/ }).click();
    await expect(page.locator('.cm-content')).toBeVisible();
  }
}

async function assertNaturalEditorIdentity(page: Page, report: Report) {
  await expect.poll(async () => page.evaluate(async () => {
    const ai = await import('/src/stores/aiPanelStore.ts');
    const editor = await import('/src/stores/editorStore.ts');
    const aiState = ai.useAiPanelStore.getState().contextSelection;
    const editorState = editor.useEditorStore.getState();
    return `${editorState.projectId}:${editorState.chapterId}:${aiState.projectId}:${aiState.chapterId}`;
  }), {
    timeout: 20_000,
    message: 'natural editor and AI store identity should bind from the real editor route',
  }).toBe(`${report.project_id}:${report.chapter_id}:${report.project_id}:${report.chapter_id}`);
}

async function setSelectionOnly(page: Page, report: Report, patch: Record<string, unknown> = {}) {
  await page.evaluate(async ({ characterIds, patch }) => {
    const ai = await import('/src/stores/aiPanelStore.ts');
    ai.useAiPanelStore.getState().setContext({
      characterIds,
      includeCharacters: characterIds.length > 0,
      loreIds: [],
      includeLore: false,
      ...patch,
    });
  }, { characterIds: report.character_ids, patch });
}

async function configureSharedUiControls(page: Page, report: Report, purpose: 'serial' | 'volume_end' | 'series_finale') {
  await page.getByLabel('회차 목적').selectOption(purpose);
  const relationship = page.getByLabel('선택 인물 관계 포함');
  await expect(relationship).toBeEnabled();
  if (!(await relationship.isChecked())) await relationship.check();
  await page.getByRole('button', { name: /복선 회수 승인 선택/ }).click();
  const payoff = page.getByLabel(/이번 요청에서 회수\/공개 허용: 검의 진짜 주인/);
  await expect(payoff).toBeVisible();
  if (!(await payoff.isChecked())) await payoff.check();
  const style = page.getByLabel(/문체 프로파일 적용/);
  if (!(await style.isChecked())) await style.check();
  evidence.promptChecks = [...(evidence.promptChecks as unknown[]), { phase: 'ui-controls', purpose, foreshadow_id: report.foreshadow_id, relationship_id: report.relationship_id }];
}

function querySqlite(report: Report, sql: string, params: unknown[] = []) {
  const code = [
    'import json, sqlite3, sys',
    'from pathlib import Path',
    'db, sql, raw_params = sys.argv[1], sys.argv[2], sys.argv[3]',
    'uri = Path(db).resolve().as_uri() + "?mode=ro"',
    'conn = sqlite3.connect(uri, uri=True)',
    'conn.row_factory = sqlite3.Row',
    'rows = conn.execute(sql, json.loads(raw_params)).fetchall()',
    'print(json.dumps([dict(row) for row in rows], ensure_ascii=False))',
  ].join('\n');
  const out = execFileSync(report.python_executable, ['-c', code, report.db_path, sql, JSON.stringify(params)], { encoding: 'utf-8' });
  return JSON.parse(out) as Array<Record<string, unknown>>;
}

async function expectNoProviderIncrease(report: Report, before: number, action: () => Promise<void>, note: string) {
  await action();
  const after = countPrompts(report.prompt_log);
  expect(after, `${note} must not create provider chat logs`).toBe(before);
  (evidence.apiNegatives as unknown[]).push({ note, before, after });
}

test.describe.serial('AI context consistency real Task4 integration', () => {
  test.beforeAll(async ({ request }) => {
    const report = await waitForReadyReport();
    creativeBefore = await creativeSnapshot(request, report);
    evidence.report = {
      run_id: report.run_id,
      db_path: report.db_path,
      work_dir: report.work_dir,
      prompt_log: report.prompt_log,
      ports: { frontend: report.frontend_port, backend: report.backend_port, provider: report.provider_port },
      owned_pids: report.owned_pids,
      seed_ids: {
        project_id: report.project_id,
        chapter_id: report.chapter_id,
        second_chapter_id: report.second_chapter_id,
        character_ids: report.character_ids,
        relationship_id: report.relationship_id,
        lore_id: report.lore_id,
        foreshadow_id: report.foreshadow_id,
        future_plant_foreshadow_id: report.future_plant_foreshadow_id,
        future_resolution_foreshadow_id: report.future_resolution_foreshadow_id,
        foreign_project_id: report.foreign_project_id,
      },
    };
  });

  test.afterAll(async ({ request }) => {
    const report = await waitForReadyReport();
    const creativeAfter = await creativeSnapshot(request, report);
    evidence.creativeBefore = creativeBefore;
    evidence.creativeAfter = creativeAfter;
    evidence.finalPromptCounts = readPrompts(report.prompt_log).reduce<Record<string, number>>((acc, entry) => {
      acc[entry.kind] = (acc[entry.kind] ?? 0) + 1;
      return acc;
    }, {});
    fs.mkdirSync(path.dirname(evidencePath()), { recursive: true });
    fs.writeFileSync(evidencePath(), JSON.stringify(evidence, null, 2), 'utf-8');
  });

  test('browser single generation + automatic review uses saved identity while body opt-out omits body sentinel', async ({ page }) => {
    const report = await waitForReadyReport();
    const uiRequests: Array<{ url: string; body: unknown }> = [];
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/api/v1/ai/generate')) {
        try { uiRequests.push({ url: req.url(), body: req.postDataJSON() }); } catch { /* noop */ }
      }
    });

    await prepareEditorPage(page, report);
    await assertNaturalEditorIdentity(page, report);
    await setSelectionOnly(page, report);
    await page.getByRole('button', { name: /AI 패널/ }).click();
    await page.getByLabel('프롬프트 직접 입력').fill('AI_CONTEXT_SINGLE_REQUEST — 검의 주인을 결말에서 드러내라');
    await page.getByLabel('생성 후 자동 감수 (지적 + 수정본)').check();
    await configureSharedUiControls(page, report, 'series_finale');
    const includeBody = page.getByLabel(/현재 회차 본문 포함/);
    if (await includeBody.isChecked()) await includeBody.uncheck();

    await page.getByRole('button', { name: '✨ 생성 시작' }).click();
    await expect(page.getByText('AI_CONTEXT_REFINED')).toBeVisible({ timeout: 30_000 });
    await waitForKindCount(report.prompt_log, 'draft', 1);
    await waitForKindCount(report.prompt_log, 'single_review', 1);

    expect(uiRequests.length).toBeGreaterThanOrEqual(1);
    const requestBody = uiRequests.at(-1)!.body as { context: Record<string, unknown> };
    expect(requestBody.context.project_id).toBe(report.project_id);
    expect(requestBody.context.chapter_id).toBe(report.chapter_id);
    expect(requestBody.context.expected_revision).toBe(report.chapter_revision);
    expect(requestBody.context.include_chapter_content).toBe(false);
    expect(requestBody.context.episode_purpose).toBe('series_finale');
    expect(requestBody.context.approved_foreshadow_ids).toEqual([report.foreshadow_id]);
    expect(requestBody.context.include_relationships).toBe(true);
    expect(requestBody.context.character_ids).toEqual(report.character_ids);

    const prompts = readPrompts(report.prompt_log);
    const draft = prompts.find((entry) => entry.kind === 'draft')!;
    const singleReview = prompts.find((entry) => entry.kind === 'single_review')!;
    for (const [phase, entry] of [['draft', draft], ['single_review', singleReview]] as const) {
      const text = promptText(entry);
      expect(text).toContain('[최종화 목적]');
      expect(text).toContain('AI_CONTEXT_STYLE_SENTINEL');
      expect(text).toContain('[인물 관계');
      expect(text).toContain('AI_CONTEXT_REL_SENTINEL');
      expect(text).toContain('[이번 요청에서 회수/공개 허용된 복선: 검의 진짜 주인]');
      expect(text).toContain('AI_CONTEXT_PAYOFF_SENTINEL');
      expect(text).not.toContain(report.sentinels.body);
      (evidence.promptChecks as unknown[]).push({ phase, kind: entry.kind, contains: ['finale', 'style', 'relationship', 'approved-payoff'], omits: ['body-sentinel'] });
    }
    expect(singleReview.response_content).toContain('[감수]');
    expect(singleReview.response_content).toContain('[수정본]');

    await page.getByRole('button', { name: '패널 닫기' }).click();
    await page.getByRole('button', { name: /AI Context Task4 2화/ }).click();
    await expect(page.locator('.cm-content')).toBeVisible();
    await page.getByRole('button', { name: /AI 패널/ }).click();
    await expect(page.getByRole('button', { name: '⧉ 복사' })).toBeEnabled();
    await expect(page.getByRole('button', { name: '↪ 끼워넣기' })).toBeDisabled();
    (evidence.uiRequests as unknown[]).push({ phase: 'single', requests: uiRequests });
  });

  test('browser parallel generation and canon log every provider phase with context parity', async ({ page, request }) => {
    const report = await waitForReadyReport();
    const uiRequests: Array<{ url: string; body: unknown }> = [];
    page.on('request', (req) => {
      if (req.method() === 'POST' && (req.url().includes('/api/v1/ai/generate-parallel') || req.url().includes('/api/v1/canon-check'))) {
        try { uiRequests.push({ url: req.url(), body: req.postDataJSON() }); } catch { /* noop */ }
      }
    });

    await prepareEditorPage(page, report);
    await assertNaturalEditorIdentity(page, report);
    await setSelectionOnly(page, report);
    await page.getByRole('button', { name: /AI 패널/ }).click();
    await page.getByLabel('프롬프트 직접 입력').fill('AI_CONTEXT_PARALLEL_REQUEST — 순서대로 두 장면으로 닫아라');
    await page.getByLabel('집필 모드').selectOption('parallel');
    await configureSharedUiControls(page, report, 'series_finale');
    await page.getByRole('button', { name: '✨ 병렬 집필 시작' }).click();
    await expect(page.getByText('AI_CONTEXT_PARALLEL_REVIEW')).toBeVisible({ timeout: 45_000 });
    const parallelRequest = uiRequests.find((entry) => entry.url.includes('/api/v1/ai/generate-parallel'))?.body as { context?: Record<string, unknown> } | undefined;
    expect(parallelRequest?.context?.project_id).toBe(report.project_id);
    expect(parallelRequest?.context?.chapter_id).toBe(report.chapter_id);
    expect(parallelRequest?.context?.expected_revision).toBe(report.chapter_revision);
    expect(parallelRequest?.context?.episode_purpose).toBe('series_finale');
    expect(parallelRequest?.context?.approved_foreshadow_ids).toEqual([report.foreshadow_id]);
    expect(parallelRequest?.context?.include_relationships).toBe(true);
    expect(parallelRequest?.context?.character_ids).toEqual(report.character_ids);
    await waitForKindCount(report.prompt_log, 'planner', 1);
    await waitForKindCount(report.prompt_log, 'worker', 2);
    await waitForKindCount(report.prompt_log, 'parallel_review', 1);

    const promptsAfterParallel = readPrompts(report.prompt_log);
    const planner = promptsAfterParallel.find((entry) => entry.kind === 'planner')!;
    const plannerJson = JSON.parse(planner.response_content ?? '{}') as { scenes: Array<Record<string, unknown>> };
    expect(plannerJson.scenes.map((scene) => scene.order)).toEqual([1, 2]);
    expect(plannerJson.scenes.at(-1)?.ending_intent).toBeTruthy();
    const workers = promptsAfterParallel.filter((entry) => entry.kind === 'worker');
    const parallelReview = promptsAfterParallel.find((entry) => entry.kind === 'parallel_review')!;
    expect(workers.length).toBeGreaterThanOrEqual(2);
    for (const [phase, entry] of [['planner', planner], ['worker-1', workers[0]], ['worker-2', workers[1]], ['parallel_review', parallelReview]] as const) {
      const text = promptText(entry);
      expect(text).toContain('[최종화 목적]');
      expect(text).toContain('AI_CONTEXT_STYLE_SENTINEL');
      expect(text).toContain('AI_CONTEXT_REL_SENTINEL');
      expect(text).toContain('AI_CONTEXT_PAYOFF_SENTINEL');
      (evidence.promptChecks as unknown[]).push({ phase, kind: entry.kind, contains: ['finale', 'style', 'relationship', 'approved-payoff'] });
    }
    const workerResponses = workers.map((entry) => entry.response_content ?? '').join('\n---\n');
    expect(workerResponses).toContain('AI_CONTEXT_PARALLEL_SCENE_1');
    expect(workerResponses).toContain('AI_CONTEXT_PARALLEL_SCENE_2');
    const reviewPromptText = promptText(parallelReview);
    expect(reviewPromptText.indexOf('AI_CONTEXT_PARALLEL_SCENE_1')).toBeLessThan(reviewPromptText.indexOf('AI_CONTEXT_PARALLEL_SCENE_2'));

    await page.keyboard.press('Escape');
    await page.evaluate(async ({ projectId, chapterId, foreshadowId }) => {
      const ai = await import('/src/stores/aiPanelStore.ts');
      ai.useAiPanelStore.getState().setDirectives(projectId, chapterId, {
        episodePurpose: 'series_finale',
        includeRelationships: true,
        approvedForeshadowIds: [foreshadowId],
      });
    }, { projectId: report.project_id, chapterId: report.chapter_id, foreshadowId: report.foreshadow_id });
    const savedChapterForCanon = await apiJson<{ id: number; project_id: number; revision: number; content_md: string }>(request, 'GET', `/api/v1/chapters/${report.chapter_id}`);
    expect(savedChapterForCanon.id).toBe(report.chapter_id);
    expect(savedChapterForCanon.project_id).toBe(report.project_id);
    expect(savedChapterForCanon.revision).toBe(report.chapter_revision);
    const expectedCanonHash = crypto.createHash('sha256').update(savedChapterForCanon.content_md, 'utf-8').digest('hex');
    const expectedCanonProvenance = `검사 기준 — 작품 #${savedChapterForCanon.project_id} · 회차 #${savedChapterForCanon.id} · rev ${savedChapterForCanon.revision} · hash ${expectedCanonHash}`;
    await page.getByRole('button', { name: '모순 검사' }).click();
    await page.getByRole('button', { name: /검사 실행/ }).click();
    const canonProvenance = page.getByText(expectedCanonProvenance, { exact: true });
    await expect(canonProvenance).toBeVisible({ timeout: 30_000 });
    const actualCanonProvenance = (await canonProvenance.textContent())?.trim();
    expect(actualCanonProvenance).toBe(expectedCanonProvenance);
    await waitForKindCount(report.prompt_log, 'canon', 1);

    const canonEntries = readPrompts(report.prompt_log).filter((entry) => entry.kind === 'canon');
    const canon = canonEntries.at(-1)!;
    const canonText = promptText(canon);
    expect(canon.response_content).toBe('{"issues": []}');
    expect(canonText).toContain('[최종화 목적]');
    expect(canonText).toContain('AI_CONTEXT_REL_SENTINEL');
    expect(canonText).toContain('[이번 요청에서 회수/공개 허용된 복선: 검의 진짜 주인]');
    expect(canonText).toContain('AI_CONTEXT_PAYOFF_SENTINEL');
    expect(canonText).toContain('AI_CONTEXT_FUTURE_PLANT_SENTINEL');
    expect(canonText).toContain('현재 사실 아님');
    expect(canonText).toContain('AI_CONTEXT_FUTURE_RESOLUTION_SENTINEL');
    expect(canonText).toContain('미래 회수 계획은 현재 사실이나 현재 인물 지식으로 단정하지 마라');
    (evidence.promptChecks as unknown[]).push({ phase: 'canon', kind: canon.kind, contains: ['finale', 'relationship', 'approved-payoff', 'future-plant', 'future-resolution'] });

    const canonRuns = await apiJson<Array<{ chapter_id: number; context_json: Record<string, unknown> }>>(request, 'GET', `/api/v1/canon-check/runs?chapter_id=${report.chapter_id}`);
    expect(canonRuns[0].chapter_id).toBe(report.chapter_id);
    expect(canonRuns[0].context_json.project_id).toBe(report.project_id);
    expect(canonRuns[0].context_json.chapter_id).toBe(report.chapter_id);
    expect(canonRuns[0].context_json.checked_input_revision).toBe(savedChapterForCanon.revision);
    expect(canonRuns[0].context_json.checked_input_hash).toBe(expectedCanonHash);
    const canonDbRows = querySqlite(report, 'SELECT chapter_id, context_json FROM canon_runs WHERE chapter_id = ? ORDER BY id DESC LIMIT 1', [report.chapter_id]);
    const canonDbContext = JSON.parse(String(canonDbRows[0].context_json)) as Record<string, unknown>;
    expect(canonDbRows[0].chapter_id).toBe(report.chapter_id);
    expect(canonDbContext.checked_input_revision).toBe(savedChapterForCanon.revision);
    expect(canonDbContext.checked_input_hash).toBe(expectedCanonHash);
    evidence.canonProvenance = {
      expected: expectedCanonProvenance,
      actual: actualCanonProvenance,
      source: {
        project_id: savedChapterForCanon.project_id,
        chapter_id: savedChapterForCanon.id,
        revision: savedChapterForCanon.revision,
        hash: expectedCanonHash,
      },
      apiHistory: canonRuns[0].context_json,
      dbHistory: canonDbContext,
    };
    (evidence.uiRequests as unknown[]).push({ phase: 'parallel-canon', requests: uiRequests });
  });

  test('purpose quality, invalid ownership/revision no-provider matrix, legacy default, and creative-state preservation', async ({ request }) => {
    const report = await waitForReadyReport();

    const serial = await apiJson<{ metrics: Record<string, unknown>; suggestions: string[] }>(request, 'GET', `/api/v1/chapters/${report.chapter_id}/quality?episode_purpose=serial`);
    const volumeEnd = await apiJson<{ metrics: Record<string, unknown>; suggestions: string[] }>(request, 'GET', `/api/v1/chapters/${report.chapter_id}/quality?episode_purpose=volume_end`);
    const finale = await apiJson<{ metrics: Record<string, unknown>; suggestions: string[] }>(request, 'GET', `/api/v1/chapters/${report.chapter_id}/quality?episode_purpose=series_finale`);
    expect(serial.metrics.episode_purpose).toBe('serial');
    expect(serial.metrics.hook_score_applicable).toBe(true);
    expect(volumeEnd.metrics.episode_purpose).toBe('volume_end');
    expect(volumeEnd.metrics.hook_score_applicable).toBe(false);
    expect(JSON.stringify(volumeEnd.suggestions)).toContain('권말');
    expect(finale.metrics.episode_purpose).toBe('series_finale');
    expect(finale.metrics.hook_score_applicable).toBe(false);
    expect(JSON.stringify(finale.suggestions)).not.toContain('다음 화');

    const history = await apiJson<Array<{ metrics_json: Record<string, unknown> }>>(request, 'GET', `/api/v1/chapters/${report.chapter_id}/quality/history`);
    expect(history.some((row) => row.metrics_json?.episode_purpose === 'serial')).toBe(true);
    expect(history.some((row) => row.metrics_json?.episode_purpose === 'volume_end')).toBe(true);
    expect(history.some((row) => row.metrics_json?.episode_purpose === 'series_finale')).toBe(true);
    const qualityRows = querySqlite(report, 'SELECT content_hash, metrics_json FROM quality_checks WHERE chapter_id = ? ORDER BY id', [report.chapter_id]);
    const trueHash = crypto.createHash('sha256').update(report.sentinels.body, 'utf-8').digest('hex');
    expect(qualityRows.length).toBeGreaterThanOrEqual(2);
    for (const row of qualityRows) expect(row.content_hash).toBe(trueHash);
    expect(qualityRows.map((row) => JSON.parse(String(row.metrics_json)).episode_purpose)).toEqual(expect.arrayContaining(['serial', 'volume_end', 'series_finale']));
    evidence.quality = { serial: serial.metrics, volumeEnd: volumeEnd.metrics, finale: finale.metrics, qualityRows };

    let before = countPrompts(report.prompt_log);
    await expectNoProviderIncrease(report, before, async () => {
      await apiJson(request, 'POST', '/api/v1/ai/generate', {
        endpoint_id: report.endpoint_id,
        prompt_override: 'invalid project chapter',
        context: { project_id: report.project_id, chapter_id: report.foreign_chapter_id },
      }, 422);
    }, 'project/chapter mismatch generation');
    before = countPrompts(report.prompt_log);
    await expectNoProviderIncrease(report, before, async () => {
      await apiJson(request, 'POST', '/api/v1/ai/generate-parallel', {
        endpoint_id: report.endpoint_id,
        prompt_override: 'invalid stale parallel',
        context: { project_id: report.project_id, chapter_id: report.chapter_id, expected_revision: report.chapter_revision - 1 },
        worker_limit: 2,
        review: {},
      }, 409);
    }, 'stale revision parallel generation');
    before = countPrompts(report.prompt_log);
    await expectNoProviderIncrease(report, before, async () => {
      await apiJson(request, 'POST', '/api/v1/canon-check', {
        chapter_id: report.chapter_id,
        expected_revision: report.chapter_revision - 1,
      }, 409);
    }, 'stale revision canon');
    before = countPrompts(report.prompt_log);
    await expectNoProviderIncrease(report, before, async () => {
      await apiJson(request, 'POST', '/api/v1/ai/generate', {
        endpoint_id: report.endpoint_id,
        prompt_override: 'invalid selected ids',
        context: {
          project_id: report.project_id,
          chapter_id: report.chapter_id,
          expected_revision: report.chapter_revision,
          character_ids: [report.foreign_character_id],
          lore_ids: [report.foreign_lore_id],
        },
      }, 422);
    }, 'wrong explicit character/lore generation');
    before = countPrompts(report.prompt_log);
    await expectNoProviderIncrease(report, before, async () => {
      await apiJson(request, 'POST', '/api/v1/ai/generate', {
        endpoint_id: report.endpoint_id,
        prompt_override: 'invalid scene id',
        context: {
          project_id: report.project_id,
          chapter_id: report.chapter_id,
          expected_revision: report.chapter_revision,
          scene_id: report.foreign_scene_id,
        },
      }, 422);
    }, 'wrong explicit scene generation');
    before = countPrompts(report.prompt_log);
    await expectNoProviderIncrease(report, before, async () => {
      await apiJson(request, 'POST', '/api/v1/canon-check', {
        chapter_id: report.chapter_id,
        approved_foreshadow_ids: [report.foreign_foreshadow_id],
      }, 422);
    }, 'approved-only mixed-project foreshadow canon');
    before = countPrompts(report.prompt_log);
    await expectNoProviderIncrease(report, before, async () => {
      await apiJson(request, 'POST', '/api/v1/canon-check', {
        chapter_id: report.chapter_id,
        approved_foreshadow_ids: [report.bad_ref_foreshadow_id],
      }, 422);
    }, 'approved foreshadow with cross-project referenced chapter');
    before = countPrompts(report.prompt_log);
    await expectNoProviderIncrease(report, before, async () => {
      await apiJson(request, 'POST', '/api/v1/ai/generate', {
        endpoint_id: report.endpoint_id,
        prompt_override: 'missing selected ids',
        context: { project_id: report.project_id, chapter_id: report.chapter_id, character_ids: [report.missing_id] },
      }, 404);
    }, 'missing selected character generation');

    const legacyBefore = countPrompts(report.prompt_log);
    const legacy = await request.post('/api/v1/ai/generate', {
      data: {
        endpoint_id: report.endpoint_id,
        prompt_override: 'legacy unambiguous chapter-only request',
        context: { chapter_id: report.chapter_id },
      },
      headers: { accept: 'text/event-stream' },
    });
    expect(legacy.status()).toBe(200);
    await legacy.text();
    await expect.poll(() => countPrompts(report.prompt_log), { timeout: 20_000 }).toBeGreaterThan(legacyBefore);
    const legacyPrompt = readPrompts(report.prompt_log).at(-1)!;
    expect(legacyPrompt.kind).toBe('draft');
    expect(promptText(legacyPrompt)).toContain(report.sentinels.body);
    (evidence.promptChecks as unknown[]).push({ phase: 'legacy-default', kind: legacyPrompt.kind, contains: ['body-sentinel'] });

    const creativeAfter = await creativeSnapshot(request, report);
    expect(creativeAfter.chapters).toEqual(creativeBefore!.chapters);
    expect(creativeAfter.characters).toEqual(creativeBefore!.characters);
    expect(creativeAfter.relationships).toEqual(creativeBefore!.relationships);
    expect(creativeAfter.lore).toEqual(creativeBefore!.lore);
    expect(creativeAfter.foreshadows).toEqual(creativeBefore!.foreshadows);
  });
});
