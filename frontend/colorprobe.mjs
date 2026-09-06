import { chromium } from 'playwright';

const api = 'http://localhost:8000/api/v1';
const j = (r) => r.json();
const projects = await j(await fetch(api + '/projects'));
let pid = projects.find((p) => p.title === '색상검증')?.id;
if (!pid) {
  const res = await fetch(api + '/projects', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: '색상검증' }),
  });
  pid = (await j(res)).id;
  await fetch(api + '/projects/' + pid + '/chapters', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ volume: 1, title: '1화', sort_order: 1 }),
  });
}

const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/projects/' + pid + '/write');
await p.waitForSelector('.cm-content', { timeout: 15000 });
const info = await p.evaluate(() => {
  const el = document.querySelector('.ml-4 [class*="status-draft"], .ml-4 .rounded-full');
  if (!el) return { found: false };
  const cs = getComputedStyle(el);
  const layers = [];
  let n = el;
  for (let i = 0; i < 4 && n; i++) { layers.push(getComputedStyle(n).backgroundColor); n = n.parentElement; }
  return { found: true, cls: el.className, color: cs.color, badgeBg: cs.backgroundColor, layers };
});
console.log(JSON.stringify(info, null, 2));
await b.close();
