# D03-2 독립 검토 기록

두 건의 fresh-context 독립 검토(백엔드 / 프론트엔드). 실행 근거는 본 디렉터리의 캡처 로그.

## 검토 1 — 백엔드 (verdict: PASS_WITH_NOTES)

엔드포인트는 순수 읽기(db.get + 4 SELECT), 드리프트 null 엣지 전부 정확
(anchor null→생성 true / anchor vN→삭제 true / 양쪽 null→false), 단일 세션 일관 스냅샷,
N+1 없음, D03-1·D01 비침해, 스키마 가드 불변 확인.

### 지적 및 조치

| # | 지적 | 조치 |
|---|------|------|
| 1 | null-anchor 드리프트 미검증(생성 후·삭제 후) | `test_resume_goal_created_after_null_anchor_is_drift`, `test_resume_goal_deleted_after_anchor_is_drift` 추가 |
| 2 | sort_order 미검증(id tiebreak만 작동했을 수 있음) | `test_resume_next_scene_follows_sort_order_not_id` 추가 |
| 3 | 공백-only `content_md` 미검증 | `test_resume_next_scene_whitespace_counts_as_empty` 추가(+키 집합 tripwire) |
| 4 | 양쪽 드리프트 동시 케이스 없음 | `test_resume_both_drifts_simultaneously` 추가 |
| 5 | 다중 전이 시 마지막 이벤트 앵커 미검증 | `test_resume_drift_compares_against_latest_event_only` 추가 |
| 6 | read-only 테스트의 목표/revision 보존 미확인 | goal `history_count` assertion으로 유지(쓰기 경로 부재) — 수용 문서 기록 |
| 7 | `bool(last)` → `last is not None`이 명확 | 기존 표현 유지(동치, BaseModel은 항상 truthy) — 수용 문서 기록 |
| 8 | 장면 전체 행 로드(content_md 포함) — O(장면 바이트) | 현재 규모에서 허용 — 수용 문서 기록 |

## 검토 2 — 프론트엔드 (verdict: PASS_WITH_NOTES)

타입·fixture 드리프트 계산·캐시 키·배지 a11y(visible text가 올바른 선택)·D03-1 비침해 확인.

### 지적 및 조치

| # | 지적 | 조치 |
|---|------|------|
| 1 | resume 캐시가 세션 내 stale — 목표 저장·자동저장·감수·장면 변경 시 미갱신 | `refreshMemoriesAfterRevision`에 chapterId 추가해 revision 인정 시 resume 무효화(2 call site), 목표 PUT/DELETE/restore·장면 mutation·윤문 실행/수락/폐기 성공 경로에 `chapter-resume` 무효화 추가 |
| 2 | 409 경로가 chapter-flow만 무효화 | `chapter-resume` 무효화 추가 (EditorPage.tsx:365) |
| 3 | **manuscript-preservation.spec.ts throwing catch-all 회귀** — `/flow`·`/resume`·`/goal` 미모킹으로 실패 | fixture에 flow/resume/goal/history mock 추가 — 26 passed로 복구(D01 잠재 회귀도 함께 해소) |
| 4 | fixture `next_scene`이 삽입 순서 사용 | `sort_order, id` 정렬 후 find로 수정 |
| 5 | 배지 표시 상태의 axe 미실행 | a11y 테스트를 배지 렌더 상태(드리프트+감수+장면)로 실행하도록 수정 |
| 6 | 공백-only 장면 제목 fallback 미처리 | `title.trim() || '무제'`로 수정 |
| 7 | `ResumeSummary`가 `flow` 성공 뒤에만 렌더 — flow 실패 시 resume도 숨김 | thin slice 범위 — 수용 문서 기록 |
| 8 | light-theme secondary 배지 대비 ~3.8:1(AA 경계) — 미측정 구성 | 기존 테마 토큰 사용 — 수용 문서 기록 |

## 최종 상태

- 재실행: backend focused `74 passed`(flow+goal+resume+migration은 별도 집계), 전체 `558 passed / 1 skipped / violations []`.
- frontend: chapter-flow `10 passed`(a11y는 배지 표시 상태), preservation `26 passed`,
  chapter-goal `8 passed`, ai-context `15 passed`, tripwire escape 0, tsc `TSC_EXIT=0`.
