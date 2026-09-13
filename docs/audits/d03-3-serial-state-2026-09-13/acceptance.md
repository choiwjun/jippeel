# D03-3 수용 문서 — 연재 상태(serial_state) 분리

날짜: 2026-09-13
브랜치: `choiwjun/d01-contract-analysis` (worktree `d01-contract-analysis`, **uncommitted**)
사양: `docs/superpowers/plans/2026-09-13-d03-3-serial-state-spec.md`
Alembic head: `4e5f6a7b8c92`

## 범위

프로젝트 수준 연재 수명주기 `ongoing | hiatus | completed`를 회차 `flow_stage`(집필 확정)·레거시 `Chapter.status`(원고 성숙도)와 분리해 추가했다.

- `projects.serial_state`(NOT NULL, default `ongoing`, `ck_project_serial_state`)
- `projects.serial_completed_at`(DateTime, completed 진입·재진입마다 갱신, 이탈 시 NULL)
- `PATCH /projects/{pid}`의 `serial_state` 필드 — 명시적 null·사전 외 값은 422
- 홈 카드에 연재 상태 select + 휴재/완결 배지 + 완결 시각, "회차 집필 확정과 별개" 명시
- migration `4e5f6a7b8c92`: backfill `ongoing`/NULL, downgrade는 컬럼·constraint 제거 + 데이터 보존

## 불변 확인

- 회차 `confirmed` 전이는 `serial_state`를 변경하지 않는다(테스트로 단정)
- `serial_state` 변경은 회차 `flow_stage`·`status`·본문을 건드리지 않는다
- `serial_state` 없는 부분 PATCH는 `serial_completed_at`을 보존한다
- `serial_completed_at`은 서버 관리 — 클라이언트가 위조 불가(ProjectUpdate 필드 아님)

## 검증 결과 (2026-09-13 최종)

| 실행 | 결과 |
|------|------|
| backend 집중 (serial+migrations) | 17 passed, 격리 위반 0 |
| backend 전체 | 565 passed, 1 skipped, 격리 위반 0 |
| frontend serial-state fixture | 6 passed, tripwire 위반 없음 |
| chapter-flow fixture 회귀 | 10 passed |
| chapter-goal fixture 회귀 | 8 passed |
| preservation fixture 회귀 | 26 passed, no escapes |
| ai-context fixture 회귀 | 15 passed |
| memory fixture 회귀 | 31 passed |
| tsc --noEmit | TSC_EXIT=0 |

기존 경고 1건 유지: `wordcount.py` `SyntaxWarning: \p` — 선존, 이 슬라이스와 무관.

## 독립 검토

2건(백엔드·프론트) 모두 **PASS_WITH_NOTES** — 차단 결함 없음.
지적 15건 중 14건 반영(guard 보강, null→422, 테스트 갭, 배지, toast, 트래킹, 문서 정정 등), 1건 수용(카드 간 mutation 공유 — thin UI 범위). 상세: `review-log.md`.

## 격리·경계

- 합성 TEMP SQLite만 사용 — 운영 DB 접근 없음
- 프론트는 fixture 라우트만(전용 포트 15232), tripwire 탈출 0
- 실제 provider·credential·배포·운영 migration·commit/push 미수행

## 잔여 D03 범위

- 목표 필드 ↔ 원고 근거 연결
- 결말 변경 영향
- 해결/의도적 미해결/외전 이관 구분
- 연재·완결 산출물 관리 (serial_state 데이터 위에 올라갈 후속 단위)
