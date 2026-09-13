# D03-6 독립 검토 기록 — 완결본 관리

날짜: 2026-09-13 / 검토자: fresh-context subagent 2명 (backend·frontend) — 읽기 전용, 구현자와 무관

## 결과 요약

| 검토 | 판정 | 지적 | 반영 |
|------|------|------|------|
| backend | PASS_WITH_NOTES | 12건 (HIGH 2·LOW 3·NOTE 7) | 5건 수정, 7건 수용 |
| frontend | PASS_WITH_NOTES | 7건 (LOW 4·NOTE 3) | 4건 수정, 3건 수용 |

차단(BLOCKER) 지적 없음.

## backend 지적과 처리

1. **HIGH — sort_order 조립 순서 미검증** (test gap): 기존 테스트가 두 회차 모두 기본 sort_order=0.0으로 생성해 `.order_by(sort_order)` 삭제 회귀를 잡지 못함.
   → **수정**: `test_create_final_edition_assembles_chapters`가 생성 순서와 반대 sort_order(2.0→1.0)로 시드.
2. **HIGH — checklist_json 동결 미단정** (test gap): 스냅샷의 핵심 불변조건이 테스트되지 않음.
   → **수정**: `test_final_edition_is_immutable_snapshot`을 확장 — 캡처 후 근거 링크 파손·복선 추가 → live 점검표 변화와 detail.checklist 불변을 대조 단정.
3. **LOW — 목록 타 프로젝트 격리 미검증** → **수정**: `test_list_final_editions_cross_project_isolation` 추가.
4. **LOW — label strip 전 max_length 검증** (spec은 strip 후 200자) → **수정**: `StringConstraints(strip_whitespace=True, max_length=200)` 적용.
5. **NOTE — 동일 sort_order 비결정성** → **수정**: 캡처 `order_by(sort_order, id)` tiebreak 추가(Scene 정렬 패턴과 동일).
6. NOTE — bodyless POST 422 / by_stage 허용 초과 / NOT NULL fallback / DELETE에 BEGIN IMMEDIATE 없음(단일 행 삭제라 안전) / 체크리스트 재조회(단일 writer 환경에서 무시 가능) / client_db 중복 fixture + 미사용 import → **수용** (미사용 `select` import만 제거, 나머지는 코드베이스 관례·안전 방향과 일치).

## frontend 지적과 처리

1. **LOW — spec §5 이중 무효화 미구현** → **수정**: 생성·삭제 `onSuccess`에 `['completion-checklist', pid]` 무효화 추가.
2. **LOW — serial 배지 테스트 준자명** (점검표 배지가 `.first()`를 선점) → **수정**: `li` 범위로 한정해 완결본 행 배지를 단정.
3. **NOTE — `aria-expanded` 부재** → **수정**: 토글 버튼에 부여.
4. **NOTE — 삭제 후 stale expandedId** → **수정**: `deleteMutation.onSuccess`에서 `setExpandedId(null)`.
5. **NOTE — fixture POST가 extra=forbid 미검증** → **수정**: 알 수 없는 키·비문자열 label에 422 응답.
6. LOW — 쿼리 오류 경로 무음(실패 문구 없음) → **수용**: 코드베이스 관례와 일치, mutation은 toast 처리됨.
7. LOW — 매니페스트 `<ul>` (spec의 "표" 해석) → **수용**: spec이 컬럼을 열거하지 않음, 정보는 충실.

## 잔여 수용 사항

- 쿼리 실패 시 무음 UI(관례), 매니페스트 ul 렌더링, DELETE의 writer lock 부재(단일 행 삭제로 안전), bodyless POST 422 — 모두 코드베이스 관례·안전 방향이며 spec 범위 내.

## 최종 검증(수정 반영 후)

- backend focused 31 passed / 전체 605 passed·1 skipped·violations 0
- frontend fixture 6 passed·tripwire 0 / TSC_EXIT=0
- 회귀: chapter-goal 8·chapter-flow 10·preservation 26·ai-context 15·memory 31·serial-state 6·evidence-links 8·foreshadow-disposition 7
