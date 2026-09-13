# D03-7 독립 검토 기록 — 2026-09-13

검토자: fresh-context subagent 2명 (backend / frontend, 구현 코드 접근·판정 독립)

## 판정

- backend 검토: **PASS_WITH_NOTES** — 차단 결함 없음, LOW/NOTE 다수
- frontend 검토: **PASS_WITH_NOTES** — 차단 결함 없음, LOW/NOTE 다수

## 수용·수정한 지적

| # | 지적 | 심각도 | 처리 |
|---|------|--------|------|
| 1 | `ending_locked: null` 명시 전달 시 스키마가 통과 → DB NOT NULL 위반으로 HTTP 500 | MED | `ProjectUpdate` pre-validator에서 명시적 null을 422로 거부 (`serial_state`와 동일 처리). 회귀 테스트 추가 |
| 2 | 기존 결말 지우기 테스트가 timestamp non-null만 단정 — 실제 변경 여부 미증명 | LOW | 지우기 후 `ending_updated_at`가 이전 값과 달라짐을 단정하도록 강화 |
| 3 | `ending_intent: ""` 저장 시 `""`가 그대로 영속 — 사양상 null 정규화 | LOW | `update_project`에서 `""` → `None` 정규화 + 회귀 테스트 |
| 4 | fixture PATCH 배열을 비동기 단정 — 레이스 가능 | LOW | `await expect.poll(() => fixture.patches).toHaveLength(1)` 후 정확 단정 |
| 5 | 프로젝트 전환 시 ending draft 잔존 — 다른 프로젝트 결말로 오염 가능 | MED | `useEffect(() => setDraft(null), [pid, project?.ending_intent])` |
| 6 | 프로젝트 로딩 중 textarea/저장 버튼 활성 — 미로딩 상태 저장 가능 | LOW | `project === undefined`를 disabled 조건에 추가 |
| 7 | 잠금 토글 성공 토스트가 "결말 저장됨"과 동일 — 오해 소지 | LOW | 잠금/해제 토스트 분리, ending_intent 저장 시에만 draft 리셋 |
| 8 | fixture unhandled-request 추적이 `afterEach`에서만 리셋 | LOW | `beforeEach`에서도 리셋하도록 이전 |
| 9 | 공백 결말 → `{ending_intent: null}` 경로 테스트 부재 | LOW | 빈/공백 입력 테스트 추가 |

## 수용(NOTE, 변경 없음)

- `EndingSection`의 `<Label>`이 `htmlFor`로 textarea와 미연결 — textarea에 `aria-label="결말 후보"`가 있어 차단 아님. 코드베이스 동일 패턴 다수.
- impact 파생 로직이 목표 `updated_at` vs `ending_updated_at` 단순 비교 — 사양상 "potentially stale" 파생 표시로 정확한 계약 충족.

## 검토 후 재검증

- backend focused (test_ending_impact + test_migrations + test_serial_state): **33 passed**
- backend full: **618 passed, 1 skipped**, isolation violations 0
- frontend ending-impact fixture: **6 passed**, tripwire no escapes
- tsc: `TSC_EXIT=0`
