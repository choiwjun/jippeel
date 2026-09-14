# E1·E2 수용 기록 — 생성 이력 + 작가 처분 기록 (2026-09-14)

작가 피드백 자가개선([전체 설계](../../specs/2026-09-14-author-feedback-improvement.md))의 첫 구현 슬라이스.
사양은 [E1 세부 사양](../../specs/2026-09-14-e1-generation-runs-spec.md)을 따른다.

## 범위

- **E1** — 생성 요청 봉투(`generation_runs`) + 산출물(`generation_outputs`) append-only 보존.
  입력 프롬프트 원문은 저장하지 않고 sha256·주입 manifest만 보존한다. 출력 텍스트는
  작가 diff 분석의 재료로 원문 보존한다.
- **E2** — 작가의 명시 UI 액션(끼워넣기/선택 교체/복사)을 output별 outcome으로 기록.
  자동 삽입·자동 반영은 없다. 기록 실패는 사용자 액션을 막지 않는다(best-effort).

## 구현 내용

### 데이터 모델 (`backend/app/models.py`)

- `GenerationRun` — 요청 봉투. `project_id`(CASCADE)·`chapter_id`(SET NULL, 감사 보존)·
  `surface`(generate/generate_parallel/review)·`preset_id`·`model`·`reasoning_effort`·
  `input_sha256`·`input_manifest_json`·`prompt_chars`·`applied_rules_json`(E6 대비)·
  `status`(completed/provider_error/aborted)·`wall_ms`·`ai_usage_id`(SET NULL).
- `GenerationOutput` — 산출물. `channel`(draft/review/refined/plan/worker)·
  `scene_order`(worker)·`output_text`·`output_sha256`·`output_chars`·
  `outcome`(pending/inserted/replaced/copied/discarded)·`outcome_events_json`(append-only
  전이 이력)·`landed_text`·`chapter_revision_at_action`·`outcome_at`.
- 한 요청이 여러 산출물을 낼 수 있어 run/output 2테이블로 분리했다.

### 마이그레이션

- `ae1f2b3c4d58_generation_runs.py` — head `9d0e1f2a3747` → `ae1f2b3c4d58`.
- `database.py`의 `ALEMBIC_HEAD` 상수·`test_migrations.py` 고정 버전을 갱신했다.

### 기록 서비스 (`backend/app/services/generation_runs.py`)

- `save_run(...)` — run + outputs를 한 세션에 기록, `(run_id, {channel: output_id})` 반환.
  worker 키는 `worker_{scene_order}`.
- `messages_sha256` — canonical JSON의 sha256으로 프롬프트 원문 대신 식별자 보존.
- `db` 파라미터로 요청 세션 재사용 — 테스트의 `get_db` 오버라이드 DB와 동일한
  트랜잭션/DB에 기록된다. `db=None`이면 기존 `SessionLocal` 폴백.
- `project_id` 미지정 시 `chapter_id`에서 유도 — 작품 격리 스코프 보존.
- 모든 예외를 삼켜 이력 기록이 생성 스트림을 절대 막지 않는다.

### usage 연동 (`backend/app/services/usage.py`)

- `record(...)`가 삽입된 `AiUsage.id`를 반환하도록 변경 + 선택적 `db` 세션.
- `summary(...)`도 선택적 `db` — `/ai/usage` 라우트가 요청 세션을 전달.
- 기존 호출부(foreshadows·quality·bootstrap·projects) 전부 세션 전달로 통일.

### API (`backend/app/routers/generation_runs.py`)

- `POST /api/v1/generation-outputs/{oid}/outcome` — outcome 전이 기록.
  상태 기계: `pending → {inserted|replaced|copied|discarded}`, `copied → {inserted|replaced|discarded}`.
  종결 상태 재전이는 409 — 이력을 덮어쓰지 않고 `outcome_events_json`에 append만 한다.
- `GET /api/v1/chapters/{cid}/generation-runs` — 회차별 run 목록(outputs 요약).
- `GET /api/v1/generation-runs/{rid}` — run 상세(전체 outputs 원문 포함).

