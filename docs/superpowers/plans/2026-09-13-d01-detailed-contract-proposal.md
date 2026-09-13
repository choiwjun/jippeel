# D01 회차 목표 영속화 — 상세 계약 제안서

- 작성일: 2026-09-13
- 상태: **제안서 — 소유자 승인 대기**. 이 문서는 상세 사양 승인 또는 구현 승인이 아니며, 승인 전까지 어떤 소스·schema·migration·테스트도 변경하지 않는다.
- 선행 문서: [D01 조사·요구 질문](2026-09-13-d01-contract-questions.md), [조사 원문](../../audits/d01-goal-contract-2026-09-13/research.md.txt), [단일 원장 D01](../../handoffs/2026-09-08-remaining-work.md), [통합 인계](../../handoffs/2026-09-13-commit-handoff.md), [순차 실행 승인](2026-09-12-remaining-sequence.md).
- 기준 소스: 현재 HEAD `c2e4f6a`. 문서에 남은 `c1a92c4`는 9월 13일 게시 이전 기준점이다.

## 1. Executive summary

- 회차 목표(브리프)는 현재 **생성 요청에만 존재하는 임시 구조체**다. `EpisodeBrief`는 스스로 "DB 마이그레이션 없이 요청에만 존재하는 구조체"라고 명시한다(`backend/app/schemas.py:408–424`). 프론트의 `episodeBrief`는 Zustand 단일 메모리 값이며 앱 재시작·재진입 시 소실된다(`frontend/src/stores/aiPanelStore.ts:393–395`).
- D01의 핵심은 **작품/회차별 목표의 영속 저장과 재진입 복원**이다. 이 제안서는 저장 경계·버전·동시성·생성 연계·검증 범위를 구체화하고, **최신값만 저장(A) vs 변경 이력 조회·복원(B)** 의 소유자 결정과 나머지 미결정 제품 질문을 분리해 둔다.
- 추천: **B(영구 저장 + append-only 변경 이력)**. D03의 목표↔원문 근거 연결을 위해서도 과거 목표 내용이 필요하다. 다만 아직 승인되지 않았으므로 이 문서의 계약 상세는 A/B 모두에 적용 가능한 공통 부분과 B 전용 부분을 구분한다.
- 완료된 범위(C13/B01/B02/B04, M01~M05, B03, C10 provider-free planner, C03 원고 보존, C04 AI 맥락, C09 고정 OAuth)는 **다시 열지 않는다**. D03/D04는 구현하지 않고 다음 handoff용 의존성·테스트 매트릭스만 제시한다.

## 2. 현재 상태의 근거 — 확인한 소스만

