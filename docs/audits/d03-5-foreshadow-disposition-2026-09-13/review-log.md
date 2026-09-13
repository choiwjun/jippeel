# D03-5 복선 이관 구분 — 독립 검토 기록

날짜: 2026-09-13 / 검토자: 독립 서브에이전트 2인(백엔드·프론트), fresh 컨텍스트, 읽기 전용

## 판정

| 검토 | 판정 | 지적 |
|------|------|------|
| 백엔드 | PASS_WITH_NOTES | LOW 1 + NOTE 3 + 테스트 갭 |
| 프론트엔드 | PASS_WITH_NOTES | HIGH 1 + LOW 5 + NOTE 4 |

## 백엔드 지적 처리

| # | 지적 | 처리 |
|---|------|------|
| B1 | `?disposition=` 빈 문자열이 조용히 무시됨 — 사양상 사전 외 값은 422 | **수정** — `if disposition is not None:`로 변경, 빈 문자열 422 + 테스트 추가 |
| B2 | `disposition IS NULL` 필터 불가 | **수용** — 사양 미요구. 필요 시 후속 |
| B3 | PRAGMA OFF가 lazy BEGIN에 의존 | **수용** — 기존 migration과 동일 패턴, populated 테스트로 입증됨 |
| B4 | 손상 행(설치+disposition)도 `{disposition:null}`로 복구 가능 | **수용** — 잠금 없음이 의도된 회복 경로 |

백엔드 테스트 갭 처리: PATCH 미존재 id 404, 단일 요청 `설치+disposition` 422, `intentional_unresolved` 필터, closed+생략→NULL, 빈 문자열 필터 422 — **전부 추가**.

## 프론트엔드 지적 처리

| # | 지적 | 처리 |
|---|------|------|
| F1 (HIGH) | 사양 §6의 status 필터 회귀 테스트 누락 | **수정** — 필터 버튼 회귀 테스트 추가 |
| F2 | `intentional_unresolved` 배지 미검증 | **수정** — 배지 테스트에 seed 추가 |
| F3 | fixture PATCH가 status/disposition만 병합·사전 검증 없음 | **수정** — Literal/VALID_* 동일 검증 + 제공 필드 전부 병합(exclude_unset 동일) |
| F4 | disposition PATCH 중 모든 행 select 비활성(mutation-level pending) | **수용** — fail-safe, 무효화로 자기 회복 |
| F5 | 렌더 시점 `f.disposition` 읽기 — disposition 설정 직후 설치 전환 시 422 창 | **수용** — 좁은 경합 창, 서버가 정확히 거절·toast 표시 |
| F6 | `span.rounded-full` locator가 키워드 배지와 충돌 가능 | **수정** — 제목 행 `div:has(> h2)` 범위로 한정 |
| F7 | 빈 옵션 라벨 "처분 미분류…" vs 사양 "미분류" | **수용** — 표기 차이, 기능 동일 |
| F8 | `dispositionLabel()` 중복 호출 | **수용** — cosmetic |
| F9 | (범위 밖) `create_foreshadow`가 `audience_knows`를 저장하지 않는 선존 결함 | **수용·기록** — G-045 시대 선존 문제, D03-5 범위 밖. 원장에 후속 참고로 기록 |

## 검토 후 재검증

- backend focused: 36 passed (test_foreshadow_disposition.py + test_migrations.py + test_foreshadows_canon.py)
- backend full: 584 passed, 1 skipped, 0 isolation violations
- foreshadow-disposition fixture: 7 passed, tripwire no escapes
- 회귀 fixture: chapter-goal 8 / chapter-flow 10 / preservation 26 / ai-context 15 / memory 31 / serial-state 6 / evidence-links 8 — 전부 통과
- tsc --noEmit: exit 0
