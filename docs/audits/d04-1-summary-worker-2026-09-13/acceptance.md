# D04-1 수용 문서 — summary_jobs 영속 + fake worker 생명주기

- 슬라이스: **D04-1** (D04 자동 요약·backfill의 첫 얇은 단위)
- 사양: `docs/superpowers/plans/2026-09-13-d04-1-summary-worker-spec.md`
- 상위 설계: `docs/superpowers/plans/2026-09-11-long-memory-auto-summary-backfill.md` §3–§7, §9
- 상태: **수용 완료** (2026-09-13)
- 커밋 여부: **uncommitted** (`manifest.json`의 `committed: false`)

## 범위 결정

- job/idempotency 저장 방식: **설계 §5 선택지 1** — 별도 `summary_jobs` manifest 테이블 + `idempotency_key` UNIQUE 제약.
- **서비스 계층만 구현** — HTTP 엔드포인트·프론트 UI·자동 스케줄링 없음. 실제 provider 호출·비용·운영 DB는 승인 게이트(G01/G02/G03) 대상이며 이 슬라이스에 경로가 존재하지 않는다(독립 검토로 확인).

## 계약 요약

- `summary_jobs` (migration `9d0e1f2a3747`, head): manifest 11필드 + `request_options_json` + `idempotency_key` UNIQUE + status CHECK 8종 + `attempt_count`·`finished_at`·`error`.
- 상태 기계: `planned → running → draft_saved | skipped_empty | stale_source | provider_error | rejected | duplicate_skipped`; 복구 `running → planned`; 재시도 `provider_error → planned`(명시적만).
- `plan_summary_jobs` — manifest 계획을 영속, 동일 `idempotency_key`는 기존 job 재사용(duplicates 반환, 새 행 없음).
- `run_pending_summary_jobs` — running 잔여 복구(attempt_count 보존) → planned을 id 순·limit·project 범위로 처리. job마다 독립 트랜잭션. provider 호출 **전후**로 source revision+sha 재검증(호출 중 변경 → stale_source, 삭제 → rejected). 동일 provenance draft 존재 시 duplicate_skipped.
- 결과는 `MemoryEntry(kind='summary', visibility='draft')`로 append만 — 자동 승인·기존 row 변경·kind 승격 없음. provenance에 generated_by·job_id·idempotency_key·prompt_version·provider_identity·model_snapshot·request_options_hash 보존.
- chapter 삭제 → job은 `chapter_id` SET NULL로 감사 보존; project 삭제 → CASCADE(기존 관례).
- `retry_summary_job` — provider_error만 planned 복귀, 나머지는 ValueError. stale_source는 자동 재시도 없음(최신 revision으로 새 계획).

## 검증 결과 (검토 후 최종)

| 항목 | 결과 |
|------|------|
| backend focused (summary_worker + migrations + summary_jobs) | **41 passed** |
| backend 전체 회귀 | **641 passed, 1 skipped**, 위반 0 |
| frontend | 해당 없음 — 서비스 계층 슬라이스(표면 없음) |
| 독립 검토 | backend·contract/design 모두 **PASS_WITH_NOTES**, MED 5건·LOW 다수 반영·재검증 통과 |

migration 검증: head 정합, populated upgrade 보존, CHECK/UNIQUE 강제, chapter 삭제 시 SET NULL 보존, populated downgrade 제거+프로젝트 보존.

## 격리

- backend: 합성 TEMP SQLite만. provider는 테스트 주입 fake callable만 — 실제 provider·네트워크·credential 경로 없음.
- 운영 DB migration 적용·실제 provider·비용 실행은 별도 승인 경계 유지.

## 범위 밖 / 후속

- D04 후속: 실제 provider 어댑터(provider는 job의 manifest만 수신 — 원문 재독 계약 명시 필요), 비용·token hard cap, 평가 manifest, 작가 승인 UI 문구, 운영 실행 절차(dry-run·backup·batch 기록·pause) — §9 체크리스트·G01/G02/G03 승인 필요.
- 다중 worker claim/lease, 계획 select-then-insert 경합 — 자동 호출 배선 전 선행 조건.
- 선존 결함 G-045(`create_foreshadow`의 `audience_knows` 미영속) — 원장에 기록 유지.