| 승인된 D01 요구 | 현재 소스 사실 |
| --- | --- |
| 작품/회차별 목표 영속 저장 | `EpisodeBrief`는 요청 전용 Pydantic 모델이며 DB 테이블이 없다(`backend/app/schemas.py:408–424`). |
| 재진입·재시작 복원 | `episodeBrief`는 메모리 병합 setter뿐이고(`frontend/src/stores/aiPanelStore.ts:393–395`), 회차별 `_directiveMap`도 메모리 맵이다(`frontend/src/stores/aiPanelStore.ts:340–357`). `EpisodeBriefState`/`EMPTY_EPISODE_BRIEF`는 폼 원문 문자열 보관용이다(`frontend/src/stores/aiPanelStore.ts:49–73`). |
| 버전·원문 연결 | `Chapter.revision`(낙관적 잠금)과 `ChapterSnapshot`(교체 전 복구본)은 원문 보존용이다(`backend/app/models.py:52–106`). 목표 버전·이력 계약은 없다. |
| 빠른 메모 | `Chapter.memo`는 자유 텍스트이며 `PATCH /chapters/{cid}`로 저장된다(`backend/app/models.py:65`, `backend/app/routers/projects.py:202–210`, `frontend/src/pages/EditorPage.tsx:166–168,238–249`). 목표와 혼용하지 않는다. |
| 생성 요청 동결 | 생성 시작 시 directive와 브리프를 `structuredClone`으로 복제하고(`frontend/src/components/panels/AiPanel.tsx:273–283`), `flushManuscriptDraft` 후 `expected_revision`을 고정한다(`frontend/src/components/panels/AiPanel.tsx:294–322`). 브리프 불완전은 `incomplete`(미전송), 계약 위반은 `invalid`(경고 후 미전송)로 구분한다(`frontend/src/components/panels/AiPanel.tsx:45–109`). |
| 서버 context 조합 | 공통 `build_context_bundle`이 revision 불일치를 409로 거절하고(`backend/app/services/ai_context.py:449–471`), 브리프 블록은 `_format_brief_block` 한 곳에서 조립한다(`backend/app/services/ai_context.py:218–237,481–482`). router의 `_build_context_blocks`/`_build_messages`는 이 번들을 그대로 사용한다(`backend/app/routers/ai_panel.py:198–250`). |
| 목적(purpose) | `episode_purpose`는 브리프와 별도의 요청 필드이며 목적별 브리프 검증에 관여한다(`backend/app/schemas.py:405,432,459–472`). system 프롬프트의 `purpose_directive`는 세 가지 목적 문구를 고정한다(`backend/app/services/ai_context.py:195–215`). 프론트에서는 회차별 directive로 보관된다(`frontend/src/stores/aiPanelStore.ts:340–357`). |
| 삭제·보존 정책 | 회차 DELETE는 `BEGIN IMMEDIATE`로 writer lock을 먼저 확보하고 복선·기억 참조 시 409다(`backend/app/routers/projects.py:275–304`). 원문 복원은 같은 회차 snapshot만 허용하고 과거 revision 번호로 되돌리지 않는다(`backend/app/routers/projects.py:257–272`, `backend/app/services/manuscripts.py:55–123`). |
| 고정 OAuth | 프론트는 고정 `ChatGPT OAuth` / `gpt-5.6-luna` / `xhigh`만 사용한다(`frontend/src/components/panels/AiPanel.tsx:167–173,353–364`). |
| 요약 planner | `summary_jobs.py`는 provider 없이 deterministic manifest만 만든다. `SummaryManifestItem`은 원문 revision/hash·prompt/provider/model/options와 idempotency key를 담지만 **목표 버전은 없다**(`backend/app/services/summary_jobs.py:1–5,24–38,83–156`). |

## 3. 남은 작업 순서와 의존성

승인된 순서([순차 실행 승인](2026-09-12-remaining-sequence.md), 원장 §8)를 유지한다.

1. **D01 — 이 문서.** 소유자 결정(A/B 및 §8 질문) → 좁은 상세 사양 승인 → 합성 RED → 최소 구현 → 회귀·계측 → 독립 검토 → 수용.
2. **D03 — 얇은 단위.** D01의 안정된 회차 소속·목표 버전·기준 원문 revision을 접점으로 기획→집필→퇴고→완결·재개 계약을 별도 승인한다(§6). 이 문서는 D03을 구현하지 않는다.
3. **D04 — job/worker.** C10의 provider-free planner는 완료물이며 재작성하지 않는다. job/idempotency 저장 방식·schema·worker·draft·중단/재개·실패 계약을 fake worker로 먼저 검증한다(§7).
4. **V01/V02/V04 — 검증 보강.** 프론트 source-mapped coverage, 복원 실패 injection, 외부 metrics 소스 비교(원장 §5).
5. **G02→G01→G03→G04 — 실제 자원 수용.** 실제 OAuth/provider·운영 DB·credential/키 복구·지정 Windows 실기기는 각 gate의 환경·예산·접근 허가 확보 후에만 실행한다(원장 §6).

D02(인지 구분 기억 확장)는 이 묶음의 자동 추가 범위가 아니다.

## 4. A vs B 결정표와 추천

