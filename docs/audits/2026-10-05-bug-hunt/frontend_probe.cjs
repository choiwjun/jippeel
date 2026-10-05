/* Full application browser probes with synthetic API responses only.
 * Run after starting vite.fixture.config.ts on dedicated port 15483.
 */
const { createRequire } = require('node:module');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const requireFrontend = createRequire(path.resolve(__dirname, '../../../frontend/package.json'));
const { chromium, expect: baseExpect } = requireFrontend('@playwright/test');
const expect = baseExpect.configure({ timeout: 15000 });
const base = 'http://127.0.0.1:15483';
const stamp = '2026-10-05T00:00:00Z';
const results = [];
const verifyFixes = process.argv.includes('--verify-fixes');

async function fixture(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  const violations = [];
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  const writes = [];
  const chapters = new Map([10, 11].map((id, index) => [id, {
    id, project_id: 1, volume: 1, sort_order: index + 1,
    title: `${index + 1}화`, status: '초고', flow_stage: 'planning',
    word_count_cache: 8, memo: null, revision: 0,
    content_md: id === 10 ? 'ORIGINAL_BODY' : 'SECOND_BODY', created_at: stamp, updated_at: stamp,
  }]));
  const scenes = new Map([
    [101, { id: 101, chapter_id: 10, sort_order: 1, title: '장면A', content_md: 'SCENE_A_ORIGINAL', created_at: stamp, updated_at: stamp }],
    [102, { id: 102, chapter_id: 10, sort_order: 2, title: '장면B', content_md: 'SCENE_B_ORIGINAL', created_at: stamp, updated_at: stamp }],
  ]);
  const project = { id: 1, title: '합성 조사 작품', genre: null, concept: null,
    synopsis: null, platform_note: null, style_profile: null, serial_state: 'ongoing',
    chapter_count: 2, total_chars: 16, created_at: stamp, updated_at: stamp };
  let holdManuscriptWrites = false;
  const heldWrites = [];
  const heldMetaWrites = [];
  const heldChapterGets = [];
  let holdNextChapterGet = null;
  let holdMetaWrites = false;
  let nextWriteFailure = null;
  await context.route('**/*', async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (url.origin !== base) {
      violations.push(`external:${req.url()}`);
      return route.abort();
    }
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const p = url.pathname.replace('/api/v1', '');
    const method = req.method();
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    const body = () => req.postDataJSON();
    if (method === 'GET' && p === '/auth/status') return json({ enabled: false, configured: false });
    if (method === 'GET' && p === '/projects') return json([project]);
    if (method === 'GET' && p === '/projects/1') return json(project);
    if (method === 'GET' && p === '/projects/1/chapters') return json([...chapters.values()].map(({ content_md, ...meta }) => meta));
    let match = p.match(/^\/chapters\/(\d+)$/);
    if (match && method === 'GET') {
      const id = Number(match[1]);
      const response = { ...chapters.get(id) };
      if (holdNextChapterGet === id) {
        holdNextChapterGet = null;
        await new Promise(resolve => heldChapterGets.push(resolve));
      }
      return json(response);
    }
    if (match && method === 'PATCH') {
      const id = Number(match[1]);
      const changes = body();
      writes.push({ kind: 'chapter_meta', id, body: changes });
      Object.assign(chapters.get(id), changes);
      const response = { ...chapters.get(id) };
      if (holdMetaWrites) await new Promise(resolve => heldMetaWrites.push(resolve));
      return json(response);
    }
    match = p.match(/^\/chapters\/(\d+)\/content$/);
    if (match && method === 'PUT') {
      const id = Number(match[1]);
      const changes = body();
      writes.push({ kind: 'manuscript', id, body: changes });
      if (holdManuscriptWrites) await new Promise(resolve => heldWrites.push(resolve));
      const ch = chapters.get(id);
      if (nextWriteFailure !== null) {
        const status = nextWriteFailure;
        nextWriteFailure = null;
        if (status === 409) {
          ch.revision += 1;
          ch.content_md = 'REMOTE_REVISION';
          return json({ detail: { code: 'revision_conflict', message: 'synthetic revision conflict', current_revision: ch.revision } }, 409);
        }
        return json({ detail: 'synthetic save failure' }, status);
      }
      if (changes.expected_revision !== ch.revision) return json({ detail: { code: 'revision_conflict', current_revision: ch.revision } }, 409);
      Object.assign(ch, { content_md: changes.content_md, revision: ch.revision + 1 });
      return json(ch);
    }
    match = p.match(/^\/chapters\/(\d+)\/scenes$/);
    if (match && method === 'GET') return json([...scenes.values()].filter(s => s.chapter_id === Number(match[1])));
    match = p.match(/^\/scenes\/(\d+)$/);
    if (match && method === 'PATCH') {
      const id = Number(match[1]);
      const changes = body();
      writes.push({ kind: 'scene', id, body: changes });
      Object.assign(scenes.get(id), changes);
      return json(scenes.get(id));
    }
    match = p.match(/^\/chapters\/(\d+)\/flow$/);
    if (match && method === 'GET') return json({ chapter_id: Number(match[1]), flow_stage: 'planning', last_event: null });
    if (method === 'GET' && /^\/chapters\/\d+\/resume$/.test(p)) return json({
      pending_refine_runs: 0, scene_count: 2, next_empty_scene: null,
      goal_changed_since_transition: false, manuscript_changed_since_transition: false,
    });
    if (method === 'GET' && /^\/chapters\/\d+\/goal$/.test(p)) return json({ goal: null, goal_version: null });
    if (method === 'GET' && /^\/chapters\/\d+\/snapshots$/.test(p)) return json([]);
    if (method === 'GET' && /^\/chapters\/\d+\/generation-runs$/.test(p)) return json([]);
    if (method === 'GET' && /^\/chapters\/\d+\/quality$/.test(p)) return json({ metrics: { hook_present: true }, suggested_preset_names: [] });
    if (method === 'GET' && /^\/projects\/\d+\/(characters|foreshadows|foreshadows\/match|memories|improvement-rules)$/.test(p)) return json([]);
    if (method === 'GET' && /^\/projects\/\d+\/trend-pack$/.test(p)) return json({ detail: 'not found' }, 404);
    if (method === 'GET' && p === '/ai/presets') return json([]);
    violations.push(`${method}:${p}`);
    return json({ detail: 'Unmocked audit request' }, 599);
  });
  await page.goto(`${base}/projects/1/write`, { waitUntil: 'commit' });
  try {
    await expect(page.locator('.cm-content')).toContainText('ORIGINAL_BODY', { timeout: 60000 });
  } catch (error) {
    console.error(JSON.stringify({ fixture_init: { violations, pageErrors, body: (await page.locator('body').innerText()).slice(0, 2000) } }));
    throw error;
  }
  return { page, context, violations, writes, chapters, scenes,
    holdWrites: () => { holdManuscriptWrites = true; },
    release: () => { holdManuscriptWrites = false; for (const resolve of heldWrites.splice(0)) resolve(); },
    holdMeta: () => { holdMetaWrites = true; },
    releaseMeta: () => { holdMetaWrites = false; for (const resolve of heldMetaWrites.splice(0)) resolve(); },
    failNextWrite: status => { nextWriteFailure = status; },
    holdNextGet: id => { holdNextChapterGet = id; },
    pendingGets: () => heldChapterGets.length,
    releaseGets: () => { for (const resolve of heldChapterGets.splice(0)) resolve(); },
  };
}

