# E1 생성 이력 영속 — 구현 사양 (2026-09-14)

상위 설계: `docs/specs/2026-09-14-author-feedback-improvement.md` §3-E1/E2.
본 문서는 코드 대조로 확정한 세부 계약이다. E1은 생성 이력 영속, E2(처분 기록)의
수신 엔드포인트까지 같은 슬라이스에 포함한다 — 이력 없이 처분을 기록할 수 없으므로.

## 1. 스키마 — 2테이블

한 번의 API 호출이 여러 산출물을 낸다(아래 §2). 작가의 반영·폐기 대상은
"호출"이 아니라 개별 산출물이므로 봉투/산출물을 분리한다.

### `generation_runs` — 요청 봉투 (append-only)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | PK | |
| project_id | FK→projects CASCADE, index | nullable — 독립 /ai/review는 컨텍스트 없음 |
| chapter_id | FK→chapters SET NULL, index | nullable — 회차 삭제 시 run 보존(감사) |
| surface | str, CheckConstraint | `'generate'|'generate_parallel'|'review'` |
| preset_id | int | nullable — prompt_override 경로는 없을 수 있음 |
| model | str | 실제 해석된 모델 |
| reasoning_effort | str | nullable |
| input_sha256 | str(64) | `sha256(canonical_json(messages))` — 프롬프트 원문은 저장하지 않음 |
| input_manifest_json | JSON | `{context_metadata, injected_lore_ids, injected_foreshadow_ids, preset_id, episode_purpose, scene_id, worker_limit, brief}` — 번들의 주입 내역만 |
| prompt_chars | int | |
| applied_rules_json | JSON null | E6이 채울 승인 규칙 id 목록 — 지금 마이그레이션에 포함해 재마이그레이션 회피 |
| status | str, CheckConstraint | `'completed'|'provider_error'|'aborted'` — 전송 결과. 작가 처분과 별개 축 |
| wall_ms | int | |
| ai_usage_id | FK→ai_usage SET NULL | nullable — usage.record()가 id 반환하도록 1줄 변경 |
| created_at | datetime | 완결 시각(행 생성 시각) — started_at은 만들지 않고 wall_ms로 충분 |

### `generation_outputs` — 산출물 (append-only, 처분 대상)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | PK | |
| run_id | FK→generation_runs CASCADE, index | |
| channel | str, CheckConstraint | `'draft'|'review'|'refined'|'plan'|'worker'` |
| scene_order | int | nullable — channel='worker'일 때 장면 순번 |
| output_text | TEXT | 전문 보존 — E3 diff·E5 분석의 재료 |
| output_sha256 | str(64) | |
| output_chars | int | |
| outcome | str, CheckConstraint | `'pending'|'inserted'|'replaced'|'copied'|'discarded'` — 기본 pending |
| outcome_events_json | JSON | `[{outcome, at}]` 전이 이력 — 행 내 append-only |
| landed_text | TEXT null | 작가가 실제 삽입/교체한 텍스트(편집 후 반영이면 output과 다를 수 있음) |
| chapter_revision_at_action | int null | 처분 시점의 회차 revision — E3 드리프트 앵커 |
| outcome_at | datetime null | 최종 처분 시각 |
| created_at | datetime | |

체크 제약·인덱스·cascade 규칙은 `MemoryEntry`/`SummaryJob`의 기존 패턴을 따른다.

## 2. surface × channel 매트릭스

| 엔드포인트 | surface | 생성되는 outputs |
|---|---|---|
| POST /ai/generate | `generate` | `draft` ×1 (+review 옵션 시 `review`,`refined` — _split_review_stream 결과) |
| POST /ai/generate-parallel | `generate_parallel` | `plan` ×1 + `worker` ×N(scene_order) + `draft`(조립본) ×1 + `review` ×1 |
| POST /ai/review | `review` | `review`,`refined` — input은 사용자 draft(해시만, 번들 없음) |

## 3. 기록 경로 — 서비스 계층, best-effort

`app/services/generation_runs.py` 신설. `usage_service.record`와 동일하게
자체 `SessionLocal`을 열고 예외를 삼켜 본 스트림을 절대 막지 않는다.

```python
def finish_run(*, surface, payload_ctx, model, effort, messages, manifest,
               outputs: list[OutputSpec], status, wall_ms) -> int | None:
    """run+outputs+usage를 한 세션에 기록하고 run_id를 반환."""
```

- `usage_service.record` 시그니처 변경: `-> int | None`(신규 행 id). 기존 호출부 무영향.
- 기록 시점 = 각 SSE 스트림의 종료 지점 — `usage_service.record`가 이미 호출되는 곳.
  - `/ai/generate`: draft 스트림 종료 후 → run(status)·draft output. review 종료 후 같은 run에 review/refined output append.
  - 에러 경로(`except openai.APIError`/`Exception`)에서도 `status='provider_error'`로 부분 텍스트와 함께 기록 — case-05 RemoteProtocolError 같은 실측이 데이터가 된다.
  - generator 취소(클라이언트 끊김)는 `status='aborted'`로 기록 시도 — 실패해도 무해.