| 비교축 | A. 최신 목표만 저장 | B. 변경 이력 조회·복원 |
| --- | --- | --- |
| 저장 형태 | 회차당 현재 목표 1행(또는 컬럼) + 독립 목표 버전 + 기준 원고 revision | 동일한 현재값 계약 + 목표 내용의 append-only 버전 이력 |
| 과거 목표 내용 조회 | 불가 — 버전 번호만으로 내용을 재구성할 수 없다 | 버전별 내용 조회 가능 |
| 과거 목표 복원 | 불가 | 지원 시 "새 목표 버전 생성"으로 처리(과거 덮어쓰기 아님) |
| schema/migration 비용 | 테이블 1개 또는 Chapter 컬럼 추가 | 테이블 + 이력 테이블(또는 통합 버전 테이블), 목록/선택 API 추가 |
| UI 비용 | 로딩/저장/충돌 안내 | + 이력 목록·비교·복원 확인 UI |
| D03 연결 | 현재 목표만 근거로 참조 가능. 목표가 바뀐 뒤에는 과거 판단 근거 소실 | 목표 버전 ↔ 원문 revision 근거 쌍을 유지해 변경 추적 가능 |
| 회귀 범위 | 저장/CAS/재진입 | + 이력 append-only·복원·삭제 보존 케이스 |
| 위험 | 나중에 이력을 추가하면 기존 row를 이력 모델로 이관해야 함 | 최소 범위를 넘는 기능 팽창 위험 — 이력 UI를 얇게 제한 필요 |

**추천: B, 단 두 단계로 얇게.** (1) D01에서 현재값 저장 + append-only 이력 row + 목록·복원의 최소 API까지 확정하고, (2) 이력 UI는 목록 조회·선택 복원만 포함하며 비교 diff·검색은 후속으로 미룬다. 복원은 항상 새 목표 버전을 만들어 이력을 지우지 않는다. 이는 기존 인계의 부모 추천(영구 저장 + 이력 보존)과 일치하지만, **최종 선택은 소유자 승인 대기다**.

A를 선택할 경우에도 현재값 계약(§5)은 동일하게 적용되며, 이력 요구가 나중에 필수가 되면 schema 재결정이 필요하다는 점을 명시한다.

## 5. D01 상세 계약 제안 (공통 부분)

### 5.1 작품/회차 범위

- 소유 단위: **회차당 목표 하나**. 작품 소속은 `Chapter.project_id` FK에서 도출한다(`backend/app/models.py:56`). 별도 `project_id` 입력을 받는 API는 실제 회차 소속과 대조해 불일치 시 422로 거절한다 — 기존 교차 소속 검증 패턴(`backend/app/services/ai_context.py:86–95`)과 동일.
- **작품 공통 목표는 이번 범위에 포함하지 않는다**(미결정 질문 Q1).
- 회차가 삭제될 수 없는 기존 조건(복선/기억 참조 409, `backend/app/routers/projects.py:275–304`)은 목표로 확장하지 않는다. 목표 row는 회차 삭제가 허용되는 경우 함께 정리(cascade)한다. B 선택 시 이력도 같은 생애를 따를지, provenance 보존을 위해 별도 정리 절차를 둘지는 §8 Q5로 남긴다.

### 5.2 목표 데이터 모델과 버전

