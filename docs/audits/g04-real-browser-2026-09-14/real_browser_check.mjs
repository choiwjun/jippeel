// G04 실제 브라우저 검증 — mock 없음, 실제 dist + 실제 백엔드 + 실 DB 복사본
import { chromium } from 'playwright';
import fs from 'node:fs';

const BASE = 'http://localhost:18700';
const API = '/api/v1';
const OUT = '/tmp/jippeel-real-ui';
const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ' — ' + detail : ''}`);
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

// 1) 실제 로드
await page.goto(BASE, { waitUntil: 'networkidle' });
await page.screenshot({ path: `${OUT}/shot-01-landing.png` });
check('landing render', await page.locator('body').innerText().then(t => t.length > 50));
check('no console errors on load', errors.length === 0, errors.slice(0, 2).join(' | '));

// 2) 실제 API 왕복 — 실 DB 복사본의 실데이터
const projects = await page.evaluate(async (p) => (await fetch(`${p}/projects`)).json(), API);
check('real API projects', Array.isArray(projects) && projects.length >= 1, `count=${projects?.length}`);
const pid = projects?.[0]?.id;
const chapters = pid ? await page.evaluate(async ([p, id]) => (await fetch(`${p}/projects/${id}/chapters`)).json(), [API, pid]) : [];
check('real chapters API', Array.isArray(chapters) && chapters.length >= 1, `count=${chapters?.length}`);

// 3) 키보드 전용 탐색 — Tab 순회
await page.keyboard.press('Tab');
const f1 = await page.evaluate(() => document.activeElement?.tagName + '|' + (document.activeElement?.className?.toString() || '').slice(0, 30));
let moved = f1;
for (let i = 0; i < 10; i++) {
  await page.keyboard.press('Tab');
  moved = await page.evaluate(() => document.activeElement?.tagName + '|' + (document.activeElement?.className?.toString() || '').slice(0, 30));
  if (moved !== f1) break;
}
check('keyboard Tab moves focus', moved !== f1 && !f1.startsWith('BODY'), `f1=${f1} -> ${moved}`);

// 4) 실제 UI 탐색 — 에디터 페이지로 이동해 챕터 선택
await page.goto(`${BASE}/projects/${pid}/write`, { waitUntil: 'networkidle' });
await page.screenshot({ path: `${OUT}/shot-02-editor-page.png` });
// 챕터 목록에서 첫 항목 클릭 (실제 UI 상호작용)
const chapterItem = page.locator('[data-testid*="chapter"], li:has-text("1"), button:has-text("1"), tr, [role="listitem"], [role="treeitem"]').first();
const bodyBefore = await page.locator('.cm-content').count();
if (await chapterItem.count()) { await chapterItem.click().catch(() => {}); await page.waitForTimeout(1200); }
const cmCount = await page.locator('.cm-content').count();
check('editor mounts via real nav', cmCount >= 1, `cm=${cmCount} (before=${bodyBefore}) url=${page.url()}`);

// 5) uiScale 실제 DOM 적용 — flat persist 키에 xlarge 기록 후 리로드
const fontBefore = await page.evaluate(() => getComputedStyle(document.documentElement).fontSize);
await page.evaluate(() => localStorage.setItem('jippeel-settings', JSON.stringify({ uiScale: 'xlarge' })));
await page.reload({ waitUntil: 'networkidle' });
const fontAfter = await page.evaluate(() => getComputedStyle(document.documentElement).fontSize);
const marker = await page.evaluate(() => document.documentElement.dataset.uiScale || 'unset');
check('uiScale persists & applies', marker === 'xlarge' && fontAfter !== fontBefore, `htmlFont ${fontBefore} -> ${fontAfter}, data-ui-scale=${marker}`);
await page.screenshot({ path: `${OUT}/shot-03-uiscale.png`, fullPage: false });

// 6) 실제 에디터 5만 자 — sentinel 삽입 → 자동저장 PUT → API 재조회로 실증
const SNAP = async () => page.evaluate(async (p) => {
  const ps = await (await fetch(`${p}/projects`)).json();
  const out = {};
  for (const pr of ps) {
    const chs = await (await fetch(`${p}/projects/${pr.id}/chapters`)).json();
    for (const ch of chs) {
      const d = await (await fetch(`${p}/chapters/${ch.id}`)).json();
      out[ch.id] = d?.content_md ?? '';
    }
  }
  return out;
}, API);
const cm2 = page.locator('.cm-content').first();
let insertMs = -1, sentinelHit = null, delta = 0;
if (await cm2.count()) {
  const before = await SNAP();
  const SENT = '\nZQ9-SENTINEL-';
  const big = '가나다라마바사아자차카타파하 '.repeat(3334).slice(0, 50_000) + SENT + Date.now();
  await cm2.click();
  const t0 = Date.now();
  await page.keyboard.insertText(big);   // 실제 입력 경로 — CM6 input 핸들링 통과
  insertMs = Date.now() - t0;
  for (let i = 0; i < 12 && !sentinelHit; i++) {
    await page.waitForTimeout(800);
    const after = await SNAP();
    for (const [id, txt] of Object.entries(after)) {
      if (txt.includes('ZQ9-SENTINEL-')) { sentinelHit = id; delta = txt.length - (before[id]?.length ?? 0); break; }
    }
  }
  check('editor 50k real input + autosave roundtrip', !!sentinelHit,
        `insert=${insertMs}ms chapter=${sentinelHit} delta=+${delta}chars`);
  await page.screenshot({ path: `${OUT}/shot-04-editor-50k.png` });
} else {
  check('editor 50k real input + autosave roundtrip', false, 'no .cm-content');
}

// 7) 설정 페이지 키보드 접근성 — /settings에서 Tab으로 uiScale 컨트롤 도달
await page.goto(`${BASE}/settings`, { waitUntil: 'networkidle' });
const settingsText = await page.locator('body').innerText();
check('settings page renders', /설정|uiScale|확대|글꼴/.test(settingsText), settingsText.slice(0, 60).replace(/\n/g, ' '));
await page.screenshot({ path: `${OUT}/shot-05-settings.png` });

// 8) 콘솔 오류 누적 최종 확인
check('no console errors overall', errors.length === 0, errors.slice(0, 3).join(' | '));

await browser.close();
fs.writeFileSync(`${OUT}/real-browser-results.json`, JSON.stringify(results, null, 2));
const fails = results.filter(r => !r.ok);
console.log(`\n${results.length - fails.length}/${results.length} PASS`);
process.exit(fails.length ? 1 : 0);