- run 행은 첫 산출물 확정 시점에 만들고 run_id를 이후 output append에 재사용한다.

## 4. SSE 계약 — additive만, 기존 이벤트 불변

기존 이벤트 순서·페이로드는 바꾸지 않는다. `done` 직전에 신규 이벤트 1건 추가:

```
event: generation_saved
data: {"run_id": 12, "outputs": {"draft": 34, "review": 35, "refined": 36}}
```

- parallel은 `outputs`에 `"plan":…`, `"worker_1":…`, `"worker_2":…` 포함.
- 프론트가 이 이벤트를 무시해도 기존 동작 동일(하위 호환). output id는 E2 처분 API의 키다.

## 5. E2 수신 엔드포인트 — `POST /api/v1/generation-outputs/{id}/outcome`

```json
{"outcome": "inserted|replaced|copied|discarded",
 "landed_text": "…",            // inserted/replaced 시 권장
 "chapter_revision": 41}         // 처분 시점 revision 앵커
```

- 전이 규칙: `pending → 임의`, `copied → inserted|replaced|discarded` 허용
  (복사 후 실제 삽입은 흔한 경로), 나머지는 terminal — 재전이 시 **409**.
- 모든 성공 전이는 `outcome_events_json`에 `{outcome, at}` append.
- 존재하지 않는 output → 404. 잘못된 outcome 문자열 → 422(스키마 Literal).
- `discarded`는 명시 액션만 기록 — pending 영구 잔존은 허용(세션 만료 스위프는 후속).

## 6. 읽기 엔드포인트 (테스트·후속 UI용 최소 계약)

- `GET /api/v1/chapters/{cid}/generation-runs` — run 목록 + outputs 요약(channel·chars·outcome)
- `GET /api/v1/generation-runs/{id}` — run + 전체 outputs 상세
- 프로젝트 스코프 목록은 E7 UI 때 추가 — 지금은 회차 단위만.

## 7. 스키마 변경 — `ReviewRequest` additive

```python
project_id: int | None = None   # 프론트가 알 때만 전송
chapter_id: int | None = None
```

독립 감수도 어느 작품의 원고를 감수한 것인지 남길 수 있게 한다. 미전송 시 null — 규칙 주입(E6)과 무관하게 이력만 보존.

## 8. Alembic

- 새 리비전 id: `ae1f2b3c4d58`, `down_revision = "9d0e1f2a3747"`(현재 head).
- 테이블 2개 + ai_usage FK 인덱스. downgrade는 drop 순서 역순.
- 기존 패턴: CheckConstraint 이름 `ck_generation_run_status` 등 명명.

## 9. 범위 밖 (명시적 제외)

- **RefineRun 미통합** — 윤문(M5) 경로는 이미 `result_text`+`accepted`를 보존한다.
  generation_runs는 ai_panel 3개 surface만 다룬다. 윤문 경로의 피드백 통합은 후속 단위.
- 규칙 주입(E6)·분석(E3/E5)·UI(E7)는 본 슬라이스에 없음.
- `applied_rules_json`은 이번에 컬럼만 만들고 항상 null로 둔다.

## 10. 테스트 계획 (fake provider — `test_ai_generate_stream.py`의 FakeAsyncOpenAI 재사용)

| # | 검증 |
|---|---|
| 1 | generate happy path → run 1 + draft output 1, sha/chars 일치, status=completed |
| 2 | generate + review 옵션 → outputs draft/review/refined 채널·내용 분리 저장 |
| 3 | draft 스트림 중 provider 에러 → status=provider_error + 부분 텍스트 보존 |
| 4 | generate-parallel → plan+worker(N, scene_order)+draft+review outputs |
| 5 | /ai/review → project/chapter null로 run 저장 |
| 6 | outcome 전이: pending→copied→inserted 성공, inserted→copied 409 |
| 7 | outcome landed_text·chapter_revision 저장 |
| 8 | chapter 삭제 → run의 chapter_id SET NULL로 보존; project 삭제 → CASCADE |
| 9 | SSE 이벤트 순서 하위호환 — 기존 스트림 테스트 전부 무수정 통과 |
| 10 | generation_saved 이벤트의 run_id/output id가 DB 실재 행과 일치 |
| 11 | 기록 실패(세션 오류 주입) 시에도 스트림 정상 완료 — best-effort 격리 |

## 11. 수용 기준

- 위 테스트 전부 통과 + 전체 회귀(현재 726P) 무결
- 원고·설정·프리셋 어떤 기존 컬럼도 이 기능이 쓰지 않음(쓰기 경로 = 신규 2테이블뿐)
- `alembic upgrade head` + `downgrade -1` 왕복 성공
- 독립 검토 2건: 스트림 무결성(additive만), 스키마 격리(프로젝트 스코프·cascade)