- 권장 최소안(조사 후보 B): 회차당 현재 목표 1행의 별도 테이블. 필드 후보: `id`, `chapter_id`(unique FK), 목표 payload(기존 브리프 필드와 동일한 구조의 JSON), `goal_version`(독립 낙관적 버전), `base_manuscript_revision`, `created_at`/`updated_at`. `memo`에 JSON을 덮어쓰는 방식은 기존 메모 계약을 훼손하므로 채택하지 않는다.
- **목표 저장은 `Chapter.revision`을 증가시키지 않고 `ChapterSnapshot`을 만들지 않는다.** 목표 버전과 원문 revision은 별개다. 이를 어기면 기존 CAS·stale 의미(`backend/app/services/manuscripts.py:55–123`)가 바뀐다.
- B 선택 시 이력은 append-only이며 각 이력 row는 `goal_version`·payload·`base_manuscript_revision`·생성 시각을 보존한다. 복원은 이력 row를 현재값으로 "새 버전" 기록하는 쓰기다.
- 목표 payload의 필드 구조는 기존 `EpisodeBrief` 필드(`emotion_goal`, `core_events`, `character_choices`, `cost`, `prohibitions`, `next_hook`, `ending_intent`, `scene_type`, `target_chars_novelpia`, `backend/app/schemas.py:416–424`)를 재사용한다. **저장 검증은 생성 검증과 분리한다**(§5.4).

### 5.3 기준 원고 revision(`base_manuscript_revision`)

- 의미: 목표를 마지막으로 저장한 작가가 **작성 당시 본/의도한 원고 revision**. 저장 요청 시 클라이언트가 보고한 값을 기록한다.
- 목표 저장이 원문을 잠그지 않는다. 원문 저장/복원으로 revision이 진행해도 목표는 자동 갱신되지 않으며, UI는 "기준 revision과 현재 revision의 차이"를 stale 안내로만 표시한다.
- 원문 snapshot 복원(`backend/app/routers/projects.py:257–272`)은 목표를 변경하지 않고 기준 revision 차이 안내만 남긴다. 목표 과거본 복원이 원문을 되돌리는 일도 없다.

### 5.4 빈 값·부분 입력·삭제

- **저장 완성도 ≠ 생성 완성도.** 빈/부분 목표는 저장 가능하다. 단 필드당 길이·배열 개수 상한은 요청 계약(`BriefText` 1~500자, 배열 상한, `backend/app/schemas.py:404,416–424`)과 같은 보호 한도를 유지해 비대 payload를 막는다.
- 생성 적용 가능 여부는 기존 `parseEpisodeBrief`의 `incomplete`/`invalid` 구분(`frontend/src/components/panels/AiPanel.tsx:50–109`)과 백엔드 `validate_context_contract`(`backend/app/schemas.py:459–472`)를 그대로 따른다. 부분 저장본이 자동으로 생성 요청의 유효 브리프가 되는 일은 없다.
- 전 필드 빈 값 저장은 "목표 비우기"로 해석할지, 명시적 삭제 버튼과 확인으로 분리할지는 §8 Q4. 어떤 방식이든 실패·취소 시 입력을 유지한다.
- 삭제는 해당 회차의 목표 데이터만 대상으로 하며 `Chapter.memo`, 원문, snapshot, 기억, 복선에 영향을 주지 않는다.

### 5.5 purpose(회차 목적)

- 현재 `episode_purpose`는 브리프 밖의 별도 directive다(`backend/app/schemas.py:432`, `frontend/src/stores/aiPanelStore.ts:348–349`). 목표와 함께 영속화·복원할지는 §8 Q3으로 남긴다.
- 어떤 결정이든 serial/volume_end/series_finale의 검증·점수 의미와 `purpose_directive` 문구(`backend/app/services/ai_context.py:195–215`)는 변경하지 않는다.

### 5.6 AI 생성에서 현재 입력값과 저장값의 관계

- **기본값(제안): 생성은 현재 입력값(메모리 폼)을 사용한다.** 기존 동결 경로 — directive·브리프 `structuredClone`, `flushManuscriptDraft` 후 `expected_revision` 고정(`frontend/src/components/panels/AiPanel.tsx:273–322`) — 을 그대로 유지한다.
- 서버가 요청 브리프를 저장된 "최신 목표"로 몰래 교체하지 않는다. `context.brief`가 오면 요청 값을, 없으면 기존처럼 브리프 없이 생성한다(`backend/app/services/ai_context.py:481–482`).
- "저장된 목표 불러와 생성" 같은 대체 모드는 별도 제품 결정(§8 Q6)이며, 채택돼도 요청에 사용된 값과 출처를 metadata로 기록하는 기존 방침을 따른다.
- 목표 저장은 목표 달성 판정이 아니다. 자동 달성·완결 분류는 D01 범위가 아니다.

