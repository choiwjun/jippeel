import { test, expect, type APIRequestContext, type Page, type Route } from '@playwright/test';

const BACKEND_ORIGIN = 'http://127.0.0.1:18080';
const API = `${BACKEND_ORIGIN}/api/v1`;

const SWITCH_TEXT = '통합 전환 전 초안 — debounce 이전 입력';
const HELD_TEXT = '통합 저장 지연 중 원고 v1';
const LATE_TEXT = '통합 저장 지연 중 늦은 원고 v2';
const HUMAN_EDIT_AFTER_REFINE = '윤문 뒤 사람 편집이 우선인 원고';
const SCENE_ONE = '장면 하나 본문입니다.';
const SCENE_TWO = '장면 둘 본문입니다.';
const MERGED_SCENES = `${SCENE_ONE}\n\n${SCENE_TWO}`;
const LATE_RESTORE_TEXT = '복원 응답 대기 중 새로 쓴 로컬 원고';

type Project = { id: number; title: string };
type Chapter = { id: number; project_id: number; title: string; content_md: string; revision: number };
type Snapshot = { id: number; chapter_id: number; revision: number; reason: string };

async function apiGet<T>(request: APIRequestContext, path: string): Promise<T> {
  const response = await request.get(`${API}${path}`);
  expect(response.ok(), `${path} status ${response.status()}: ${await response.text()}`).toBeTruthy();
  return response.json() as Promise<T>;
}

async function apiPost<T>(request: APIRequestContext, path: string, data?: unknown, expectedStatus = 200): Promise<T> {
  const response = await request.post(`${API}${path}`, { data });
  expect(response.status(), `${path}: ${await response.text()}`).toBe(expectedStatus);
  return response.json() as Promise<T>;
}

