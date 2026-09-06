import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { writeFileSync, mkdirSync } from 'node:fs';

/**
 * a11y 자동 스캔 (TC-501 자동화분) — axe-core로 전 화면을 훑고
 * critical·serious 위반은 차단, 나머지는 baseline 리포트로 기록한다.
 * NVDA·키보드 실기기 항목(TC-503~505)은 여전히 수동 대상.
 */

const REPORT_DIR = 'e2e/a11y';

type Violation = {
  id: string;
  impact: string | null;
  nodes: { target: string[] }[];
};

async function scan(page: import('@playwright/test').Page, name: string) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const blocking = results.violations.filter((v) =>
    ['critical', 'serious'].includes(v.impact ?? ''),
  );
  return { name, blocking, all: results.violations };
}

test.describe('a11y axe-core 스캔', () => {
  let projectId = 0;

  test.beforeAll(async ({ request }) => {
    // 기존 검증 프로젝트 정리 후 생성 (에디터·캐릭터·로어북 화면 확보)
    const res = await request.get('/api/v1/projects');
    for (const p of (await res.json()) as Array<{ id: number; title: string }>) {
      if (p.title === 'A11Y스캔') await request.delete(`/api/v1/projects/${p.id}`);
    }
    const pres = await request.post('/api/v1/projects', { data: { title: 'A11Y스캔' } });
    projectId = ((await pres.json()) as { id: number }).id;
    await request.post(`/api/v1/projects/${projectId}/chapters`, {
      data: { volume: 1, title: '1화', sort_order: 1 },
    });
  });

  test.afterAll(async ({ request }) => {
    if (projectId) await request.delete(`/api/v1/projects/${projectId}`);
  });

  test('critical·serious 위반 0건 — 홈/설정/작품 화면', async ({ page }) => {
    mkdirSync(REPORT_DIR, { recursive: true });
    const scans: Awaited<ReturnType<typeof scan>>[] = [];

    await page.goto('/');
    scans.push(await scan(page, 'home'));

    await page.goto('/settings');
    scans.push(await scan(page, 'settings'));

    await page.goto(`/projects/${projectId}/write`);
    await page.locator('.cm-content').waitFor({ state: 'visible', timeout: 15_000 });
    scans.push(await scan(page, 'editor'));

    await page.goto(`/projects/${projectId}/characters`);
    await page.waitForTimeout(800);
    scans.push(await scan(page, 'characters'));

    await page.goto(`/projects/${projectId}/lore`);
    await page.waitForTimeout(800);
    scans.push(await scan(page, 'lore'));

    // baseline 리포트 저장 — 전체 위반(id·impact·대상) 기록
    const report = scans.map((s) => ({
      screen: s.name,
      blocking: s.blocking.map((v: Violation) => ({
        id: v.id, impact: v.impact, targets: v.nodes.slice(0, 5).map((n) => n.target.join(' ')),
      })),
      minor: s.all
        .filter((v) => !['critical', 'serious'].includes(v.impact ?? ''))
        .map((v) => v.id),
    }));
    writeFileSync(`${REPORT_DIR}/baseline.json`, JSON.stringify(report, null, 2));

    const blocking = scans.flatMap((s) =>
      s.blocking.map((v) => `${s.name}: ${v.id} (${v.nodes.length}노드)`),
    );
    expect(blocking, `a11y 차단 위반:\n${blocking.join('\n')}`).toHaveLength(0);
  });
});
