# D03-1 수용 기록 — 회차 집필 흐름(flow_stage) 상태 기계

- 날짜: 2026-09-13
- worktree: `/home/hunter8891/orca/workspaces/jippeel/d01-contract-analysis`
- branch: `choiwjun/d01-contract-analysis` (변경은 **미커밋** — stage/commit/push 미수행)
- 사양: `docs/superpowers/plans/2026-09-13-d03-1-flow-stage-spec.md`

## 범위

`Chapter.status`(초고/수정중/완료 — 원고 성숙도, plus-status가 의존)와 독립된 집필 흐름 단계
`flow_stage`(planning → writing → revising → confirmed, revising→writing, confirmed→revising)와
append-only 전이 이벤트(`chapter_flow_events`)를 추가했다. `confirmed`는 **집필 확정**이며
연재/발행 완결이 아니다.

- API: `GET /chapters/{cid}/flow`, `POST /chapters/{cid}/flow/transition`, `GET /chapters/{cid}/flow/events`
- CAS: `expected_flow_stage` 불일치 → 409 + 현재 단계. 불법 전이 → 422. SQLITE_BUSY → 409.
- 이벤트 앵커: 전이 커밋 시점의 `goal_version`(nullable) + 원고 `revision`을 writer lock 하에서 기록.
- 전이는 content/revision/snapshot/memo/goal/status를 건드리지 않는다(`updated_at` 갱신은 허용 범위).
- migration `3d4e5f6a7b81`: 컬럼 추가 + backfill(완료→confirmed, 수정중→revising, 빈 초고→planning,
  나머지→writing) + check constraint + 이벤트 테이블 + 인덱스. downgrade는 전부 제거.
- 프론트: 에디터 헤더에 단계 배지(role=status) + 허용 전이 select + 마지막 이벤트 앵커 표시.
  409 시 경고 toast + refetch. status select·SaveIndicator·D01 목표 UI 비침해.

## 검증 증거 (모두 합성 TEMP DB · fake provider · fixture 전용 포트)

| 항목 | 결과 |
|------|------|
| backend 집중 (flow+goal+migration) | `69 passed`, pytest_exit=0, violations=[] |
| backend 전체 회귀 | `543 passed, 1 skipped`, violations=[] |
| frontend tsc | `TSC_EXIT=0` |
| chapter-flow fixture (port 15231) | `6 passed`, tripwire escape 없음 |
| chapter-goal 회귀 (15230) | `8 passed`, tripwire 없음 |
| ai-context 회귀 | `15 passed`, tripwire 없음 |
| memory 회귀 | `31 passed`, tripwire 없음 |

로그 파일: 본 디렉터리 `backend-focused.txt`, `backend-regression.txt`, `frontend-tsc.txt`,
`frontend-chapter-flow.txt`, `frontend-*-regression.txt`. RED 기록: `red-log.md`.
소스 해시: `source-hashes.txt` (검토 후 수정분 반영 최종본).

## 독립 검토

2건 (backend: PASS_WITH_NOTES / frontend: FAIL→수정·재검증). 상세는 `review-log.md`.
프론트 검토의 유일한 차단 지적(axe aria-prohibited-attr)은 실제 axe 실행에서 위반 0으로 반증됐고,
근본 지적(일반 span의 aria-label이 AT에서 무시됨)은 `role="status"` 부여로 해소했다.
백엔드 검토의 spec 위반(`delete-orphan`)·stale anchor window·server_default drift는 전부 수정.

## 알려진 한계 / 후속 항목

- migration의 `PRAGMA foreign_keys=ON`(finally)는 트랜잭션 내에서 no-op — `b3c4d5e6f7a8`와
  동일한 선존 quirk. env.py가 engine을 dispose하므로 실해 해 없음.
- backfill의 `TRIM()`는 ASCII 공백만 처리 — 개행만 있는 초고는 `writing`으로 매핑됨(드문 케이스).
- 프론트 `FLOW_TRANSITIONS`는 백엔드 `ALLOWED_FLOW_TRANSITIONS`의 수동 미러 — 백엔드 422가
  최종 방어선. 기계적 동기화는 후속 과제.
- 선존 이슈(본 변경 무관): `patchMeta` PATCH 후 `['chapter', id]` 캐시 미갱신으로 status select가
  remount 전까지 이전 값 표시 가능 — 별도 후속으로 기록.
- `package-lock.json`은 D01 작업 이전부터 dirty/stale 상태 — 본 슬라이스 범위 밖.

## 경계 — 수행하지 않은 것

- 운영 DB 접근·migration, 실제 provider/model 호출, credential/OAuth 접근, 배포, 지정 실기기 검증,
  commit/stage/push — 전부 미수행. fixture 검증을 운영 수용으로 주장하지 않는다.
- D03 후속 단위(장면 재개 상세, 완결/연재 분리, 이관 등)는 본 수용 범위 밖.
