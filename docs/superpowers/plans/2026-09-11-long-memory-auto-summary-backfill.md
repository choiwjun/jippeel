# 장편 기억 자동 요약·backfill 설계안

- 작성일: 2026-09-11
- 상태: **설계만 완료 / 구현·provider 호출·운영 DB 접근 금지**
- 선행 조건: `docs/superpowers/plans/2026-09-11-long-memory-followup.md` 구현·검증 완료

## 1. 목표와 비목표

### 목표

- 승인된 회차 원문에서 요약 후보를 생성한다.
- 후보는 항상 `draft`로 저장하고 작가가 승인해야 AI context에 들어간다.
- 기존 `MemoryEntry`의 provenance, source revision, SHA-256, stale 계약을 보존한다.
- 재실행해도 중복 후보를 만들지 않는 deterministic backfill 계획을 제공한다.
- dry-run, pause, resume, rollback 가능한 운영 절차를 정의한다.

### 비목표

- 자동 승인, 기존 memory 덮어쓰기, 원문 수정, 기존 memo의 자동 분류·승격
- 운영 DB migration이나 실제 provider 호출
- 새로운 memory kind 또는 새 외부 의존성 추가
- stale memory의 자동 폐기

## 2. 도메인 모델

현재 정본과 파생 데이터를 분리한다.

| 객체 | 소유권 | 불변식 |
| --- | --- | --- |
| `Chapter` | 원문 정본 | `content_md`와 `revision`이 함께 변경된다. |
| `MemoryEntry` | 파생 기억 | 기존 row를 덮어쓰지 않고 새 후보를 append한다. |
| `SummaryJob` 후보 개념 | 실행 추적 | 동일한 project/chapter/revision/hash/kind 조합은 한 번만 생성한다. |
| 승인 상태 | 작가 | 생성 결과는 `draft`; `approved` 전환은 수동 API만 허용한다. |

현재 schema에 job table은 없다. 구현 승인 전에는 별도 table, JSONL, queue를 추가하지 않는다. 초기 구현은 임시 DB에서 dry-run manifest를 생성하는 순수 서비스 경계부터 검토한다.

## 3. 입력 계약

각 후보 입력은 다음 frozen manifest를 가진다.

```text
project_id
chapter_id
source_revision
source_sha256
source_sort_order
source_content_length
kind = summary
prompt_version
model_id
request_options_hash
```

- source text는 입력 시점에 한 번 읽고 SHA-256을 계산한다.
- 생성 완료 시점에 chapter를 다시 읽어 revision/hash를 비교한다.
- 불일치하면 결과를 저장하지 않고 `stale_source`로 기록한다.
- empty chapter는 후보를 만들지 않고 `skipped_empty`로 기록한다.
- retired chapter/project 또는 소유권 불일치는 `rejected`로 기록한다.

## 4. 후보 생성 상태

```text
planned → running → draft_saved
                 ├→ skipped_empty
                 ├→ stale_source
                 ├→ provider_error
                 └→ rejected
```

- `draft_saved`는 승인 상태가 아니다.
- retry는 `provider_error`에만 허용한다.
- `stale_source`는 자동 retry하지 않는다. 최신 revision으로 새 작업을 계획한다.
- 같은 manifest 재실행은 기존 draft를 재사용하거나 `duplicate_skipped`로 끝낸다.
- 기존 `approved`·`retired` row는 backfill이 수정하거나 삭제하지 않는다.

## 5. Idempotency와 중복 방지

초기 설계에서 중복키는 다음 논리 조합이다.

```text
(project_id, chapter_id, source_revision, source_sha256,
 kind, prompt_version, request_options_hash)
```

현재 `MemoryEntry`에 이 키를 강제하는 migration은 계획하지 않는다. 구현 승인 후 다음 중 하나를 선택해야 한다.

1. 별도 `summary_jobs` manifest table에 unique constraint를 둔다.
2. 임시/단일 사용자 MVP에서는 backfill 시작 전에 기존 draft를 조회하고 deterministic comparison을 수행한다.

두 선택 모두 기존 memory body나 provenance를 덮어쓰지 않아야 한다.

## 6. 승인·표시 규칙

- 자동 생성 결과는 항상 `draft`다.
- UI에는 `generated_by`, `prompt_version`, model, source revision/hash를 표시한다.
- 작가는 기존 governance 화면에서 승인/폐기한다.
- stale 후보는 승인 버튼을 숨기지 않되, 승인 전 최신 source 확인을 명시한다.
- 승인된 memory가 stale이면 자동 주입하지 않는다.
- 자동 요약 결과가 canon/fact/decision을 주장해도 `summary` 외 kind로 자동 승격하지 않는다.

## 7. Backfill 실행 절차

### Dry-run

1. 대상 project/chapter 목록을 명시적으로 고정한다.
2. 원문 row count, revision, hash, sort order manifest를 저장한다.
3. provider 호출 없이 예상 작업 수와 skip/reject 사유를 계산한다.
4. 예상 작업 수, 최대 token budget, 예상 비용을 승인받는다.

### 승인 실행

1. 전용 test DB에서 dry-run과 fake provider 실행
2. append-only, stale race, duplicate, pause/resume, failure retry 검증
3. 운영 snapshot과 restore evidence 확보
4. 명시 승인 후 작은 batch부터 실행
5. batch마다 생성 수, draft 수, 실패 수, stale 수, usage/cost를 기록
6. hard cap 또는 오류율 초과 시 즉시 pause

### 중단·복구

- 원문 저장은 backfill transaction과 분리한다.
- 중단 시 이미 저장된 draft는 보존하고 다음 실행에서 manifest로 재사용한다.
- partial batch를 성공 전체로 표시하지 않는다.
- rollback은 memory row 삭제가 아니라 해당 batch의 draft를 `retired`로 전환하는 승인된 정리 절차로만 수행한다.

## 8. 평가셋과 acceptance

최소 6개 승인 사례를 고정한다.

- 짧은 회차, 장문 회차, 빈 본문, 개정 후 stale, 미래 회차, 기존 approved memory가 있는 회차
- exact contract: source revision/hash, project ownership, draft visibility
- quality rubric: factual consistency, omission, unsupported inference, style, length
- 독립 평가자 2명과 USD 20 hard cap
- 실제 provider 평가 전 fake provider로 경계·pause·retry·duplicate를 통과한다.

## 9. 구현 전 승인 체크리스트

- [ ] provider/model/prompt version 확정
- [ ] 비용·token hard cap 확정
- [ ] 평가 manifest 승인
- [ ] job/idempotency 저장 방식 결정
- [ ] 기존 memory 중복 정책 결정
- [ ] stale race와 restore race 테스트 통과
- [ ] dry-run manifest·backup·restore 확인
- [ ] 작가 승인 UI의 문구와 상태 전환 확인
- [ ] 운영 DB와 실제 keyring 접근 승인

이 문서 작성 단계에서는 코드, schema, migration, provider, 운영 DB를 변경하지 않았다.
