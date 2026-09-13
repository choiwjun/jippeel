# V01 수용 — 프론트 source-mapped coverage 계측

- 수용일: 2026-09-13
- 사양: [V01 사양](../../superpowers/plans/2026-09-13-v01-frontend-coverage-spec.md)
- 상태: **수용** (uncommitted)

## 수용 범위

opt-in Playwright V8 coverage 계측 — **제품 기능이 아니라 측정 인프라**.

- `frontend/e2e/coverage-test.ts` — `PW_COVERAGE=1`일 때만 `startJSCoverage({resetOnNavigation:false})` 수집, `coverage-raw/<worker>-<retry>-<testid>.json` 저장. 미설정 시 순수 passthrough(오버헤드 0). `page.coverage` 부재(비-Chromium)·`page.isClosed()` 모두 안전 가드.
- `memory-scoped-coverage.ts`·`quality-scoped-coverage.ts` — 기존 scoped 플래그 동작 보존 + `PW_COVERAGE` 전체 수집 공유.
- `scripts/coverage-report.mjs` — raw V8 → source-map 경유 Istanbul 변환. **실제 fs 경로 키로 union 병합**(포트 분리 결함 수정), `.ts/.tsx/.css` 소스만 필터, 정렬된 입력·per-file 예외 격리. 산출: `coverage-final.json` + `coverage-summary.json` + `coverage/` html·text 리포트.
- `scripts/run-coverage.sh` — 11개 fixture config 순차 실행, 개별 실패·리포트 실패 모두 exit 전파.
- 8개 평문 스펙 import 전환 + `playwright.quality.config.ts` 추가(11개째). preservation·memory·ai-context는 기존 래퍼 체인 경유.

## 측정 결과(2026-09-13 실행값 — 기록이지 목표치 아님)

| 지표 | 값 |
|------|-----|
| 스위트 | 11개 config 전부 통과 |
| 테스트 | **128 passed / 0 failed** |
| tripwire | no escapes 전부 |
| raw coverage | 127 파일(1개는 테스트가 `page.close()` — 수집 불가 의도) |
| 소스 파일 | **57 unique**(실제 fs 경로 키) |
| lines | **83.27%** (9702/11651) |
| branches | **83.28%** (1450/1741) — V8 block-coverage 근사치 |
| functions | **60.92%** (410/673) |

해석: fixture E2E가 실행하는 소스만 반영. 미실행 파일·경로는 covered=0. 이 수치는 "프론트 N% 품질" 주장이 아니라 **재현 가능한 측정 스냅샷**이다.

## 검증 근거

- 전체 실행: `coverage-full-run.txt` (11 스위트·128P·tripwire no escapes)
- 리포트 실행: `report-output.txt` (57 fs 키·union totals·html 생성)
- `tsc --noEmit` exit 0
- 독립 검토 2건: ①PASS_WITH_NOTES ②FAIL(BLOCKER 포트 분리 병합)→수정·재검증 ([review-log.md](review-log.md))
- backend 회귀 무손상: 676P/1skip/violations 0

## 비수용(명시 제외)

- coverage 임계 목표치·CI 강제 — 없음. 수동 opt-in 측정만.
- unit test 프레임워크 도입 — 별도 슬라이스.
- 비-Chromium 브라우저 수집 — `page.coverage` API 한계(가드로 안전 스킵).
- 테스트 본문이 `page.close()`하는 케이스의 수집 — API 불가(1건, 의도 스킵).
- Windows 경로 계측 — 리포트 스크립트는 POSIX 경로 가정(실행 환경 범위).

## 잔여

- 향후 스위트 추가 시 `run-coverage.sh` CONFIGS 갱신 필요.
- coverage 수치의 추세 비교는 향후 필요 시 별도 도구.