### 5.7 낙관적 동시성·stale 응답

- 쓰기는 `goal_version` 조건부 갱신: 요청 `expected_goal_version`과 현재 버전이 다르면 **409 + 현재 버전 반환**, 자동 재시도 없음. 이는 `manuscripts.replace_manuscript`의 CAS 패턴(`backend/app/services/manuscripts.py:72–105`)을 목표 버전에 응용한 것이며 원문 CAS와 분리된다.
- 모든 목표 읽기/쓰기 요청은 **요청 발생 당시의 작품·회차 식별자를 고정**한다. 회차 A에 보낸 늦은 응답이 회차 B의 폼·cache·toast를 변경하지 않는다 — M01/M02에서 수용된 경계 원칙을 새 목표 폼에 적용하는 것이며 해당 작업을 재구현하지 않는다.
- 목표 로딩 실패는 빈 목표로 해석하지 않고 실패 상태를 표시한다. 저장 실패·409 시 입력을 유지한다.
- 원문의 다른 stale 방어(전환·늦은 응답 방어, 복구 draft)는 변경하지 않는다.

### 5.8 API/UI 경계

- 목표 전용 read/write 경로와 typed 응답을 둔다(예: `GET/PUT /chapters/{cid}/goal` 형태의 별도 계약 — 정확한 경로는 상세 사양에서 확정). Chapter metadata PATCH 전체를 재설계하지 않는다.
- 프론트는 목표 전용 query key(예: `['chapter-goal', chapterId]`)를 사용해, 원문 상세 `['chapter', chapterId]` 응답이 목표 편집값을 덮는 결합을 피한다. 기존 query key 구조(`frontend/src/pages/EditorPage.tsx:52,142,160,540`)는 유지한다.
- UI는 기존 브리프 폼(`frontend/src/components/panels/AiPanel.tsx:895–959`)의 로딩/저장/오류 경계에 한정해 확장한다. 디자인 재작업·새 프레임워크 도입 없음.
- memo debounce 저장(`frontend/src/pages/EditorPage.tsx:238–249`)과 목표 저장은 서로 건드리지 않는다.

### 5.9 migration/backfill 원칙

- 새 migration은 기존 패턴(현재 head `1b2c3d4e5f60`, `backend/alembic/versions/1b2c3d4e5f60_long_memory_entries.py:12–13`)을 따른다. 실행은 합성 TEMP DB에서만 upgrade/downgrade·기존 행 보존을 검증한다. **운영 DB migration 실행은 별도 승인(G01)이며 이 문서로 허가되지 않는다.**
- backfill은 원칙적으로 없다: 기존 회차는 "목표 없음" 상태로 시작하고 최초 저장 시 row가 생긴다. B 선택 시 이력도 목표 최초 저장부터 쌓기 시작하며 소급 생성하지 않는다.
- `ai_endpoints` 등 legacy/hidden 호환 경로, 기존 테이블·컬럼 의미는 변경하지 않는다.

### 5.10 합성 TEMP DB·fake provider 회귀 케이스 (제안)

backend는 공식 runner `backend/scripts/run_backend_pytest.py`만 사용하고 직접 pytest·앱 import 선행을 금지한다([격리 가이드](../../runbooks/isolated-backend-tests.md): Windows 내부 fresh TEMP·guard·fake keyring 유지). frontend는 fixture-only/no-proxy/tripwire·전용 포트로 실행한다.

