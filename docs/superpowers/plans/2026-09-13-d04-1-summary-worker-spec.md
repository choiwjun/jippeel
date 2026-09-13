# D04-1 좁은 사양 — summary_jobs 영속 + fake worker 생명주기

- 작성일: 2026-09-13
- 슬라이스: D04(자동 요약·backfill)의 첫 얇은 단위 — **job/idempotency 저장 + fake worker**
- 선행 승인: [자동 요약·backfill 설계 §4–§7, §9](2026-09-11-long-memory-auto-summary-backfill.md), 원장 D04 행 "먼저 승인된 fake-worker 구현·검증"
- 선행 구현: `app/services/summary_jobs.py`(provider-free manifest planner), `MemoryEntry` provenance 계약

## 1. 목표·비목표

### 목표
- `summary_jobs` 테이블 — manifest를 DB에 영속하고 `idempotency_key` unique 제약으로 중복 계획을 차단한다.
- 서비스 계층 worker `run_pending_summary_jobs(db, provider)` — provider는 주입된 callable. 테스트는 fake provider만 사용한다.
- 상태 기계(설계 §4): `planned → running → draft_saved | skipped_empty | stale_source | provider_error | rejected`, 계획 단계 중복은 기존 job 재사용.
- 성공 시 `MemoryEntry`(kind=summary, visibility=draft)를 provenance와 함께 append — 기존 row 덮어쓰기·자동 승인 없음.
- 중단 복구: worker 시작 시 `running` 잔여를 `planned`로 되돌린다.
- 실패 재시도: `provider_error`만 명시적 retry로 `planned` 복귀. `stale_source`는 자동 retry하지 않는다(최신 revision으로 새 계획).

### 비목표 (승인 게이트)
- HTTP 엔드포인트, 프론트 UI, 자동 스케줄링 — 없음
- 실제 provider 호출, 비용, 운영 DB — 없음 (G01/G02/G03 필요)
- 기존 memory 자동 승격·폐기 — 없음

## 2. 스키마 — `summary_jobs` (migration `9d0e1f2a3747`, 신규 head)

| 열 | 타입 | 제약 |
|---|---|---|
| id | INTEGER | PK |
| project_id | INTEGER | FK projects.id ON DELETE CASCADE, NOT NULL, index |
| chapter_id | INTEGER | FK chapters.id ON DELETE SET NULL, NULL 허용, index |
| memory_entry_id | INTEGER | FK memory_entries.id ON DELETE SET NULL, NULL |
| source_revision | INTEGER | NOT NULL |
| source_sha256 | VARCHAR(64) | NOT NULL |
| source_sort_order | FLOAT | NOT NULL |
| source_content_length | INTEGER | NOT NULL |
| kind | VARCHAR(32) | NOT NULL, CHECK kind='summary' |
| prompt_version | VARCHAR(120) | NOT NULL |
| provider_identity | VARCHAR(120) | NOT NULL |
| model_snapshot | VARCHAR(120) | NOT NULL |
| request_options_hash | VARCHAR(64) | NOT NULL |
| request_options_json | JSON | NULL (planner가 비밀 키를 이미 거부) |
| idempotency_key | VARCHAR(64) | NOT NULL, **UNIQUE**, index |
| status | VARCHAR(20) | NOT NULL default 'planned', CHECK 8종 |
| error | TEXT | NULL |
| attempt_count | INTEGER | NOT NULL default 0 |
| finished_at | DATETIME | NULL |
| created_at / updated_at | TimestampMixin | |

- status CHECK: `('planned','running','draft_saved','skipped_empty','stale_source','provider_error','rejected','duplicate_skipped')`
- chapter 삭제 시 job은 SET NULL로 보존(감사). project 삭제는 기존 관례대로 CASCADE.
- `memory_entry_id`는 draft 저장 성공 시에만 설정.

## 3. 서비스 계약 — `app/services/summary_worker.py`

