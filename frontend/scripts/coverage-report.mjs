#!/usr/bin/env node
/**
 * V01 — coverage-raw/*.json(V8 function coverage)을
 * v8-to-istanbul로 소스 매핑해 istanbul coverage 산출물을 만든다.
 *
 * 출력:
 *   coverage-final.json    — 병합된 istanbul coverage map
 *   coverage-summary.json  — 파일별 lines/branches/functions 측정 요약
 *   coverage/              — html + text 리포트 (istanbul-lib-report)
 */
import fs from "node:fs";
import path from "node:path";
import v8toIstanbul from "v8-to-istanbul";
import libCoverage from "istanbul-lib-coverage";
import libReport from "istanbul-lib-report";
import reports from "istanbul-reports";

const FRONTEND_ROOT = path.resolve(import.meta.dirname, "..");
const RAW_DIR = path.resolve(process.env.PW_COVERAGE_DIR || "coverage-raw");
const SRC_RE = /^https?:\/\/[^/]+\/src\//;
const SRC_EXT_RE = /\.(ts|tsx|css)$/;

const files = fs.existsSync(RAW_DIR)
  ? fs.readdirSync(RAW_DIR).filter((f) => f.endsWith(".json")).sort()
  : [];
if (!files.length) {
  console.error("no coverage-raw entries — run suites with PW_COVERAGE=1 first");
  process.exit(1);
}

const map = libCoverage.createCoverageMap({});
let merged = 0;
const skipped = new Set();
for (const file of files) {
  let entries;
  try {
    entries = JSON.parse(fs.readFileSync(path.join(RAW_DIR, file), "utf-8"));
  } catch (err) {
    console.error(`parse failed, skipping raw file ${file}: ${err.message}`);
    continue;
  }
  for (const entry of entries) {
    let url;
    try {
      url = entry.url ? new URL(entry.url) : null;
    } catch {
      url = null;
    }
    if (!url || !SRC_RE.test(entry.url || "") || !SRC_EXT_RE.test(url.pathname)) {
      if (entry.url) {
        try {
          skipped.add(new URL(entry.url).pathname.split("/")[1] || entry.url);
        } catch {
          skipped.add(entry.url.slice(0, 60));
        }
      }
      continue;
    }
    try {
      // 스위트별 포트(origin)가 키에 들어가면 같은 소스가 분리 병합된다 —
      // 실제 파일시스템 경로로 정규화해 union coverage를 얻는다
      const scriptPath = path.join(FRONTEND_ROOT, url.pathname);
      const converter = v8toIstanbul(scriptPath, 0, {
        source: entry.source,
      });
      await converter.load();
      converter.applyCoverage(entry.functions);
      map.merge(converter.toIstanbul());
      merged += 1;
    } catch (err) {
      console.error(`convert failed: ${entry.url}: ${err.message}`);
    }
  }
}

fs.writeFileSync("coverage-final.json", JSON.stringify(map.toJSON()));

const summary = {};
for (const file of map.files()) {
  const fc = map.fileCoverageFor(file);
  const s = fc.toSummary();
  const rel = file.replace(/^.*\/src\//, "src/");
  summary[rel] = {
    lines: { total: s.lines.total, covered: s.lines.covered, pct: s.lines.pct },
    branches: { total: s.branches.total, covered: s.branches.covered, pct: s.branches.pct },
    functions: { total: s.functions.total, covered: s.functions.covered, pct: s.functions.pct },
    statements: { total: s.statements.total, covered: s.statements.covered, pct: s.statements.pct },
  };
}
const total = map.getCoverageSummary();
summary.__total__ = {
  lines: { total: total.lines.total, covered: total.lines.covered, pct: total.lines.pct },
  branches: { total: total.branches.total, covered: total.branches.covered, pct: total.branches.pct },
  functions: { total: total.functions.total, covered: total.functions.covered, pct: total.functions.pct },
  statements: { total: total.statements.total, covered: total.statements.covered, pct: total.statements.pct },
};
fs.writeFileSync("coverage-summary.json", JSON.stringify(summary, null, 2));

const context = libReport.createContext({
  dir: "coverage",
  coverageMap: map,
});
reports.create("html", { skipEmpty: false }).execute(context);
reports.create("text-summary").execute(context);

console.log(`raw files: ${files.length}, src entries merged: ${merged}`);
console.log(`skipped non-src prefixes: ${[...skipped].join(", ") || "(none)"}`);
console.log(`TOTAL lines ${total.lines.pct}% (${total.lines.covered}/${total.lines.total})` +
  ` | branches ${total.branches.pct}% (${total.branches.covered}/${total.branches.total})` +
  ` | functions ${total.functions.pct}% (${total.functions.covered}/${total.functions.total})`);
for (const [file, s] of Object.entries(summary)) {
  if (file === "__total__") continue;
  console.log(`  ${file}: lines ${s.lines.pct}% (${s.lines.covered}/${s.lines.total}), ` +
    `branches ${s.branches.pct}% (${s.branches.covered}/${s.branches.total})`);
}