- 두 작품·두 회차의 목표 분리: 교차 조회/저장 거절, 작품-회차 불일치 422.
- 재진입 복원: 저장 → 새 세션 재조회 → 동일 payload·`goal_version`·`base_manuscript_revision`.
- 기존 회차의 목표 없음 처리: 빈 상태 응답과 로딩 실패의 구분.
- 부분 입력·공백·배열 상한: 저장은 허용/제한 내 정규화, 생성 경로의 기존 422 계약은 불변(`backend/tests/test_ai_generate_stream.py:491–534`, `backend/tests/test_ai_context_directives.py:40–63` 스타일의 fake_llm 검증 재사용).
- 목표 동시 저장 CAS: 두 writer 중 한 명 409, 실패 측 입력 보존.
- 목표 저장 전후 `Chapter.revision`·`content_md`·snapshot 수 불변. 원문 저장/복원(`backend/tests/test_manuscript_preservation.py:108–138` 경로) 후 목표와 기준 revision 안내.
- 늦은 응답 격리: A 회차 저장 응답이 B 회차 폼·query cache를 변경하지 않는 회귀(fixture-only).
- 목표 비우기/삭제: memo·원문·기억·복선 보존, 회차 삭제 409 정책 불변.
- fake provider 생성: 저장된 목표와 미저장 폼 편집이 있을 때 **요청에 선택된 값이 정확히 한 번** 브리프 블록으로 주입되고, purpose 지시·원문 flush/CAS·실패 처리가 유지되는지 검증(`backend/app/services/ai_context.py:218–237` 블록 계약).
- B 선택 시 추가: 이력 append-only·버전 목록 순서·복원이 새 버전을 만드는 것·삭제 정책·이력과 원문 revision 쌍 보존.
- migration: TEMP DB upgrade/downgrade, 기존 chapter/memory 행 보존.

## 6. D03 다음 handoff용 — 얇은 계약 의존성·테스트 매트릭스 (구현 아님)

범위(원장 D03): 기획→집필→퇴고→완결·재개 흐름에서 목표/사건/선택/대가와 원문 근거 연결, 미해결 감수·다음 장면 재개, 해결/의도적 미해결/외전 이관, 집필 확정과 연재 여부 분리·완결본 관리.

D01이 제공해야 하는 접점:

| 의존성 | D01에서 확정할 것 | D03이 사용하는 방식 |
| --- | --- | --- |
| 회차 소속·식별 | 목표의 `chapter_id` 소유 계약 | 근거 연결의 고정 키 |
| 목표 버전 | `goal_version` 단조 증가 | "어느 목표에 대해 집필했는가"의 근거 |
| 기준 원고 revision | `base_manuscript_revision` | 목표↔원문 시점 쌍, 변경 추적 |
| 이력(B 선택 시) | 과거 목표 내용 조회 | 결말 변경 영향·이관 판단 근거 |

D03 테스트 매트릭스(다음 handoff에서 상세화):

| 축 | 케이스 |
| --- | --- |
| 흐름 상태 | 기획→집필→퇴고→완결 전이와 불법 전이 거절 |
| 재개 | 미해결 감수/다음 장면에서 재개 시 목표 버전·원문 revision 표시 |
| 근거 연결 | 목표 필드(사건/선택/대가) ↔ 원문 범위의 링크 보존·파손 안내 |
| 완결 분리 | 집필 확정과 연재 완결 상태의 분리, 완결본 관리 |
| 이관 | 해결/의도적 미해결/외전 이관 표시 |

## 7. D04 다음 handoff용 — job/idempotency/worker 의존성·테스트 매트릭스 (구현 아님)

완료물: C10의 provider-free deterministic planner(`backend/app/services/summary_jobs.py:83–156`). 남은 것: job/idempotency 저장 방식·schema, worker, draft 저장, stale/중복/중단·재개·실패 처리. 기존 설계 체크리스트([auto-summary 설계](2026-09-11-long-memory-auto-summary-backfill.md) §9)가 승인 게이트다.

D01과의 의존성 결정(다음 handoff에서 확정):