```python
def plan_summary_jobs(db, *, project_id, chapter_ids, prompt_version,
                      provider_identity, model_snapshot, request_options
) -> tuple[list[SummaryJob], list[SummaryJob]]  # (created, duplicates)
```
- 내부적으로 `build_summary_manifest()`로 manifest 생성(기존 검증 재사용: 소유권·빈 버전·비밀 옵션 거부).
- 각 항목의 `idempotency_key`로 기존 job 조회 — 있으면 `duplicates`에 넣고 새 row를 만들지 않는다(기존 draft/상태 재사용).
- 없으면 `planned` 또는 `skipped_empty`(manifest status 그대로)로 생성.
- 동일 manifest 재계획은 새 후보를 만들지 않는다(설계 §4).

```python
def run_pending_summary_jobs(db, provider, *, project_id=None, limit=None
) -> list[SummaryJob]  # 이번 실행에서 처리한 jobs
```
1. **복구**: 해당 범위의 `running` job을 `planned`로 되돌린다(중단 복구, attempt_count 불변).
2. `planned` job을 id 순·limit까지 처리. 각 job은 **독립 트랜잭션**으로 마무리(commit)한다.
3. job당 절차:
   - `running` 전이, attempt_count += 1.
   - `chapter = db.get(Chapter, chapter_id)` — 없거나 project 불일치 → `rejected`.
   - 본문 공백 → `skipped_empty`.
   - `revision != source_revision` 또는 `sha != source_sha256` → `stale_source` (저장 안 함).
   - `provider(job)` 호출 — 예외 → `provider_error`, `error=str(exc)`, finished_at 기록.
   - **호출 후 재검증**: chapter를 다시 읽어 revision/hash가 바뀌었으면 결과를 버리고 `stale_source`(설계 §3 완료 시점 재비교).
   - 동일 `idempotency_key`를 provenance에 가진 기존 draft MemoryEntry가 있으면 draft를 새로 만들지 않고 `duplicate_skipped` + `memory_entry_id`를 기존 row로 연결.
   - 성공 시 `create_memory_entry(... kind='summary', visibility='draft', source_revision=job.source_revision, source_text=당시 본문, provenance={generated_by:'summary-worker', job_id, idempotency_key, prompt_version, provider_identity, model_snapshot, request_options_hash})` → `draft_saved`, `memory_entry_id` 연결, finished_at 기록.

```python
def retry_summary_job(db, job_id) -> SummaryJob
```
- `provider_error`만 `planned`로 복귀(error 지움). 다른 상태는 ValueError.

```python
def list_summary_jobs(db, *, project_id) -> list[SummaryJob]  # id 순
```

## 4. 불변조건
- worker는 draft만 만든다. `approved`/`retired` 전이는 기존 수동 API만.
- 한 job의 MemoryEntry 저장과 `draft_saved` 전이는 같은 트랜잭션 — 고아 draft 없음.
- `running` 복구는 재처리 가능한 것만 — provider 호출 전 중단은 안전하게 재계획된다.
- 계획·실행 모두 `MemoryEntry` 기존 row를 변경하지 않는다(append-only).
- `Chapter` 원문·revision을 worker가 변경하지 않는다.

## 5. 검증
- `backend/tests/test_summary_worker.py` — 합성 TEMP SQLite, fake provider callable:
  - 계획 생성·skipped_empty 계획·중복 재계획(duplicates 반환·row 증가 없음)·idempotency unique
  - 실행: draft 저장 + job 연결 + provenance 필드 + attempt_count/finished_at
  - 계획 후 원문 수정 → stale_source, draft 미생성
  - provider 호출 중 원문 변경(호출 후 재검증) → stale_source
  - chapter 삭제/소유권 → rejected
  - provider 예외 → provider_error + error 보존, retry → planned → 재실행 성공
  - running 잔여 → 다음 run에서 복구·처리
  - limit·project 범위, 기존 memory row 불변
- migration 테스트: head 갱신, populated upgrade 보존, downgrade 제거, unique 제약.
- `run_backend_pytest.py` 전체 회귀 + 격리 선언.
