# 장편 기억 최소 수직 슬라이스 구현 계획

## 목표

작품·회차의 정본과 파생 기억을 분리하고, 기억이 만들어진 chapter revision/hash와 시간축을 보존한다. 현재 회차 context에 넣을 수 있는 approved 기억만 deterministic하게 선택한다.

## 범위

- `MemoryEntry` SQLAlchemy 모델
- Alembic head migration
- `app.services.long_memory`의 생성·stale 판정·context 선택·포맷 함수
- 임시 DB 기반 회귀 테스트
- 설계/HANDOFF 문서 갱신

## 제외

- 운영 DB migration 실행
- 프론트 UI
- 자동 요약 provider 호출
- 기존 데이터 자동 backfill
- 실제 모델 호출

## 계약

`MemoryEntry` 필드:

- `project_id`, `chapter_id` nullable
- `source_revision`, `source_sha256`
- `kind`: summary/beat/decision/fact/timeline/relationship_note
- `body`
- `visibility`: draft/approved/retired
- `effective_from_sort_order`, `effective_to_sort_order`
- `provenance_json`, timestamps

선택 규칙:

1. project 소속이 target project와 같아야 한다.
2. approved만 기본 선택한다.
3. source chapter revision/hash가 현재 원문과 다르면 stale로 제외한다.
4. source chapter가 target보다 미래면 제외한다.
5. effective range 밖이면 제외한다.
6. 선택 순서는 kind, source chapter position, id로 결정한다.

## 단계

1. 실패 테스트: model/service import와 선택 규칙을 먼저 작성한다.
2. 최소 모델·서비스를 구현한다.
3. migration을 작성하고 임시 DB head upgrade를 검증한다.
4. 전체 backend 회귀와 신규 테스트를 실행한다.
5. 운영 migration은 별도 승인 전까지 실행하지 않는다.

## Build result (2026-09-10)

- `MemoryEntry` model, `long_memory` service, migration `1b2c3d4e5f60`, and tests were implemented.
- Temporary Alembic upgrade reached `1b2c3d4e5f60`.
- New tests: 2 passed. Full backend suite: 279 passed with deprecation warnings treated as errors.
- Prompt injection, UI, automatic summarization, backfill, and production migration remain intentionally outside this slice.