| 질문 | 기본 제안 |
| --- | --- |
| 요약 worker 입력에 목표를 포함하는가 | **포함하지 않음.** manifest는 원문 revision/hash 기준을 유지(`backend/app/services/summary_jobs.py:24–38`). 목표를 prompt 입력으로 채택하면 그때 목표 버전/hash를 idempotency key·stale 검사에 넣을지 D04에서 결정한다. planner를 지금 재작성하지 않는다. |
| `draft_saved` 의미 | 승인도 목표 달성 판정도 아님(기존 설계 §4 유지). |

D04 테스트 매트릭스(다음 handoff에서 상세화, fake worker 우선):

| 축 | 케이스 |
| --- | --- |
| job 저장·idempotency | 동일 manifest 재실행 시 기존 draft 재사용/`duplicate_skipped`; unique 조합 선택안(설계 §5의 table vs deterministic comparison) |
| 상태 기계 | `planned → running → draft_saved`와 `skipped_empty`/`stale_source`/`provider_error`/`rejected` 분기 |
| 중단·재개 | 중단 시 저장된 draft 보존·manifest 재사용, partial batch를 전체 성공으로 표시하지 않음 |
| 실패 | `provider_error`만 retry 허용, `stale_source`는 새 작업 계획 |
| draft·승인 | 생성 결과는 항상 `draft`, 수동 승인만 `approved`, 기존 approved/retired 보존 |
| 경쟁 | 생성 완료 시점의 원문 revision/hash 재검사(설계 §3) |

## 8. 미결정 제품 질문 (소유자 결정 대기)

| # | 질문 | 제안 기본값 |
| --- | --- | --- |
| Q1 | 작품 공통 목표도 필요한가 | 이번 범위 제외. 회차 목표만 |
| Q2 | A vs B — 과거 목표 조회·복원을 필수로 할 것인가 | **B 추천**(§4). 미승인 |
| Q3 | `episode_purpose`를 목표와 함께 영속화·복원할 것인가 | 함께 저장(회차 directive의 영속화). 단 검증·문구 불변 |
| Q4 | 전 필드 빈 값 = 목표 비우기인가, 별도 삭제 동작인가 | 명시적 비우기/삭제 + 확인. B 선택 시 이력은 보존 여부 결정 필요 |
| Q5 | B 선택 시 회차 삭제가 허용될 때 목표 이력도 함께 삭제하는가 | 회차 생애와 동일(cascade). 단 D03 근거 참조 도입 시 재확인 |
| Q6 | 생성 시 "저장된 목표 사용" 모드를 둘 것인가 | 기본은 현재 입력값 유지. 저장본 사용은 선택 토글로만, 요청 출처를 metadata에 기록 |
| Q7 | 자동저장이 필요한가 | 명시적 저장 버튼. 자동저장 채택 시 큐·충돌·이탈 중 미저장 보존까지 별도 명세 |

## 9. 보존하는 기존 계약 — D01이 바꾸지 않는 것

- **요청 동결:** directive·브리프·설정의 `structuredClone` snapshot(`frontend/src/components/panels/AiPanel.tsx:273–293`).
- **flush와 revision 경계:** 생성 전 `flushManuscriptDraft`와 `expected_revision` 고정, 시작 토큰·회차 일치 재검사(`frontend/src/components/panels/AiPanel.tsx:294–324`).
- **revision/CAS:** 원문은 `expected_revision` 조건부 갱신 + snapshot 생성 + 409(`backend/app/services/manuscripts.py:55–123`, `backend/app/routers/projects.py:217–232`).
- **원고 보존:** `ChapterSnapshot` 복구본, 같은 회차 복원만 허용(`backend/app/models.py:89–106`, `backend/app/routers/projects.py:242–272`).
- **실패 처리:** 불완전 브리프 미전송·invalid 경고·실패 시 입력 유지·toast(`frontend/src/components/panels/AiPanel.tsx:50–109,262–281`).
- **고정 OAuth:** `ChatGPT OAuth`/`gpt-5.6-luna`/`xhigh` 고정, endpoint·모델 선택 UI 재도입 금지(`frontend/src/components/panels/AiPanel.tsx:167–173`). legacy `ai_endpoints`·hidden route는 migration 호환용으로만 유지.
- **기억·삭제 정책:** memory provenance/stale, 회차 삭제 409·cascade 정책 불변(`backend/app/routers/projects.py:275–304`).

