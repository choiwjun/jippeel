# 장편 기억 설계

- 작성일: 2026-09-10
- 상태: **read-only 설계. 스키마·코드·운영 DB는 변경하지 않음.**

## 현재 경계

현재 정본은 `Project`, `Chapter.content_md`, `Chapter.revision`, `ChapterSnapshot`, `Scene`, `Character`, `Relationship`, `LoreEntry`, `Foreshadow`에 있다. `ai_context.ContextBundle`은 요청 시점에 DB에서 조립되는 불변 전달물이며 저장된 장편 기억이 아니다.

- 회차 원문과 revision은 `Chapter`가 소유한다.
- 이전 원문은 `ChapterSnapshot`이 교체 전 revision별로 보존한다.
- canon 후보와 복선 상태는 project/chapter 참조를 가진 정본 데이터다.
- style profile, volume note, chapter memo, outline은 서로 다른 의미를 가지며 하나의 `memory` 문자열로 합치지 않는다.
- provider에 전달된 context는 현재 요청의 `project_id`, `chapter_id`, `expected_revision`, 선택 ID와 옵션으로 재구성된다.

근거: `backend/app/models.py`, `backend/app/services/ai_context.py`, `backend/app/services/manuscripts.py`.

## 제안하는 저장 경계

### 1. 정본과 파생 기억을 분리한다

| 층 | 소유자 | 쓰기 규칙 |
|---|---|---|
| 원문 정본 | `chapters` + `chapter_snapshots` | revision 검증과 snapshot 생성이 같은 transaction에서 수행 |
| 명시적 canon | project-scoped canon/fact 레코드 | 작가 승인 또는 명시적 import만 상태 변경 |
| 회차 기억 | chapter-scoped summary/beat/decision 레코드 | 원문 revision과 source hash를 함께 저장 |
| 장기 작품 기억 | project-scoped fact/timeline/relationship 레코드 | chapter position/effective range와 provenance 필수 |
| 요청 context | `ContextBundle` | 저장하지 않고 요청마다 재계산; debug evidence만 별도 보관 |

`ContextBundle`을 장기 기억 저장소로 승격하지 않는다. 저장된 파생 기억은 항상 `source_chapter_id`, `source_revision`, `source_sha256`, `created_at`, `approved/state`를 가진다.

### 2. 최소 도메인 계약

새 저장소를 구현할 때 후보 필드는 다음과 같다.

```text
MemoryEntry
- id
- project_id
- chapter_id nullable
- source_revision nullable
- source_sha256
- kind: summary | beat | decision | fact | timeline | relationship_note
- body
- visibility: draft | approved | retired
- effective_from_sort_order nullable
- effective_to_sort_order nullable
- provenance_json
- created_at / updated_at
```

이는 구현 승인이 아니라 설계 후보이다. `kind`별 의미와 writer가 별도여야 하며, 자유 텍스트 하나에 canon·미래 복선·작가 메모를 섞지 않는다.

## stale 판정

1. 요청의 `chapter_id`와 `expected_revision`을 먼저 검증한다.
2. 기억 레코드의 `source_revision` 또는 `source_sha256`이 현재 원문과 다르면 `stale`로 표시한다.
3. stale 기억은 provider context에 자동 주입하지 않는다.
4. 재계산은 현재 원문을 읽고 새 레코드를 append하는 방식으로 한다. 기존 레코드를 덮어써 provenance를 잃지 않는다.
5. chapter/project 소속이 다르면 422/404로 거부하고 fallback으로 숨기지 않는다.
6. 미래 chapter position의 fact/foreshadow는 현재 chapter context에 넣지 않는다. 작가가 approved visibility를 명시해도 시간축 규칙을 우회하지 않는다.
7. 원문 교체는 기존 `replace_manuscript`의 revision/snapshot transaction을 사용한다. 기억 갱신 실패가 원문 저장 성공을 가장하지 않도록 별도 상태와 retry를 둔다.

## 회귀 테스트 설계

구현 전 테스트 fixture와 acceptance evidence를 먼저 확정한다.

- 같은 chapter의 revision 변경 후 이전 memory가 stale이 되는지
- snapshot 복원 후 source hash/revision과 memory 상태가 다시 맞는지
- 다른 project의 memory ID/character/lore가 422로 거부되는지
- 미래 chapter의 fact/foreshadow가 현재 context에서 제외되는지
- chapter 0개 작품과 volume 없는 chapter에서 context가 빈 값으로 안전하게 동작하는지
- 같은 원문에서 재계산이 중복 canonical fact를 만들지 않는지
- concurrent write에서 revision conflict와 memory append가 서로의 성공을 오인하지 않는지
- generate, canon, review가 동일한 frozen bundle을 사용하고 await 뒤에 context를 다시 읽지 않는지
- source hash가 화면/API/DB evidence와 일치하는지

## 마이그레이션·운영 게이트

- 새 테이블은 Alembic migration과 downgrade 계획이 없으면 추가하지 않는다.
- 기존 `Project.memo`, `Chapter.memo`, `VolumeNote` 데이터를 자동 분류해 memory로 승격하지 않는다. 분류 규칙과 사용자 승인 없이는 원문 의미가 바뀐다.
- 기존 서비스와 운영 DB를 중지하거나 migrate하지 않는다.
- 임시 DB에서 migration, stale 판정, rollback, ownership negative corpus를 먼저 검증한다.
- 새 memory가 provider prompt에 들어가는 경우 실제 `payload.messages`에서 inclusion/exclusion을 확인한다. metadata 라벨만 검사하지 않는다.

## 현재 결정과 미결정

결정:

- 원문/revision/snapshot은 정본으로 유지한다.
- 파생 기억은 source revision/hash와 provenance를 갖고 append/stale 모델을 사용한다.
- 요청 bundle과 영속 기억을 분리한다.
- 구현 전 실제 회귀 fixture와 negative corpus를 만든다.

미결정:

- `MemoryEntry` kind 목록과 각 kind의 승인자
- timeline position의 기준(`sort_order`만 사용할지 별도 chronology를 둘지)
- 자동 요약 provider와 재계산 시점
- stale memory를 사용자에게 표시하는 UI
- migration/backfill 승인

## 안전 범위

이번 문서는 설계만 남긴다. 운영 DB, 실제 모델, 외부 API, 스키마 파일, Alembic migration은 건드리지 않았다.