async function apiPatch<T>(request: APIRequestContext, path: string, data: unknown): Promise<T> {
  const response = await request.patch(`${API}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json() as Promise<T>;
}

async function apiPut<T>(request: APIRequestContext, path: string, data: unknown, expectedStatus = 200): Promise<T> {
  const response = await request.put(`${API}${path}`, { data });
  expect(response.status(), `${path}: ${await response.text()}`).toBe(expectedStatus);
  return response.json() as Promise<T>;
}

async function currentChapter(request: APIRequestContext, chapterId: number) {
  return apiGet<Chapter>(request, `/chapters/${chapterId}`);
}

async function expectChapter(request: APIRequestContext, chapterId: number, content: string, revision?: number) {
  const expected = revision === undefined ? content : `${revision}\n${content}`;
  await expect.poll(async () => {
    const chapter = await currentChapter(request, chapterId);
    return revision === undefined ? chapter.content_md : `${chapter.revision}\n${chapter.content_md}`;
  }, { timeout: 20_000 }).toBe(expected);
}

async function fillEditor(page: Page, text: string) {
  const editor = page.locator('.cm-content');
  await expect(editor).toBeVisible();
  await editor.click();
  await editor.fill(text);
}

async function pressSave(page: Page) {
  await page.locator('.cm-content').click();
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+S' : 'Control+S');
}

async function createProjectAndTwoChaptersInBrowser(page: Page, request: APIRequestContext) {
  const title = `Task3 통합 QA ${Date.now()}`;
  await page.goto('/');
  await page.getByRole('button', { name: /새 작품/ }).first().click();
  await page.getByPlaceholder('제목').fill(title);
  await page.getByPlaceholder(/장르/).fill('QA');
  await page.getByRole('button', { name: '생성', exact: true }).click();
  await expect(page.getByRole('heading', { name: title })).toBeVisible();
  await page.getByRole('link', { name: /열기/ }).first().click();
  await expect(page).toHaveURL(/\/projects\/\d+\/write/);

  await page.getByRole('button', { name: /회차 추가/ }).click();
  await expect(page.locator('.cm-content')).toBeVisible();
  await page.getByRole('button', { name: /회차 추가/ }).click();
  await expect(page.locator('.cm-content')).toBeVisible();

  const projects = await apiGet<Project[]>(request, '/projects');
  const project = projects.find((p) => p.title === title);
  expect(project, `created project ${title} should exist in real backend`).toBeTruthy();
  const chapters = await apiGet<Chapter[]>(request, `/projects/${project!.id}/chapters`);
  expect(chapters).toHaveLength(2);
  const [first, second] = chapters.sort((a, b) => a.id - b.id);
  await apiPatch<Chapter>(request, `/chapters/${first.id}`, { title: '통합 1화' });
  await apiPatch<Chapter>(request, `/chapters/${second.id}`, { title: '통합 2화' });

  return { project: project!, first, second };
}


async function expandChapterTree(page: Page) {
  const volumeButton = page.getByRole('button', { name: /권 없음|1권/ }).first();
  if (await volumeButton.isVisible()) {
    const expanded = await volumeButton.getAttribute('aria-expanded');
    if (expanded !== 'true') await volumeButton.click();
  }
}

async function openProject(page: Page, projectId: number) {
  await page.goto(`/projects/${projectId}/write`);
  await expect(page.locator('.cm-content')).toBeVisible();
  await expandChapterTree(page);
}

test.describe.serial('manuscript preservation real backend integration', () => {
  test('uses real temp backend for browser saves, stale refine accept, scene merge, and restore race', async ({ page, request }) => {
    test.setTimeout(120_000);

    const { project, first, second } = await createProjectAndTwoChaptersInBrowser(page, request);
    await openProject(page, project.id);

    // Type and switch before the debounce fires. The save must still reach the temp backend.
    await page.getByRole('button', { name: /통합 1화/ }).click();
    await fillEditor(page, SWITCH_TEXT);
    await page.getByRole('button', { name: /통합 2화/ }).click();
    await expect(page.locator('.cm-content')).not.toContainText(SWITCH_TEXT);
    await expectChapter(request, first.id, SWITCH_TEXT, 1);
    await expectChapter(request, second.id, '', 0);
    await page.reload();
    await expandChapterTree(page);

    // Hold a real PUT, type again while that request is in flight, then forward it.
    let heldSave: Route | null = null;
    await page.route(`**/api/v1/chapters/${first.id}/content`, async (route) => {
      const body = JSON.parse(route.request().postData() ?? '{}') as { content_md?: string };
      if (route.request().method() === 'PUT' && body.content_md === HELD_TEXT && heldSave === null) {
        heldSave = route;
        return;
      }
      await route.continue();
    });

    await page.getByRole('button', { name: /통합 1화/ }).click();
    await expect(page.locator('.cm-content')).toContainText(SWITCH_TEXT);
    await fillEditor(page, HELD_TEXT);
    await pressSave(page);
    await expect.poll(() => heldSave !== null, { timeout: 10_000 }).toBe(true);
    await fillEditor(page, LATE_TEXT);
    const firstSaveResponse = page.waitForResponse((response) =>
      response.url().includes(`/api/v1/chapters/${first.id}/content`) &&
      response.request().method() === 'PUT' &&
      true,
    );
    await heldSave!.continue();
    const firstHeldSave = await firstSaveResponse;
    expect(firstHeldSave.status()).toBe(200);
    await expectChapter(request, first.id, LATE_TEXT, 3);
    await expect(page.locator('.cm-content')).toContainText(LATE_TEXT);

    // Re-open and preview the exact content that the real API reports.
    await page.reload();
    await expect(page.locator('.cm-content')).toContainText(LATE_TEXT);
    await page.getByRole('tab', { name: '미리보기' }).click();
    await expect(page.getByText(LATE_TEXT)).toBeVisible();
    await page.getByRole('tab', { name: '편집' }).click();

    // The selected chapter belongs to the current project; a second project must not inherit it.
    const otherProject = await apiPost<Project>(request, '/projects', { title: `Task3 다른 작품 ${Date.now()}` }, 201);
    const otherChapter = await apiPost<Chapter>(request, `/projects/${otherProject.id}/chapters`, { title: '다른 작품 1화' }, 201);
    await apiPut<Chapter>(request, `/chapters/${otherChapter.id}/content`, { content_md: '다른 작품 원고', expected_revision: 0 });
    await openProject(page, otherProject.id);
    await expect(page.locator('.cm-content')).toContainText('다른 작품 원고');
    await expect(page.locator('.cm-content')).not.toContainText(LATE_TEXT);
    await expectChapter(request, first.id, LATE_TEXT, 3);
    await openProject(page, project.id);

    // Generate a real stub-backed refine run, edit/save afterwards, then prove accept gets 409.
    await page.getByRole('button', { name: /통합 1화/ }).click();
    await page.getByRole('button', { name: '윤문 리포트' }).click();
    await page.locator('select[aria-label="윤문 강도"]').selectOption('light');
    const refineResponse = page.waitForResponse((response) =>
      response.url().endsWith('/api/v1/refine') && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: '🔍 윤문 실행' }).click();
    const refine = await refineResponse;
    expect(refine.status()).toBe(200);
    const refineBody = await refine.json() as { run_id: number; original: string; refined: string };
    expect(refineBody.original).toBe(LATE_TEXT);
    expect(refineBody.refined).toContain('[QA 윤문 stub]');
    await expect(page.getByRole('button', { name: /수락/ })).toBeVisible();

    await apiPut<Chapter>(request, `/chapters/${first.id}/content`, {
      content_md: HUMAN_EDIT_AFTER_REFINE,
      expected_revision: 3,
    });
    const staleAcceptResponse = page.waitForResponse((response) =>
      response.url().includes(`/api/v1/refine/runs/${refineBody.run_id}/accept`) && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: /수락/ }).click();
    const staleAccept = await staleAcceptResponse;
    expect(staleAccept.status()).toBe(409);
    const afterStaleAccept = await currentChapter(request, first.id);
    expect(afterStaleAccept.content_md).toBe(HUMAN_EDIT_AFTER_REFINE);
    expect(afterStaleAccept.revision).toBe(4);

    // Re-open the server truth, assemble two nonempty scenes through the browser, and verify the API content.
    await page.reload();
    await expect(page.locator('.cm-content')).toContainText(HUMAN_EDIT_AFTER_REFINE);
    await page.getByRole('button', { name: 'AI 패널' }).click();
    await page.getByRole('button', { name: /장면 관리/ }).click();
    await page.getByLabel('장면 제목').fill('통합 장면 1');
    await page.getByLabel('장면 본문').fill(SCENE_ONE);
    await page.getByRole('button', { name: '+ 추가' }).click();
    await page.getByLabel('장면 제목').fill('통합 장면 2');
    await page.getByLabel('장면 본문').fill(SCENE_TWO);
    await page.getByRole('button', { name: '+ 추가' }).click();
    await expect.poll(async () => (await apiGet<Array<{ content_md: string }>>(request, `/chapters/${first.id}/scenes`)).length, { timeout: 10_000 }).toBe(2);

    page.once('dialog', (dialog) => dialog.accept());
    const mergeResponse = page.waitForResponse((response) =>
      response.url().includes(`/api/v1/chapters/${first.id}/content_from_scenes`) && response.request().method() === 'PUT',
    );
    await page.getByRole('button', { name: /본문으로 합치기/ }).click();
    const merge = await mergeResponse;
    expect(merge.status()).toBe(200);
    const merged = await merge.json() as Chapter;
    expect(merged.content_md).toBe(MERGED_SCENES);
    expect(merged.revision).toBe(5);
    await expectChapter(request, first.id, MERGED_SCENES, 5);

    // Restore the pre-merge snapshot with a held/forwarded real request, then type during the in-flight restore.
    let heldRestore: Route | null = null;
    await page.route(`**/api/v1/chapters/${first.id}/restore`, async (route) => {
      if (route.request().method() === 'POST' && heldRestore === null) {
        heldRestore = route;
        return;
      }
      await route.continue();
    });

    await page.keyboard.press('Escape');
    const closePanel = page.getByRole('button', { name: '패널 닫기' });
    if (await closePanel.isVisible({ timeout: 1_000 }).catch(() => false)) await closePanel.click();
    const snapshots = await apiGet<Snapshot[]>(request, `/chapters/${first.id}/snapshots`);
    const preMergeSnapshot = snapshots.find((snapshot) => snapshot.revision === 4 && snapshot.reason === 'scene_merge');
    expect(preMergeSnapshot, JSON.stringify(snapshots)).toBeTruthy();

    await page.getByRole('button', { name: /복구본/ }).click();
    await page.getByRole('button', { name: new RegExp(`revision ${preMergeSnapshot!.revision}.*scene_merge`) }).click();
    await expect(page.getByText(HUMAN_EDIT_AFTER_REFINE)).toBeVisible();
    const restoreResponse = page.waitForResponse((response) =>
      response.url().includes(`/api/v1/chapters/${first.id}/restore`) && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: /이 복구본으로 복원/ }).click();
    await expect.poll(() => heldRestore !== null, { timeout: 10_000 }).toBe(true);
    await page.keyboard.press('Escape');
    await fillEditor(page, LATE_RESTORE_TEXT);
    await heldRestore!.continue();
    const restore = await restoreResponse;
    expect(restore.status()).toBe(200);
    const restored = await restore.json() as Chapter;
    expect(restored.content_md).toBe(HUMAN_EDIT_AFTER_REFINE);
    expect(restored.revision).toBe(6);
    await expectChapter(request, first.id, HUMAN_EDIT_AFTER_REFINE, 6);
    await expect(page.locator('.cm-content')).toContainText(LATE_RESTORE_TEXT);
    await expect(page.getByText('저장 충돌 — 원고 확인 필요')).toBeVisible();

    await page.unroute(`**/api/v1/chapters/${first.id}/content`);
    await page.unroute(`**/api/v1/chapters/${first.id}/restore`);
  });
});