## 10. 위험

| 위험 | 완화 |
| --- | --- |
| 폼(메모리)과 저장본의 이중 정본으로 인한 혼란 | §5.6에서 생성 입력을 현재 폼으로 고정하고, 저장 상태 배지만 추가. 저장본 사용은 선택 모드(Q6) |
| 저장 검증과 생성 검증의 혼동으로 부분 작성 저장이 막힘 | §5.4의 완성도 분리. 상세 사양에 두 검증의 매트릭스 명시 |
| 목표 저장이 원문 CAS·snapshot 의미를 오염 | 독립 `goal_version`과 `base_manuscript_revision` 분리(§5.2–5.3) |
| B 선택 시 이력 기능 팽창 | 이력 UI를 목록·복원으로 제한하고 diff/검색은 후속 |
| 늦은 응답이 다른 회차 UI를 오염 | 요청 시점 식별자 고정 + 전용 query key(§5.7–5.8) |
| A1 참고(기존 provider 오류 메시지 전달, `backend/app/routers/ai_panel.py:280`)가 목표 저장과 무관하게 재지적 | 별도 후속 범위로 유지. D01에서 제품 오류 계약을 바꾸지 않는다 |

## 11. 금지 작업 (이 문서의 승인으로도 허용되지 않음)

- 운영/기존 DB 접근·migration 실행·배포, credential/keyring 조회·변경, 실제 OAuth/provider/model 호출·비용 발생, 지정 장치 접근, 유료 외부 자원 사용.
- stage/commit/push 및 Git 설정 변경.
- 완료 범위 재구현: C13(B01/B02/B04), M01~M05, B03, C10 planner 재작성, C03/C04/C09 계약 변경.
- `EpisodeBrief` 생성 검증·purpose 의미·`purpose_directive` 문구, 원문 CAS/snapshot/flush/요청 동결/실패 처리 변경.
- D02 자동 추가, D03/D04 구현 착수(§6–§7은 계획 제시일 뿐이다).
- 새 사용자/권한 체계 도입, 목표 달성 자동 판정·완결 자동 분류.

## 12. 수용 기준과 증거 형식 (승인 후 적용)

- **실행:** backend는 `backend/scripts/run_backend_pytest.py`만. exit 0과 함께 위반 latch 0·실제 subprocess 시도 0을 확인한다. 기존 `.coverage`·crypto/canon/bootstrap·Git index/HEAD를 불변 기준으로 둔다.
- **frontend:** fixture-only/no-proxy/tripwire·전용 포트·공유 Vite cache 순차 실행, axe serious/critical 0, TS/build PASS.
- **coverage:** 승인된 국소 목록에 한한 변경범위 line/branch 근거. 전체 V01로 확대 해석하지 않는다.
- **독립 검토:** fresh 2축(제품/회귀, 데이터·격리·보존) 후 부모 수용. 검토 전후 대상 소스·보호 대상 hash 불변 확인.
- **증거:** RED 로그 원문 → 최종 실행 로그 → manifest(경로·sha256·byte) → 수용 문서 순으로 남기고, 실패·차단 기록을 PASS로 고쳐 쓰지 않는다. 선별 사본과 원본 경로를 구분한다.
- **원장 갱신:** D01 항목의 완료 범위·남은 범위·근거·승인 조건을 [전체 작업 현황](../../handoffs/2026-09-08-remaining-work.md)에서만 갱신한다.

---

*이 제안서의 모든 항목은 소유자 승인 전까지 실행 계획이 아니며, 승인된 항목만 상세 사양→구현으로 진행한다.*
