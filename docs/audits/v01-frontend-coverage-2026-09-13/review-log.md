# V01 독립 검토 기록 — 프론트 source-mapped coverage 계측

- 슬라이스: V01 (frontend test infrastructure)
- 검토일: 2026-09-13
- 검토자: 독립 subagent 2건 — ①수집기·fixture 계약, ②리포트 파이프라인
- 판정: ① **PASS_WITH_NOTES** · ② **FAIL → 수정 후 재검증 통과**

## 검토 ① 수집기·fixture (PASS_WITH_NOTES)

확인: `PW_COVERAGE=1` 게이트 완전(미설정 시 순수 passthrough)·scoped 래퍼 보존·worker×test 고유 파일명·격리·tripwire 불변·실 API 경로 없음.

| # | 심각도 | 지적 | 처리 |
|---|--------|------|------|
| F1 | MED | 포트별 URL이 Istanbul 키 → 같은 파일 분리 병합 | **수정** — 실제 fs 경로로 정규화(검토②와 동일 지적, 하단 참조) |
| F2 | NOTE | spec `resetOnNavigation:true` vs 코드 `false` | **수정** — 사양 정정(코드가 정확함) |
| F3 | NOTE | 123 테스트 vs 122 파일 — `page.close()` 테스트는 stop 불가 | **수용·주석 추가** — `!page.isClosed()` 가드 의도 동작 |
| F4 | LOW | retry/다중 worker 파일명 충돌 잠재 | **수정** — `testInfo.retry` 파일명 포함 |
| F5 | NOTE | `playwright.quality.config.ts`(coverage 가능) 미포함 | **수정** — CONFIGS에 추가(11개) |
| F6 | LOW | coverage 모드 teardown 오류가 테스트를 실패로 뒤집을 수 있음 | **수용** — opt-in 측정 모드의 fail-loud 의도 동작 |
| F7 | NOTE | `page.coverage`는 Chromium 전용 | **수정** — `page.coverage &&` 가드 추가 |
| F8 | NOTE | env 읽기 비대칭(모듈 로드 1회 vs 테스트당) | **수용** — env는 워커 기동 전 고정, 무해 |
| F9 | NOTE | coverage 산출물 gitignore 누락·dead 라인 | **수정** — `.gitignore` 4행 추가·dead 라인 제거 |
| F10 | NOTE | fixture `page` 외 대상 미수집 | **수용** — 현재 스펙에 보조 page 없음 확인 |

## 검토 ② 리포트 파이프라인 (FAIL → 수정)

**검토 중 worktree가 라이브 상태였음** — 검토자는 4-port 맵·`http:/fixture/` 맵(수정 중간 단계)·삭제된 산출물을 관찰. BLOCKER는 이미 수정 진행 중이던 동일 결함.

| # | 심각도 | 지적 | 처리 |
|---|--------|------|------|
| 1 | BLOCKER | `v8toIstanbul(entry.url)` — host:port가 키 → 동일 파일이 스위트 수만큼 분리, `__total__`이 10× 분모의 가중 평균, per-file은 last-writer-wins | **수정·검증** — `path.join(FRONTEND_ROOT, url.pathname)`로 실제 fs 경로 키. 결과: 57개 실경로 키·비-fs 0·union totals(83.27%) 검증. per-file도 union 값 |
| 2 | MED | report 실패가 `exit $fail`에 마스킹 | **수정** — `\|\| fail=1` |
| 3 | MED | `JSON.parse` 미보호 — 손상 raw 1개가 전체 중단 | **수정** — per-file try/catch + skip·log |
| 4 | MED | `readdirSync` 비정렬 — 산출물 순서 비결정적 | **수정** — `files.sort()` |
| 5 | MED | 감사 증거 자기불일치(구 수치 로그 vs union 요약) | **수정** — 수정 후 전체 재실행·증거 재캡처(이 디렉터리). 11번째 스위트=quality 추가 명시 |
| 6 | LOW | `istanbul-lib-report`·`istanbul-reports` 선언만, html 산출 주장 불일치 | **수정** — `libReport.createContext`+html+text-summary 실행, `coverage/index.html` 생성 확인 |
| 7 | LOW | skip 분기 `new URL` 미보호 | **수정** — try/catch 양쪽 |
| 8 | LOW | sourcemap 없는 항목이 transpiled coverage로 유입 | **수정** — pathname `\.(ts\|tsx\|css)$` 필터 추가 |
| 9 | NOTE | branch totals 근사치(0/0 artifacts) | **수용** — 사양 §3 "근사치" 명시 유지, 정확치로 표시하지 않음 |
| 10 | NOTE | spec `resetOnNavigation` 불일치 | **수정**(①F2와 동일) |
| 11 | NOTE | cwd 상대 출력·Windows 경로·`^` range·allowScripts | **수용** — run-coverage.sh가 cwd 고정·Windows 계측은 범위 밖·lockfile 고정 존재·기존 프로젝트 스타일 일치 |

## 재검증

- 전체 coverage 재실행(11 config): **128 tests passed · tripwire no escapes 전부 · 127 raw files**
- 리포트 재생성: 57 unique fs-path keys · `TOTAL lines 83.27% · branches 83.28% · functions 60.92%`
- html 리포트 `coverage/index.html` 생성 확인
- `tsc --noEmit` exit 0
- 증거: `coverage-full-run.txt`·`report-output.txt`·`coverage-summary.json`·`tsc.txt`·`source-hashes.txt`

## 판정 근거

검토②의 BLOCKER는 실측 재검증으로 해소됨(union 병합·실경로 키·재현 산출물). 전 지적 수정 또는 명시 수용, 증거 재캡처 완료.
