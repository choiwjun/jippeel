# D03-1 좁은 상세 사양 — 회차 집필 흐름(flow_stage) 상태 기계 + 전이 근거 앵커

날짜: 2026-09-13 · 상태: 구현 승인(사용자 위임: 추천안 자율 결정) · 선행: D01 수용 완료

## 1. 범위 결정

원장 D03 전체(기획→집필→퇴고→완결·재개: 목표↔원문 근거 연결, 미해결 감수·다음 장면 재개,
해결/의도적 미해결/외전 이관, 집필 확정과 연재 분리·완결본 관리)를 얇은 단위로 나눈다.
**D03-1은 흐름 상태 기계와 전이 근거 앵커만** 다룬다 — 후속 단위의 기반이 되는 최소 계약.

| 단위 | 범위 | 상태 |
|---|---|---|
| **D03-1 (이 문서)** | `flow_stage` 상태 기계 + 전이 이벤트(append-only) + `goal_version`·원고 `revision` 앵커 + 재개 정보 표시 | 이 문서 |
| D03-2 후속 | 해결/의도적 미해결/외전 이관 표시, 미해결 감수·다음 장면 재개 상세 | 미착수 |
| D03-3 후속 | 집필 확정(confirmed)과 연재 완결의 분리, 완결본 관리, 결말 변경 영향 | 미착수 |

## 2. 기존 `status`와의 분리 (보존 계약)

- `Chapter.status`(`초고|수정중|완료`)는 **원고 성숙도 표시**다. 자유 전환 select,
  plus-status 집계(`status == '완료'`), StatusBadge가 의존 — **전이 규칙·의미 변경 없음**.
- `flow_stage`는 **D03 작업 흐름 단계**로 별도 축이다. 작가가 status를 바꿔도 flow_stage는
  변하지 않고, flow 전이도 status를 바꾸지 않는다.
- `confirmed`(집필 확정)는 **연재/발행 완결이 아니다** — 발행 상태는 이 단위에 없다.
- flow 전이는 `Chapter.revision` 증가·`ChapterSnapshot` 생성·`memo`·목표(goal) 쓰기를 하지 않는다.

## 3. 스키마

### `chapters.flow_stage` — `String(20) NOT NULL`
`CHECK IN ('planning','writing','revising','confirmed')`.

- 새 회차 기본값: `'planning'`(생성 시 본문 없음).
- migration backfill(기존 행의 근사 매핑, status는 그대로 유지):
  `완료→confirmed`, `수정중→revising`, `초고→(content_md 비어 있으면 planning, 아니면 writing)`.

### `chapter_flow_events` — append-only 전이 로그

| 컬럼 | 타입 | 제약 |
|---|---|---|
| id | Integer | PK |
| chapter_id | Integer | FK `chapters.id` ON DELETE CASCADE, index, NOT NULL |
| from_stage | String(20) | NOT NULL, 같은 CHECK |
| to_stage | String(20) | NOT NULL, 같은 CHECK |
| goal_version | Integer | NULL — 전이 시점의 저장본 목표 버전(D01 접점). 저장본 없으면 NULL |
| manuscript_revision | Integer | NOT NULL — 전이 시점 `Chapter.revision` |
| created_at | DateTime | server_default, index |

- 갱신·개별 삭제 없음. 회차 삭제 시 cascade(회차 생애와 동일).
- ORM: `Chapter.flow_events` relationship (delete-orphan 아님 — FK cascade만).

## 4. 전이 규칙

허용 전이(이 외 전부 불법 → 422):

| from | to | 의미 |
|---|---|---|
| planning | writing | 집필 시작 |
| writing | revising | 퇴고 시작 |
| revising | writing | 추가 집필로 되돌림 |
| revising | confirmed | 집필 확정 |
| confirmed | revising | 확정 후 수정 재개 |

- 동일 단계로의 전이도 불법(422) — no-op이 아니라 오류.
- `confirmed`는 terminal이 아니다 — `revising`으로 재개 가능(재개 흐름).

## 5. API

| 경로 | 요청 | 응답 | 오류 |
|---|---|---|---|
| `GET /chapters/{cid}/flow` | — | `200 ChapterFlowOut` | 404 chapter |
| `POST /chapters/{cid}/flow/transition` | `ChapterFlowTransition{to_stage, expected_flow_stage}` | `200 ChapterFlowOut` (전이 후 상태) | 404 / 409 stale·BUSY / 422 불법 전이·payload |
| `GET /chapters/{cid}/flow/events` | — | `200 list[ChapterFlowEventOut]` id 내림차순(최신 먼저) | 404 chapter |

