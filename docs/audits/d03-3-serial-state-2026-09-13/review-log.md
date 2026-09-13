# D03-3 독립 검토 기록 — serial_state 분리

날짜: 2026-09-13
검토 방식: fresh-context subagent 2건 (backend / frontend), read-only

## 검토자 1 — 백엔드

**판정: PASS_WITH_NOTES** (차단 결함 없음)

확인: 시각 설정/제거 의미론 정확, 수명주기 독립 구조적 보장(flow transition은 Chapter·이벤트만, serial PATCH는 project만), migration이 검증된 pragma 패턴과 동일, Literal → 422 계약.

| # | 심각도 | 지적 | 처리 |
|---|--------|------|------|
| 1 | LOW | schema guard가 `serial_completed_at`·check constraint를 미검사(사양 "컬럼 2개 + constraint") | 수정 — `database.py`에 컬럼·constraint 검사 추가 |
| 2 | LOW | 명시적 `{"serial_state": null}` → NOT NULL IntegrityError → 500 (사양: invalid → 422) | 수정 — `ProjectUpdate` before-validator가 명시적 null을 422로 거절 |
| 3 | LOW | 부분 PATCH가 `serial_completed_at`을 보존하는 불변 테스트 없음 | 수정 — `test_partial_patch_preserves_completed_at` 추가 |
| 4 | LOW | completed 재진입 시각 갱신 assertion이 약함(`is not None`만) | 수정 — 이전 시각과 `!=` 비교로 강화 |
| 5 | INFO | 사양 `TEXT NULL` vs 구현 `DateTime` — 구현이 올바름 | 사양 문서 정정 (TEXT → DATETIME) |
| 6 | TRIVIAL | migration이 batch 2번 → 테이블 2회 재작성 | 수정 — 단일 batch로 병합 |
| 7 | TRIVIAL | downgrade 시 projects 행 보존 미단정 | 수정 — downgrade 테스트에 행 보존 + 컬럼 제거 assertion 추가 |

## 검토자 2 — 프론트엔드

**판정: PASS_WITH_NOTES** (차단 결함 없음)

확인: PATCH 본문이 정확히 `{serial_state}`, 완결 시각 게이팅, 레거시 폴백(`?? 'ongoing'`), 카드별 pending disable, tripwire 이중 구조, 접근성 유효.

| # | 심각도 | 지적 | 처리 |
|---|--------|------|------|
| 1 | LOW | 사양 §4 배지 요구(휴재/완결 배지, 연재중 생략) 미구현 | 수정 — 휴재/완결 `Badge` 추가 |
| 2 | LOW | controlled-select snap-back으로 `fx.patches` 단정이 레이스 가능 | 수정 — `expect.poll(() => fx.patches)` 후 본문 단정으로 순서 고정 |
| 3 | LOW | `serial_state` 없는 레거시 응답 폴백 미테스트 | 수정 — 레거시 프로젝트 테스트 추가 |
| 4 | LOW | PATCH 실패 시 사용자 피드백 없음 | 수정 — `onError` toast 추가 |
| 5 | LOW | catch-all 404는 미관측 요청을 못 잡음 | 수정 — `unhandled[]` 트래킹 + `afterEach` 공백 단정 |
| 6 | LOW | fixture 422 detail이 문자열(실계약은 리스트) | 수정 — Pydantic 오류 리스트 형태로 fidelity 수정 |
| 7 | INFO | select 옆 상시 "연재 상태" 마이크로라벨 권고 | 반영 — 가시 라벨 추가 |
| 8 | NEGLIGIBLE | 카드 간 mutation 공유로 첫 카드 select가 재활성화될 수 있음 | 미수정 — 단일 사용자 로컬 도구, thin UI 범위상 수용 |

## 검토 후 재검증

- backend 집중: **17 passed** (test_serial_state.py + test_migrations.py), 격리 위반 0
- backend 전체: **565 passed, 1 skipped**, 격리 위반 0
- serial-state fixture: **6 passed**, tripwire 위반 없음
- 회귀: chapter-flow 10, chapter-goal 8, preservation 26, ai-context 15, memory 31 — 전부 통과
- `tsc --noEmit`: **TSC_EXIT=0**
