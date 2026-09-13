# D04-1 독립 검토 기록 — 2026-09-13

검토자: fresh-context subagent 2명 (backend 구현 / contract·design fidelity, 구현 코드 접근·판정 독립)

## 판정

- backend 검토: **PASS_WITH_NOTES** — 차단 결함 없음
- contract·design 검토: **PASS_WITH_NOTES** — 설계 §3–§6 전 항목 구현 또는 승인 게이트 뒤 정당한 유보 확인. 실제 provider·운영 DB·자동 승인 경로 없음 확인.

## 수용·수정한 지적

| # | 지적 | 심각도 | 처리 |
|---|------|--------|------|
| 1 | 사전 검사가 identity-map의 stale chapter를 읽을 수 있음(expire_on_commit=False) — 계획→실행 사이 다른 세션 변경을 놓침 | MED | `db.get(..., populate_existing=True)`로 갱신 |
| 2 | provider 호출 중 chapter 삭제 시 `db.refresh` 예외가 배치 전체를 중단 | MED | `ObjectDeletedError`+`InvalidRequestError` 포획 → `rejected` 종결 + 회귀 테스트 |
| 3 | `create_memory_entry` 주변 광범위 `except Exception`이 저장 계층 오류를 provider_error로 오분류·커밋 오염 | MED | `ValueError`만 provider_error + `db.rollback()` 선행, 나머지는 배치 안전망(rollback → 이 job만 provider_error 종결)으로 |
| 4 | `project_id` 범위 필터 테스트 부재(복구·계획 쿼리 양쪽) | MED | 2프로젝트 시나리오 — 처리 범위 + running 복구 범위 검증 추가 |
| 5 | migration `created_at`/`updated_at` nullable=True — 모델(NOT NULL)·기존 migration과 drift | MED | nullable=False로 정정(migration 미게시 상태) |
| 6 | 테스트 갭 다수 | LOW | 추가: 빈 결과 본문→provider_error, 호출 중 삭제→rejected, 실패가 후속 job 비차단, 다른 options→별도 job·별도 draft, 실행 시점 빈 본문→skipped_empty, stale_source retry 거부, 복구 시 attempt_count 보존, CHECK/UNIQUE/FK SET NULL 강제 검증 |
| 7 | 테스트 내 미사용 import | LOW | 제거 |

## 수용(NOTE, 변경 없음)

- `_find_duplicate_draft`가 visibility 무관 매칭 — retired/approved 재생성 억제가 의도적으로 더 안전. 두 검토자 모두 LOW 판정.
- `idempotency_key` UNIQUE + 별도 non-unique index 중복 — 사양이 둘을 명시.
- select-then-insert 계획 경합·worker claim/lease 부재·복구의 unconditional running 회수 — 단일 fake-worker 범위에서는 허용. 자동 호출 배선 시 선행 조건으로 기록.
- `provider(job)`는 manifest 메타데이터만 수신 — 실제 provider 어댑터는 원문 재독 필요(G02 배선 설계 시 명시).
- `request_options_json` 평문 영속 — planner 비밀 키 패턴에 의존, 비매칭 키 credential은 호출자 책임. 모델 docstring에 경고 명시.

## 검토 후 재검증

- backend focused (summary_worker + migrations + summary_jobs): **41 passed**
- backend full: **641 passed, 1 skipped**, isolation violations 0