```
ChapterFlowEventOut { id, chapter_id, from_stage, to_stage, goal_version|null,
                      manuscript_revision, created_at }
ChapterFlowOut { chapter_id, project_id, flow_stage,
                 last_event: ChapterFlowEventOut|null,
                 current_goal_version: int|null,      // 현재 저장본 목표 버전
                 current_chapter_revision: int }      // 현재 Chapter.revision
ChapterFlowTransition { to_stage: FlowStage, expected_flow_stage: FlowStage }
```

- `expected_flow_stage` 필수 — 현재 단계와 다르면 409 `{code:"flow_stage_conflict", current_flow_stage}`.
- 불법 전이는 CAS보다 먼저 검사하지 않는다 — CAS 먼저(기대 단계가 틀리면 전이 판단 자체가 무의미).
  순서: 404 chapter → expected 불일치 409 → 불법 전이 422.
- 전이는 `chapter_flow_events` INSERT + `chapters.flow_stage` UPDATE를 한 트랜잭션으로.
  SQLITE_BUSY → 409(기존 패턴).
- `goal_version` 앵커는 전이 시점의 `chapter_goals.goal_version`(없으면 NULL).
  목표 내용을 복사하지 않는다 — 버전 참조만(D01 이력에서 조회 가능).

## 6. 프론트 (얇은 UI)

- api.ts: `FlowStage`, `ChapterFlowEvent`, `ChapterFlowOut` 타입.
- EditorPage 헤더(StatusBadge 옆): 현재 flow_stage 배지 + 허용된 다음 단계만 담은 select
  (`aria-label="집필 흐름 단계"`). 선택 즉시 transition POST.
- 마지막 전이 앵커 표시: `last_event`가 있으면 `목표 v{goal_version}·원고 r{manuscript_revision} 기준`,
  goal_version이 null이면 `원고 rM 기준`만. 현재 revision과 다르면 stale 표시는 하지 않는다
  (앵커는 기록이지 경고가 아님).
- query key `['chapter-flow', chapterId]` — `['chapter', id]`·`['chapter-goal', id]`와 분리.
  전이 성공 시 `setQueryData`; 409 시 toast + invalidate(입력 상태 없음 — 단순 select라 덮을 게 없다).
- 422 불법 전이 → toast로 사유 표시. 프론트는 허용 전이만 보여주므로 422는 이론상 경합/버그 경로.
- 목표 없는 회차도 flow 전이 가능(goal_version NULL 앵커).

## 7. 테스트 계획

Backend (`tests/test_chapter_flow.py`, 합성 TEMP DB):
1. 새 회차 `flow_stage='planning'`; GET flow 기본값(last_event null, current_* 필드).
2. 허용 전이 전부(planning→writing→revising→confirmed→revising→writing) + 이벤트 누적 순서.
3. 불법 전이 422: planning→revising, planning→confirmed, writing→confirmed, same→same, confirmed→writing.
4. `expected_flow_stage` 불일치 → 409 + current 반환. 생략 → 422.
5. 전이 시 goal_version 앵커: 목표 저장 후 전이 → event.goal_version 기록; 목표 삭제 후 전이 → NULL.
6. 전이가 `revision`·snapshot·memo·goal·status를 바꾸지 않음.
7. 회차 삭제 시 이벤트 cascade; 없는 회차 404.
8. 이력 최신 먼저 정렬.
9. migration: upgrade/downgrade, 기존 행 backfill 매핑, 재upgrade 멱등.

Frontend fixture (`e2e/chapter-flow.spec.ts`, 전용 포트 15231):
1. flow 배지 + 허용 전이만 select에 표시.
2. 전이 선택 → POST 본문(to_stage+expected) → 배지·앵커 갱신.
3. 409 → toast + refetch.
4. 목표 저장본 있는 회차의 앵커에 목표 vN 표시.
5. axe serious/critical 0.

## 8. 명시적 범위 밖

- status↔flow_stage 연동·자동 승격 — 없음.
- 전이 조건(예: revising 진입에 최소 글자 수·감수 요구) — 후속 단위에서 판단.
- 연재/발행 상태, 완결본 관리, 이관, 장면 단위 재개 — D03-2/3.
- 목표 달성 자동 판정 — 영구 금지.