async function closeFixture(f) {
  assert.deepEqual(f.violations, [], 'API/external request escapes');
  f.release();
  f.releaseMeta();
  f.releaseGets();
  await f.context.close();
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    // Saving edited scene A should send the edited buffer, not its old server body.
    let f = await fixture(browser);
    await f.page.keyboard.press('Alt+a');
    await f.page.getByRole('button', { name: '장면 관리 열기' }).click();
    const dialog = f.page.getByRole('dialog').filter({ has: f.page.getByRole('heading', { name: '현재 회차 장면 관리' }) });
    await dialog.getByRole('button', { name: /장면A/ }).click();
    await dialog.getByRole('textbox', { name: '장면 본문' }).fill('SCENE_A_EDITED');
    const rowA = dialog.getByRole('button', { name: /^장면A/ }).locator('..');
    await rowA.getByRole('button', { name: '저장', exact: true }).click();
    await expect.poll(() => f.writes.filter(w => w.kind === 'scene').length).toBe(1);
    const sceneWrite = f.writes.find(w => w.kind === 'scene');
    results.push({ case: 'scene_edit_reset_on_save', request: sceneWrite,
      edited_text: 'SCENE_A_EDITED', scene_a_after: { ...f.scenes.get(101) },
      [verifyFixes ? 'fix_verified' : 'defect_confirmed']: sceneWrite.body.content_md === (verifyFixes ? 'SCENE_A_EDITED' : 'SCENE_A_ORIGINAL') });
    assert.equal(sceneWrite.id, 101);
    assert.equal(sceneWrite.body.content_md, verifyFixes ? 'SCENE_A_EDITED' : 'SCENE_A_ORIGINAL');
    await closeFixture(f);

    // A memo typed for chapter 10 must retain its chapter identity across debounce.
    f = await fixture(browser);
    await f.page.getByRole('button', { name: '메모 편집' }).click();
    await f.page.getByPlaceholder('회차 메모…').fill('MEMO_FOR_CHAPTER_10');
    await f.page.getByRole('button', { name: /2화/ }).click();
    await expect(f.page.locator('.cm-content')).toContainText('SECOND_BODY');
    await expect.poll(() => f.writes.filter(w => w.kind === 'chapter_meta').length).toBe(1);
    const memoWrite = f.writes.find(w => w.kind === 'chapter_meta');
    results.push({ case: 'memo_chapter_switch', request: memoWrite,
      chapter_10_memo: f.chapters.get(10).memo, chapter_11_memo: f.chapters.get(11).memo,
      [verifyFixes ? 'fix_verified' : 'defect_confirmed']: memoWrite.id === (verifyFixes ? 10 : 11) });
    assert.equal(memoWrite.id, verifyFixes ? 10 : 11);
    assert.equal(memoWrite.body.memo, 'MEMO_FOR_CHAPTER_10');
    await closeFixture(f);

    // Metadata response should update the displayed selected chapter status.
    f = await fixture(browser);
    await f.page.getByRole('combobox', { name: '회차 상태 변경' }).selectOption('수정중');
    await expect.poll(() => f.chapters.get(10).status).toBe('수정중');
    await expect(f.page.getByRole('button', { name: /1화/ })).toContainText('수정중');
    if (verifyFixes) await expect(f.page.getByRole('combobox', { name: '회차 상태 변경' })).toHaveValue('수정중');
    const displayedStatus = await f.page.getByRole('combobox', { name: '회차 상태 변경' }).inputValue();
    results.push({ case: 'metadata_cache_stale', backend_status: f.chapters.get(10).status,
      displayed_status: displayedStatus, [verifyFixes ? 'fix_verified' : 'defect_confirmed']: displayedStatus === (verifyFixes ? '수정중' : '초고') });
    assert.equal(displayedStatus, verifyFixes ? '수정중' : '초고');
    await closeFixture(f);

    // Explicit export while autosave is pending should include visible draft text.
    f = await fixture(browser);
    f.holdWrites();
    await f.page.locator('.cm-content').fill('VISIBLE_UNSAVED_NEW_BODY');
    await expect(f.page.locator('.cm-content')).toContainText('VISIBLE_UNSAVED_NEW_BODY');
    await f.page.getByRole('button', { name: '내보내기 메뉴' }).click();
    const downloadPromise = f.page.waitForEvent('download');
    await f.page.getByRole('menuitem', { name: '마크다운 (.md)', exact: true }).click();
    if (verifyFixes) {
      await expect.poll(() => f.writes.filter(w => w.kind === 'manuscript').length).toBe(1);
      f.release();
    }
    const download = await downloadPromise;
    const text = fs.readFileSync(await download.path(), 'utf8');
    if (verifyFixes) assert.equal(download.suggestedFilename(), '1화.md');
    results.push({ case: 'export_pending_draft', editor_text: 'VISIBLE_UNSAVED_NEW_BODY',
      exported_text: text, [verifyFixes ? 'fix_verified' : 'defect_confirmed']: text === (verifyFixes ? 'VISIBLE_UNSAVED_NEW_BODY' : 'ORIGINAL_BODY') });
    assert.equal(text, verifyFixes ? 'VISIBLE_UNSAVED_NEW_BODY' : 'ORIGINAL_BODY');
    f.release();
    await closeFixture(f);

    if (verifyFixes) {
      // A delayed metadata response must preserve a later acknowledged manuscript.
      f = await fixture(browser);
      f.holdMeta();
      await f.page.getByRole('combobox', { name: '회차 상태 변경' }).selectOption('수정중');
      await expect.poll(() => f.writes.filter(w => w.kind === 'chapter_meta').length).toBe(1);
      await f.page.locator('.cm-content').fill('NEWER_ACKNOWLEDGED_BODY');
      await f.page.keyboard.press('Control+s');
      await expect.poll(() => f.chapters.get(10).revision).toBe(1);
      f.releaseMeta();
      await expect(f.page.getByRole('combobox', { name: '회차 상태 변경' })).toHaveValue('수정중');
      await f.page.getByRole('button', { name: '내보내기 메뉴' }).click();
      const lateDownload = f.page.waitForEvent('download');
      await f.page.getByRole('menuitem', { name: '마크다운 (.md)', exact: true }).click();
      const lateText = fs.readFileSync(await (await lateDownload).path(), 'utf8');
      assert.equal(lateText, 'NEWER_ACKNOWLEDGED_BODY');
      results.push({ case: 'late_metadata_preserves_manuscript', exported_text: lateText, fix_verified: true });
      await closeFixture(f);

      // Both chapter drafts, including an unmounted chapter, must reach a bundle.
      f = await fixture(browser);
      f.holdWrites();
      await f.page.locator('.cm-content').fill('FIRST_LATEST_DRAFT');
      await f.page.getByRole('button', { name: /2화/ }).click();
      await expect(f.page.locator('.cm-content')).toContainText('SECOND_BODY');
      await f.page.locator('.cm-content').fill('SECOND_LATEST_DRAFT');
      Object.assign(f.chapters.get(10), { title: '후반 회차', volume: 2, sort_order: 1 });
      Object.assign(f.chapters.get(11), { title: '초반 회차', volume: 1, sort_order: 9 });
      await f.page.getByRole('button', { name: '내보내기 메뉴' }).click();
      const bundleDownload = f.page.waitForEvent('download');
      await f.page.getByRole('menuitem', { name: '전 회차 마크다운 (.md)', exact: true }).click();
      await expect.poll(() => f.writes.filter(w => w.kind === 'manuscript').length).toBe(2);
      f.release();
      const bundleText = fs.readFileSync(await (await bundleDownload).path(), 'utf8');
      assert.ok(bundleText.includes('FIRST_LATEST_DRAFT') && bundleText.includes('SECOND_LATEST_DRAFT'));
      assert.ok(bundleText.includes('# 1권 초반 회차\n\nSECOND_LATEST_DRAFT'));
      assert.ok(bundleText.includes('# 2권 후반 회차\n\nFIRST_LATEST_DRAFT'));
      assert.ok(bundleText.indexOf('# 1권 초반 회차') < bundleText.indexOf('# 2권 후반 회차'));
      results.push({ case: 'bundle_flushes_all_chapter_drafts', exported_text: bundleText, fix_verified: true });
      await closeFixture(f);

      // A fresh GET must not rebase an existing dirty draft over another writer.
      f = await fixture(browser);
      f.holdWrites();
      let concurrentDownloads = 0;
      f.page.on('download', () => { concurrentDownloads += 1; });
      await f.page.locator('.cm-content').fill('LOCAL_CONCURRENT_DRAFT');
      Object.assign(f.chapters.get(10), { revision: 1, content_md: 'OTHER_WRITER_COMMITTED' });
      await f.page.getByRole('button', { name: '내보내기 메뉴' }).click();
      await f.page.getByRole('menuitem', { name: '전 회차 마크다운 (.md)', exact: true }).click();
      await expect.poll(() => f.writes.filter(w => w.kind === 'manuscript').length).toBe(1);
      assert.equal(f.writes.find(w => w.kind === 'manuscript').body.expected_revision, 0);
      f.release();
      await expect(f.page.getByText(/내보내기 실패:/)).toBeVisible();
      assert.equal(concurrentDownloads, 0);
      assert.equal(f.chapters.get(10).content_md, 'OTHER_WRITER_COMMITTED');
      await expect(f.page.locator('.cm-content')).toContainText('LOCAL_CONCURRENT_DRAFT');
      results.push({ case: 'bundle_preserves_concurrent_revision', downloads: concurrentDownloads,
        server_text: f.chapters.get(10).content_md, local_draft_preserved: true, fix_verified: true });
      await closeFixture(f);

      // A GET begun before autosave must not roll back a newer ACK on arrival.
      f = await fixture(browser);
      f.holdWrites();
      f.holdNextGet(10);
      await f.page.locator('.cm-content').fill('ACK_AFTER_EXPORT_GET');
      await f.page.getByRole('button', { name: '내보내기 메뉴' }).click();
      const racedDownload = f.page.waitForEvent('download');
      await f.page.getByRole('menuitem', { name: '전 회차 마크다운 (.md)', exact: true }).click();
      await expect.poll(f.pendingGets).toBe(1);
      await f.page.keyboard.press('Control+s');
      await expect.poll(() => f.writes.filter(w => w.kind === 'manuscript').length).toBe(1);
      f.release();
      await expect.poll(() => f.chapters.get(10).revision).toBe(1);
      await expect(f.page.getByText('저장됨', { exact: true })).toBeVisible();
      f.releaseGets();
      const racedText = fs.readFileSync(await (await racedDownload).path(), 'utf8');
      assert.ok(racedText.includes('ACK_AFTER_EXPORT_GET'));
      assert.equal(f.writes.filter(w => w.kind === 'manuscript').length, 1);
      results.push({ case: 'bundle_ignores_get_older_than_save_ack', manuscript_writes: 1, fix_verified: true });
      await closeFixture(f);

      for (const status of [500, 409]) {
        f = await fixture(browser);
        let downloads = 0;
        f.page.on('download', () => { downloads += 1; });
        f.failNextWrite(status);
        await f.page.locator('.cm-content').fill('PRESERVED_LOCAL_DRAFT');
        await f.page.getByRole('button', { name: '내보내기 메뉴' }).click();
        await f.page.getByRole('menuitem', { name: '마크다운 (.md)', exact: true }).click();
        await expect(f.page.getByText(/내보내기 실패:/)).toBeVisible();
        assert.equal(downloads, 0);
        await expect(f.page.locator('.cm-content')).toContainText('PRESERVED_LOCAL_DRAFT');
        results.push({ case: `export_blocks_save_${status}`, downloads, local_draft_preserved: true, fix_verified: true });
        await closeFixture(f);
      }
    }
    console.log(JSON.stringify({ results, unmocked_api_requests: [], real_provider_calls: 0 }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(JSON.stringify({ completed_results: results }, null, 2)); console.error(error); process.exitCode = 1; });
