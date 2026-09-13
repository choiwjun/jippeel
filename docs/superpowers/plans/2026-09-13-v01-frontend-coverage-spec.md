# V01 좁은 사양 — 프론트 source-mapped coverage 계측

- 작성일: 2026-09-13
- 슬라이스: V01(프론트 source-mapped coverage) — 원장 "계측 설정·수치 coverage. E2E 통과만으로 프론트 80%를 주장하지 않음"
- 근거: 원장 V01 행, B03/M01~M05의 국소 계측 선례(istanbul 독립 재구성)
- 경계: fixture 전용 포트·합성 데이터만. 실 API·운영 자원 없음.

## 1. 목표·비목표

### 목표
- 기존 fixture E2E 스위트 실행 동안 V8 coverage를 수집하는 계측 설정(opt-in, `PW_COVERAGE=1`).
- 수집 원시 데이터를 source map 경유로 소스 파일(`.ts/.tsx`)에 매핑한 istanbul coverage 산출물: `coverage-final.json` + 파일별 line/branch 요약.
- fixture 스위트 전체(coverage 가능한 11개 config)에 대한 수치 coverage 보고서(전체 % 주장이 아니라 **측정값 기록**).

### 비목표
- "프론트 80%" 같은 임계 목표치 주장·강제
- unit test 프레임워크 도입(vitest 등)
- 스펙의 검증 행위 자체 변경(커버리지 수집은 env 게이트 부수효과만)

## 2. 계측 설계

### 수집 — `frontend/e2e/coverage-test.ts`
- Playwright `page.coverage.startJSCoverage({resetOnNavigation:false})` / `stopJSCoverage()`의 V8 function-coverage를 테스트마다 JSON으로 저장. (`true`는 다중 네비게이션 테스트에서 이전 커버리지를 버리므로 `false`가 정확하다.)
- `PW_COVERAGE=1`일 때만 수집. 미설정 시 통과(fixture 래퍼는 no-op).
- 저장: `coverage-raw/<worker>-<testid>.json` — 항목은 `{url, source, functions}`.
- 10개 fixture 스펙의 `import { test, expect } from "@playwright/test"`를 `./coverage-test`로 변경(1행씩).

### 변환 — `frontend/scripts/coverage-report.mjs`
- `coverage-raw/*.json`을 읽어 `v8-to-istanbul`로 URL+inline sourcemap 기반 소스 매핑.
- `http://localhost:<port>/src/**`만 포함(node_modules·vite 내부 제외).
- `istanbul-lib-coverage`로 전체 병합 → `coverage-final.json` + `coverage-summary.json`(파일별 lines/branches/functions covered/total/pct) + text 요약 출력.

### 실행 — `frontend/scripts/run-coverage.sh`
1. `coverage-raw/` 초기화.
2. `PW_COVERAGE=1`로 11개 fixture config를 순차 실행.
3. `node scripts/coverage-report.mjs`로 산출물 생성.

## 3. 정직성 규칙
- 수집은 fixture 스위트가 실행한 코드만 반영 — 미실행 파일은 covered=0으로 집계됨을 명시.
- vite dev 서버의 transpiled JS + sourcemap 기반이므로 TS 소스 매핑은 근사치; `v8-to-istanbul`의 매핑 결과를 그대로 보고한다.
- 결과를 "커버리지 목표 달성"으로 표현하지 않고 "측정 스냅샷"으로 기록한다.

## 4. 검증
- `PW_COVERAGE=1`로 소규모 스위트 1개 실행 → raw JSON 생성·변환·요약 산출 확인.
- 전체 10스위트 실행 후 `coverage-summary.json`의 src 파일 집계 — audit 증거로 보존.
- 기존 스위트는 `PW_COVERAGE` 미설정 시 기존과 동일하게 통과해야 함(회귀).
- `npx tsc --noEmit` 통과.