### SSE 기록 배선 (`backend/app/routers/ai_panel.py`)

세 표면 모두 `finally`에서 `_finalize()`로 run을 기록하고 additive `generation_saved`
이벤트(`{run_id, outputs: {channel: id}}`)를 방출한다.

- `/ai/generate` — draft 스트림을 수집해 채널별 보존. draft 에러 시 부분 초안도 보존하고
  `status=provider_error`. 기존 계약 보존: draft 에러 시 `done` 미방출.
- `/ai/generate-parallel` — plan·worker×N(scene_order)·assembled draft·review 보존.
  generation 단계 실패 시 `status=provider_error` 후 기존처럼 `parallel_error` 방출·종료.
- `/ai/review` — review·refined 채널 보존. `ReviewRequest`에 additive
  `project_id`/`chapter_id` 추가(프론트가 알 때만 채움).
- `GeneratorExit`/`CancelledError`는 `status=aborted`로 기록 후 재전파 — abort 시
  클라이언트가 끊겨 `generation_saved`는 미방출이나 DB에는 남는다.

### 프론트 계측

- `frontend/src/lib/aiStream.ts` — `generation_saved` 파싱 + `onGenerationSaved` 핸들러(additive).
- `frontend/src/stores/aiPanelStore.ts` — `generationRunId`·`generationOutputIds`
  (channel→id) 상태 + `startStream`/`resetResult`에서 초기화.
- `frontend/src/components/panels/AiPanel.tsx` — 명시 액션 계측:
  - 끼워넣기 → `inserted`, 선택 교체 → `replaced`(선택 없어 끝에 추가되면 `inserted`),
    복사 → `copied`.
  - `landed_text`=실제 반영 텍스트, `chapter_revision`=처분 시점 회차 revision 앵커.
  - 기록은 fire-and-forget — 실패해도 편집·복사를 막지 않는다.
  - `discarded`는 명시 폐기 UI가 없어 기록하지 않는다 — `pending` 잔류가 정상 상태.

## 안전성

- 생성 이력은 원고 정본이 아니다 — 읽기·처분 전이만 제공, 원고·설정 변경 없음.
- 회차 삭제는 `chapter_id`를 NULL로 두고 이력을 보존한다. 작품 삭제는 작품 데이터
  생명주기에 따라 CASCADE로 함께 삭제된다.
- `applied_rules_json`은 E6에서 승인 규칙 주입 시 채운다 — 현재 빈 배열.
- 프롬프트 원문 미보존(sha256만). 출력 원문은 분석 재료로 보존 — 작가 본인 데이터이며
  외부 전송 없음.

## 검증

- `backend/tests/test_generation_runs.py` 신규 12P:
  - generate 정상 run + draft/review/refined 채널 보존·`generation_saved` 이벤트
  - generate_parallel plan/worker/draft/review 보존·scene_order
  - 독립 /ai/review 표면 기록
  - provider_error 시 부분 초안·status 보존
  - abort 시 `status=aborted` 기록
  - outcome 전이·409 재전이·`outcome_events_json` append-only
  - 회차 삭제 시 run 보존 + `chapter_id` NULL
  - ai_usage FK 연결(요청 DB 세션)
  - 프로젝트 격리(타 작품 chapter로 유도된 project_id 정확성)
- `test_migrations.py` 갱신 — head `ae1f2b3c4d58`.
- 전체 회귀: **738 passed / 1 skipped / 70 subtests / violations 0** (격리 러너).
- 프론트: `tsc -b` 0 오류 + `vite build` 통과. fixture tripwire 회피 확인 —
  fixture SSE는 `generation_saved`를 보내지 않으므로 `recordOutcome` no-op.

## 한계·잔여

- `discarded` 전이는 UI 진입점 부재로 미기록 — E7에서 명시 폐기 액션과 함께 처리.
- 프로젝트 단위 이력 목록 API는 E7 UI와 함께 추가 예정(현재 회차 단위만).
- E3 결정론 분석·E4 규칙 저장소·E5 제안 job·E6 주입·E7 UI는 미착수 — 본 슬라이스는
  데이터 수집 기반만 제공한다.
