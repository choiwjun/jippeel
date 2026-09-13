# D03-2 수용 기록 — 회차 재개 계약 (resume surface)

- 날짜: 2026-09-13
- worktree: `/home/hunter8891/orca/workspaces/jippeel/d01-contract-analysis`
- branch: `choiwjun/d01-contract-analysis` (변경은 **미커밋** — stage/commit/push 미수행)
- 사양: `docs/superpowers/plans/2026-09-13-d03-2-resume-spec.md`
- 선행: D01(목표 버전), D03-1(flow_stage + 전이 이벤트 앵커)

## 범위

`GET /chapters/{cid}/resume` — 재개 요약의 순수 파생 읽기. 새 테이블·migration·쓰기 경로 없음.

- `flow_stage` + `last_event`(D03-1) + 현재 `goal_version`/`revision`
- 드리프트: `goal_changed_since_transition`, `manuscript_changed_since_transition`
  — last_event 앵커와 현재값 비교. 이벤트 없으면 false. null↔값 변경은 드리프트.
- `pending_refine_runs`: `RefineRun.accepted=false` 수(거절/미적용 구분 불가는 기존 스키마 한계).
- `next_scene`: sort_order 순 첫 빈(공백 포함) 장면. `scene_count` 함께 반환.
- 프론트: 에디터 헤더에 "목표 변경됨"/"원고 변경됨"/"미해결 감수 N"/"다음 장면: 제목" 배지.
  전이 성공·409·목표 저장/삭제/복원·원고 revision 인정·장면 mutation·윤문 실행/수락/폐기 시
  `chapter-resume` 무효화.

## 검증 증거 (합성 TEMP DB · fake provider · fixture 전용)

| 항목 | 결과 |
|------|------|
| backend 집중 (resume+flow+goal) | `74 passed`, pytest_exit=0, violations=[] |
| backend 전체 회귀 | `558 passed, 1 skipped`, violations=[] |
| frontend tsc | `TSC_EXIT=0` |
| chapter-flow+resume fixture (15231) | `10 passed`, tripwire escape 없음 (a11y는 배지 표시 상태) |
| preservation 회귀 (15225) | `26 passed`, escape 없음 |
| chapter-goal 회귀 | `8 passed` |
| ai-context 회귀 | `15 passed` |

로그: 본 디렉터리 각 txt. RED: `red-log.txt`(구현 전 8 failed). 해시: `source-hashes.txt`.

## 독립 검토

2건 모두 **PASS_WITH_NOTES**, 차단 결함 없음. 상세 `review-log.md`.
주요 수정: 검토에서 발견된 선존 회귀(preservation fixture의 `/flow`·`/resume`·`/goal` 미모킹 —
D01/D03-1 시점 잠재 파손)를 fixture mock으로 복구, resume 캐시 staleness 해소(모든 관련
mutation에 무효화), null-anchor 드리프트·sort_order·공백 장면 테스트 추가.

## 알려진 한계 / 후속 항목

- `pending_refine_runs`는 `accepted=false`만 본다 — "거절"과 "미적용"의 구분은 RefineRun
  스키마 변경이 필요한 후속 범위.
- `ResumeSummary`는 flow 쿼리 성공 뒤에만 렌더된다(flow 실패 시 함께 숨김) — thin UI 선택.
- `next_scene`은 장면 행 전체를 읽어 Python에서 공백 판정 — 회차당 장면 수 규모에서 허용.
- light 테마 secondary 배지 대비는 미측정(기존 테마 토큰 그대로 사용).
- 목표 저장·원고 자동저장 외에도 `staleTime 30s` 내 다른 경로 변경은 다음 invalidate까지
  지연될 수 있다(기존 캐시 정책과 동일한 수준).

## 경계 — 수행하지 않은 것

- 운영 DB·실제 provider·credential·배포·실기기·commit/stage/push 미수행.
- 완결 분리·이관·근거 연결(목표 필드↔원문 링크)은 후속 D03 단위.
