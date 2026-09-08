# AI 집필 맥락 흐름 연구 — NEXT phase

- 작성 시각: 2026-09-08T03:23:56.681481+00:00
- 범위: 정적 코드 리서치. 런타임 검증, DB 실행, 테스트 실행, 앱 import는 하지 않았다.
- 변경 범위: 이 문서만 작성했다. 원고 보존 작업은 완료된 것으로 보고 재개하지 않는다.
- 기준 파일: `backend/app/routers/ai_panel.py`, `backend/app/services/parallel_writer.py`, `backend/app/services/canon.py`, `backend/app/schemas.py`를 시작점으로 실제 호출부와 테스트를 추적했다.

## 1. 현재 컨텍스트 조립 흐름

### 1.1 단일 생성 `/ai/generate`

1. `generate()`가 엔드포인트를 조회하고 `_build_messages()`를 호출한다 (`backend/app/routers/ai_panel.py:508-512`).
2. `_build_messages()`는 `_build_context_blocks()` 결과를 `다음 컨텍스트를 참고해 작성하세요.` 뒤에 붙이고, 프리셋과 `prompt_override`를 `지시:` 아래에 붙인다 (`backend/app/routers/ai_panel.py:293-312`).
3. system 메시지는 기본 `NOVEL_SYSTEM_PROMPT`이다. `context.style_profile=true`이면 프로젝트의 `style_profile`을 system 뒤에 추가한다 (`backend/app/routers/ai_panel.py:313-329`).
4. 초안 스트림이 끝나면 선택적 감수 패스가 같은 SSE 안에서 실행된다. 감수 user 메시지는 기존 생성 user 메시지와 `[초안 원고]`를 같이 받는다 (`backend/app/routers/ai_panel.py:570-581`).

현재 포함되는 블록은 다음과 같다.

| 항목 | 현재 포함 방식 | 증거 |
|---|---|---|
| 회차 브리프 | `context.brief`가 있으면 가장 앞 블록으로 직렬화 | `backend/app/routers/ai_panel.py:140-180`, `backend/app/schemas.py:332-372` |
| 현재 장면 | `scene_id`가 있으면 장면 본문을 포함하고, 장면의 회차에서 project_id를 추론할 수 있음 | `backend/app/routers/ai_panel.py:183-190` |
| 현재 회차 | `chapter_id`가 있으면 회차 제목과 본문을 포함 | `backend/app/routers/ai_panel.py:191-198` |
| 회차 목차/권 개요/다음 화 | `auto_outline=true`와 `chapter_id`가 있을 때 회차 `memo`, `VolumeNote`, 다음 회차 `memo`를 포함 | `backend/app/routers/ai_panel.py:202-243` |
| 직전 회차 | `previous_chapter=true`이면 직전 회차 끝 2,000자를 포함 | `backend/app/routers/ai_panel.py:219-228`, `backend/app/routers/ai_panel.py:61` |
| 선택 캐릭터 | `character_ids`로 지정된 `Character`의 일부 필드 포함 | `backend/app/routers/ai_panel.py:244-254` |
| 선택 로어 | `lore_ids`로 지정된 `LoreEntry` 포함 | `backend/app/routers/ai_panel.py:255-258` |
| 자동 로어 | project_id가 있을 때 현재 텍스트와 지시문을 매칭해 자동 포함 | `backend/app/routers/ai_panel.py:259-274`, `backend/app/services/injection.py:47-88` |
| 자동 복선 | project_id가 있을 때 `status == "설치"` 복선을 최신순으로 포함 | `backend/app/routers/ai_panel.py:275-289` |
| 문체 | user 블록이 아니라 system 메시지에 추가 | `backend/app/routers/ai_panel.py:314-327` |
| 관계 | 포함하지 않음 | `backend/app/routers/ai_panel.py:18`, `backend/app/routers/ai_panel.py:244-258` |

### 1.2 병렬 생성 `/ai/generate-parallel`

1. `generate_parallel()`은 `ParallelGenerateRequest`를 `GenerateRequest` 모양으로 바꾼 뒤 `_build_messages()`를 재사용한다 (`backend/app/routers/ai_panel.py:617-629`).
2. planner user 메시지는 `base_messages[-1]['content']`를 그대로 앞에 붙이고 장면 계약 JSON 요구를 추가한다 (`backend/app/routers/ai_panel.py:642-658`, `backend/app/routers/ai_panel.py:676-685`).
3. 각 worker user 메시지도 `base_messages[-1]['content']`와 자기 장면 계약을 받는다 (`backend/app/routers/ai_panel.py:701-721`).
4. worker 결과는 `parallel_writer.run_parallel_workers()`에서 동시성 제한 뒤 order 순으로 정렬된다 (`backend/app/services/parallel_writer.py:126-155`). 최종 조립도 order 순이다 (`backend/app/services/parallel_writer.py:112-123`).
5. parallel reviewer user 메시지는 `base_messages[-1]['content']`와 장면별 계약+원고를 받는다 (`backend/app/routers/ai_panel.py:778-785`, `backend/app/services/parallel_writer.py:91-109`).

중요 차이: 병렬 흐름은 user 컨텍스트는 재사용하지만 system 쪽 문체 컨텍스트는 재사용하지 않는다. 단일 생성은 `Project.style_profile`을 system에 붙이지만 (`backend/app/routers/ai_panel.py:314-327`), 병렬 planner는 별도 `planner_system`을 쓰고 (`backend/app/routers/ai_panel.py:642-649`), worker는 원본 `NOVEL_SYSTEM_PROMPT`만 쓰며 (`backend/app/routers/ai_panel.py:712-715`), parallel reviewer도 별도 system만 쓴다 (`backend/app/routers/ai_panel.py:778-780`).

### 1.3 canon 검사 `/canon-check`

1. `canon_check()`는 `chapter_id`로 회차를 조회하고 기본 AI 엔드포인트를 사용한다 (`backend/app/routers/quality.py:28-47`).
2. `canon_service.run_canon_check()`는 `build_messages()`가 만든 메시지를 LLM에 보낸다 (`backend/app/services/canon.py:85-124`).
3. 컨텍스트는 검수 대상 회차 본문, 직전 회차 끝 1,000자, 같은 프로젝트의 모든 캐릭터, 모든 로어, `status in ("설치", "보류")` 복선이다 (`backend/app/services/canon.py:30-82`).
4. 결과는 `CanonRun`에 저장된다. 저장되는 것은 `chapter_id`, `model`, `issues_json`, `context_json`이다 (`backend/app/routers/quality.py:56-67`, `backend/app/models.py:168-177`). 현재 원고 revision이나 content hash는 canon run에 없다.

## 2. 프론트엔드 호출 모양

- AI 패널은 단일/병렬 모드에 따라 같은 body를 만들고 `streamGenerate` 또는 `streamParallelGenerate`를 선택한다 (`frontend/src/components/panels/AiPanel.tsx:206-246`). 실제 POST 경로는 `frontend/src/lib/aiStream.ts:239-245`에 있다.
- body의 `context.chapter_id`는 `c.includeChapter ? c.chapterId : null`이다 (`frontend/src/components/panels/AiPanel.tsx:211-222`).
- AI 패널 store 기본값은 `chapterId: null`, `includeChapter: false`, `autoLore/autoOutline/autoForeshadow: true`, `styleProfile: false`이다 (`frontend/src/stores/aiPanelStore.ts:183-196`).
- 에디터의 “AI 패널” 버튼은 패널을 열 뿐 AI 패널 context의 `chapterId`를 설정하지 않는다 (`frontend/src/pages/EditorPage.tsx:113-120`).
- `ContextSection`은 현재 에디터 `chapterId`를 읽어 UI를 보여주지만, “현재 회차” 체크박스의 onChange는 `includeChapter`만 바꾸고 `chapterId`를 넣지 않는다 (`frontend/src/components/panels/AiPanel.tsx:595-604`, `frontend/src/components/panels/AiPanel.tsx:649-654`).
- `previous_chapter`는 backend schema에 있지만 (`backend/app/schemas.py:360-361`), 현재 AI 패널 body에는 보내지 않는다 (`frontend/src/components/panels/AiPanel.tsx:211-222`).
- 캐릭터 페이지와 로어북 페이지는 AI 패널 context에 선택 캐릭터/로어 ID를 넣는다 (`frontend/src/pages/CharactersPage.tsx:286-301`, `frontend/src/pages/LorebookPage.tsx:263-280`).

## 3. 현재 확인된 divergence / 누락 / 안전하지 않은 지점

### D1. 에디터에서 연 AI 패널이 현재 회차를 실제 요청에 넣지 못할 수 있음

현재 에디터 버튼은 AI 패널을 열기만 한다 (`frontend/src/pages/EditorPage.tsx:113-120`). store 기본 `contextSelection.chapterId`는 `null`이다 (`frontend/src/stores/aiPanelStore.ts:183-196`). UI 체크박스도 `includeChapter`만 바꾼다 (`frontend/src/components/panels/AiPanel.tsx:649-654`). 요청 body는 결국 `chapter_id: null`을 보낼 수 있다 (`frontend/src/components/panels/AiPanel.tsx:211-222`).

그 결과 backend의 회차 본문/목차/권 개요/다음 화/직전 회차 컨텍스트는 생성되지 않는다. 자동 로어와 자동 복선도 project_id를 못 얻으면 실행되지 않는다 (`backend/app/routers/ai_panel.py:191-243`, `backend/app/routers/ai_panel.py:259-289`).

### D2. backend 컨텍스트 조립은 ID 소속 불일치를 막지 않는다

`_build_context_blocks()`는 `scene_id`, `chapter_id`, `character_ids`, `lore_ids`, `project_id`를 한 요청에서 받지만 동일 작품/회차 소속 검증을 하지 않는다.

- 장면과 회차를 각각 조회하고 둘 다 블록에 넣는다. 서로 다른 작품이어도 명시적으로 차단하는 코드가 없다 (`backend/app/routers/ai_panel.py:183-198`).
- `project_id`가 이미 있으면 장면/회차의 project_id로 덮지 않는다 (`backend/app/routers/ai_panel.py:182-190`, `backend/app/routers/ai_panel.py:197`). 따라서 잘못된 `project_id`가 자동 로어/복선과 문체에 쓰일 수 있다 (`backend/app/routers/ai_panel.py:259-289`, `backend/app/routers/ai_panel.py:314-327`).
- 선택 캐릭터와 선택 로어는 ID만으로 조회한다. 추론된 project_id와 같은 작품인지 확인하지 않는다 (`backend/app/routers/ai_panel.py:244-258`).

### D3. 선택 컨텍스트의 순서와 예산이 명확하지 않다

자동 로어는 점수 내림차순, 동점 id 오름차순이다 (`backend/app/services/injection.py:27-57`). 자동 복선은 `created_at desc, id desc` 뒤 limit이다 (`backend/app/routers/ai_panel.py:275-282`). 반면 선택 캐릭터와 선택 로어는 `IN` 조회에 `order_by`가 없다 (`backend/app/routers/ai_panel.py:244-258`). DB가 반환하는 순서가 요청 순서인지 id 순서인지 계약이 없다.

길이 예산도 일부만 있다. 복선 content는 400자로 자른다 (`backend/app/routers/ai_panel.py:282-287`). 권 개요 필드는 400자, 다음 회차 방향은 600자로 자른다 (`backend/app/routers/ai_panel.py:212-241`). 하지만 현재 회차 본문, 장면 본문, 선택 캐릭터, 선택 로어, 자동 로어에는 공통 예산 규칙이 없다 (`backend/app/routers/ai_panel.py:183-258`, `backend/app/routers/ai_panel.py:273`). canon은 모든 캐릭터/로어/복선을 별도 limit 없이 넣는다 (`backend/app/services/canon.py:46-82`).

### D4. 회차 브리프는 자동 로어 매칭 원본이 아니다

브리프는 컨텍스트 블록에는 들어간다 (`backend/app/routers/ai_panel.py:178-180`). 그러나 자동 로어 매칭의 `source_parts`에는 장면/회차 본문, 회차 memo, prompt_override만 들어간다 (`backend/app/routers/ai_panel.py:181-201`, `backend/app/routers/ai_panel.py:259-268`). 빈 회차에서 브리프에만 나온 고유명사/유물/장소는 자동 로어로 보강되지 않는다.

### D5. 관계 데이터가 생성과 canon에서 소비되지 않는다

관계는 별도 모델과 API로 존재한다 (`backend/app/models.py:231-244`, `backend/app/routers/characters.py:102-129`). 하지만 생성 컨텍스트는 `Character`만 조회하고 `Relationship`을 조회하지 않는다 (`backend/app/routers/ai_panel.py:244-254`). canon도 `Relationship`을 import하지 않고 캐릭터 카드만 넣는다 (`backend/app/services/canon.py:13`, `backend/app/services/canon.py:46-58`). 관계 라벨/노트가 인물 카드에 복사되어 있지 않으면 집필과 검증 모두 놓친다.

### D6. 복선은 “현재 회차 시점”과 “이번 화 회수 허용”을 구분하지 않는다

모델에는 `planted_chapter_id`, `resolved_chapter_id`, `audience_knows`가 있다 (`backend/app/models.py:121-143`, `backend/app/schemas.py:533-565`). 그러나 생성 자동 복선은 해당 project의 `status == "설치"`만 최신순으로 뽑는다 (`backend/app/routers/ai_panel.py:275-282`). canon은 `status in ("설치", "보류")` 전체를 unknown/known으로 나눈다 (`backend/app/services/canon.py:66-79`). 두 흐름 모두 대상 회차의 `sort_order` 기준으로 미래 설치/회수 복선을 걸러내지 않는다. 또한 “이번 화에서 회수해도 되는 복선”을 전달하는 입력 계약이 없다.

### D7. 단일/병렬 문체 적용이 다르다

단일 생성의 `style_profile`은 system 메시지에 붙는다 (`backend/app/routers/ai_panel.py:314-327`). 병렬 planner, worker, reviewer는 각각 별도 system 메시지를 쓰며 그 style addendum을 받지 않는다 (`backend/app/routers/ai_panel.py:642-649`, `backend/app/routers/ai_panel.py:712-715`, `backend/app/routers/ai_panel.py:778-780`). 같은 body를 보내도 단일과 병렬의 문체 조건이 달라질 수 있다.

### D8. canon run은 검사 시점의 원고 revision을 캡처하지 않는다

원고 저장/윤문/장면 조립은 이미 `expected_revision`과 snapshot 기반으로 보호된다 (`backend/app/services/manuscripts.py:55-123`, `backend/app/routers/projects.py:212-267`, `backend/app/routers/refine.py:41-132`, `backend/app/routers/scenes.py:99-122`). 그러나 canon run은 `chapter_id`, `model`, `issues_json`, `context_json`만 저장한다 (`backend/app/routers/quality.py:56-67`, `backend/app/models.py:168-177`). 회차가 바뀐 뒤 과거 canon 이력이 어느 revision의 본문을 검사했는지 알기 어렵다.

생성 결과도 서버에 저장되지 않는다. 프론트는 사용자가 명시 버튼을 눌러 CodeMirror view에 삽입/교체한다 (`frontend/src/components/panels/AiPanel.tsx:885-913`). 이후 저장은 기존 원고 자동저장 경로가 처리한다. 이 보존 계약은 유지해야 한다.

## 4. 기존 테스트가 보장하는 것과 빈칸

현재 테스트는 다음을 보장한다.

- 자동 로어 주입, 명시 로어 중복 제외, project_id만 있는 자동 로어 (`backend/tests/test_injection.py:115-180`).
- 빈 회차 memo 기반 로어 매칭과 outline 주입 (`backend/tests/test_ai_generate_stream.py:266-293`).
- 직전 회차 tail backend 동작 (`backend/tests/test_ai_generate_stream.py:309-333`).
- 브리프 블록과 Pydantic 검증 (`backend/tests/test_ai_generate_stream.py:465-544`).
- 단일 감수 패스와 마커 분리 (`backend/tests/test_ai_generate_stream.py:338-445`, `backend/tests/test_ai_generate_stream.py:547-589`).
- 병렬 worker 진행 이벤트, order 조립, review 순서, reviewer 설정, worker 실패 시 partial message 차단 (`backend/tests/test_ai_generate_stream.py:674-757`).
- 병렬 결과 검증의 empty/oversize/meta leak/order/title guard (`backend/tests/test_parallel_quality.py:23-54`).
- 복선 자동 주입과 canon 기본 성공/이력 (`backend/tests/test_foreshadows_canon.py:54-130`).
- 문체 프로파일 단일 생성 적용 (`backend/tests/test_godohwa_v2.py:121-150`).
- 장면 컨텍스트 주입 (`backend/tests/test_scenes_api.py:63-90`).

빈칸은 다음과 같다.

- 에디터에서 열린 AI 패널이 실제 body에 현재 `chapter_id`/`project_id`를 넣는지.
- 단일과 병렬이 같은 사용자 컨텍스트와 같은 문체 조건을 받는지.
- 잘못된 `project_id`, 타 작품 `chapter_id`/`scene_id`/`character_ids`/`lore_ids`가 섞였을 때 차단하는지.
- 브리프에만 있는 고유명사가 자동 로어 후보가 되는지.
- Relationship이 생성/canon 컨텍스트에 들어가는지.
- 복선의 설치/회수 회차가 대상 회차 시점과 맞는지.
- canon 이력이 특정 revision/hash와 연결되는지.
- 선택 캐릭터/로어 순서와 컨텍스트 예산이 deterministic한지.

## 5. 최소 아키텍처 접근안

### 접근 A — backend 공통 ContextAssembler 서비스

`GenerateContext`와 DB session을 받아 검증된 `ContextBundle`을 만드는 backend service seam을 둔다. 출력은 user blocks, system addenda, included metadata, rejected/missing reason, prompt length summary 정도로 제한한다. `/ai/generate`, `/ai/generate-parallel`, canon용 builder가 이 seam을 사용한다.

- 장점: 소속 검증, 순서, 중복 제거, 예산, 자동/명시 출처 표시를 한 곳에서 고정할 수 있다.
- 장점: 단일/병렬 equality 테스트가 쉬워진다.
- 단점: 프론트가 현재 회차를 body에 넣지 않는 문제는 별도 수정이 필요하다.
- 위험: 너무 크게 만들면 역사 기억 시스템으로 번질 수 있다. 이번 scope에서는 현재 존재하는 테이블과 요청 컨텍스트만 다룬다.

### 접근 B — frontend 요청 snapshot builder + backend guard

프론트에서 `editorStore(projectId, chapterId)`와 AI 패널 state를 합쳐 한 번의 request snapshot을 만든다. backend는 해당 snapshot의 ID 소속만 검증한다.

- 장점: 현재 UI의 `chapter_id:null` 문제를 가장 직접적으로 줄인다.
- 장점: 단일/병렬 body 생성 중복을 줄일 수 있다.
- 단점: backend 컨텍스트 조립 중복과 canon divergence는 남는다.
- 단점: API 직접 호출이나 stale 클라이언트는 backend guard 없이는 계속 위험하다.

### 접근 C — mode별 ContextPolicy를 얇게 둔다

공통 resolver 위에 `generation`, `parallel_worker`, `parallel_review`, `canon` 정책만 다르게 둔다. 예: generation은 회차 본문/브리프/outline을 넣고, canon은 검사 대상 본문과 검증용 canon blocks를 넣는다. 복선은 대상 회차 시점과 “이번 화 회수 허용”만 얇게 구분한다.

- 장점: canon과 generation의 차이를 숨기지 않고 명시한다.
- 장점: full historical memory 없이도 미래 복선 누출과 정당한 회수 차단을 줄인다.
- 단점: 정책 이름과 metadata 계약을 정해야 한다.

### 추천 seam

A를 중심으로 하고 B의 request snapshot fix를 같이 한다. 즉, backend에는 `services/ai_context.py` 같은 공통 조립 seam을 만들고, 프론트에는 “현재 편집기 context를 요청 직전에 확정한다”는 얇은 body builder를 둔다. C는 그 service 안의 작은 policy enum으로 제한한다.

추천 scope는 “현재 존재하는 Project/Chapter/Scene/Character/Relationship/LoreEntry/Foreshadow/VolumeNote/style_profile/brief를 안전하게 조립”하는 것이다. 회차별 역사 기억, 원고에서 상태 추출, 장기 메모리 자동 갱신은 이번 개발 단위 밖이다.

## 6. falsifiable 테스트 매트릭스

| 영역 | 테스트 입력 | 관찰할 결과 |
|---|---|---|
| 프론트 요청 snapshot | 에디터 `/projects/A/write`에서 1화 선택 후 AI 패널 열기, 현재 회차 포함 ON, 단일 생성 | `POST /api/v1/ai/generate` body에 A의 `chapter_id`와 project 기준이 들어간다. `chapter_id:null`이면 실패. |
| 프론트 병렬 equality | 같은 상태에서 병렬 생성 | `POST /api/v1/ai/generate-parallel` body의 context가 단일과 동일하다. 병렬 전용 필드만 다르다. |
| wrong project: chapter/project | `context.project_id=B`, `chapter_id=A chapter` | 422 또는 명시 오류. B의 style/lore/foreshadow가 A 회차와 섞이면 실패. |
| wrong project: scene/chapter | `scene_id=A scene`, `chapter_id=B chapter` | 차단. 두 블록이 한 prompt에 같이 들어가면 실패. |
| wrong project: characters/lore | A 회차 + B 캐릭터/B 로어 명시 | 차단 또는 제외+경고 metadata. 타 작품 캐릭터/로어가 prompt에 있으면 실패. |
| supplied vs auto lore | 명시 로어 X + 자동 로어 ON에서 X가 본문에 매칭 | 명시 블록 1개만 있고 자동 중복은 없다. 기존 테스트 유지. |
| brief as auto source | 빈 회차 + 브리프에만 로어 키워드 + auto_lore ON | 해당 로어가 자동 포함된다. 포함하지 않기로 결정한다면 UI/metadata에 “브리프는 자동 검색 원본 제외”가 명시되어야 한다. |
| deterministic order | character_ids/lore_ids를 역순으로 보내고 동점 자동 로어를 만든다 | 선택 항목과 자동 항목의 순서가 문서화된 규칙과 일치한다. 실행마다 바뀌면 실패. |
| budget | 긴 회차/장면/로어/캐릭터를 넣고 limit을 넘긴다 | context bundle이 정해진 예산에서 자르거나 오류/metadata를 낸다. silent unlimited prompt이면 실패. |
| single/parallel style equality | `style_profile=true`인 같은 body로 단일/병렬 호출 | 단일 system, parallel planner/worker/reviewer 또는 그들의 context metadata에 같은 style 조건이 관찰된다. |
| outline equality | `auto_outline=true`, 회차 memo/권 개요/다음 화 memo 있음 | 단일 user prompt, parallel planner, worker, reviewer에 같은 outline 블록이 관찰된다. |
| relationship inclusion | A 회차 + 두 캐릭터 관계 label/note | 생성과 canon context에 관계 블록이 들어간다. 단, 선택 캐릭터만 보낼지 프로젝트 관계 전체를 보낼지 정책대로 검증한다. |
| foreshadow as-of | 미래 회차에 planted된 설치 복선을 과거 회차 생성/canon에 사용 | 과거 회차 context에 미래 복선이 들어가지 않는다. |
| foreshadow allowed resolution | 이번 화에서 회수 허용된 복선과 미허용 복선을 함께 둔다 | 허용 복선은 “결론을 풀지 마라” 블록이 아니라 회수 허용 블록으로 들어가고, canon은 그 회수를 오류로 보지 않는다. |
| canon revision capture | canon 검사 뒤 회차를 수정하고 이력 조회 | run이 검사한 base revision/hash를 보여준다. 없다면 과거 이력 해석 테스트 실패. |
| preservation invariant | 생성 결과 수신만 하고 아무 반영 버튼도 누르지 않음 | 서버 원고 revision/content/snapshot이 변하지 않는다. |
| preservation invariant: insert | 생성 결과를 끼워넣은 뒤 기존 자동저장 경로 | 저장 요청은 현재 `expected_revision`을 사용한다. stale이면 기존 409 경로가 유지된다. |
| preservation invariant: refine/scene merge | 기존 보존 테스트 | `expected_revision`, snapshot, stale accept 차단 테스트가 계속 통과해야 한다. |

## 7. 권장 다음 개발 범위

1. AI 요청 snapshot을 정확히 만든다. 에디터 현재 `(project_id, chapter_id)`와 AI 패널 context가 요청 직전에 일치해야 한다.
2. backend 공통 ContextAssembler seam을 만든다. 같은 seam에서 소속 검증, deterministic ordering, 예산, 중복 제거, metadata를 처리한다.
3. 단일/병렬/canon이 같은 resolver를 쓰되 mode별 policy만 다르게 둔다.
4. Relationship 포함과 복선 as-of/회수 허용은 이 seam 안에서 최소 정책으로 추가한다.
5. 기존 원고 보존 계약은 변경하지 않는다. 생성 결과는 계속 자동 반영하지 않고, 반영 뒤 저장은 기존 `expected_revision` 경로를 사용한다.

## 8. 남은 질문

소스만으로 해결되지 않는 질문은 정책 선택뿐이다.

1. 선택 캐릭터가 있을 때 관계는 “선택 캐릭터와 연결된 관계만” 넣을지, “현재 회차/프로젝트의 주요 관계 전체”를 넣을지 정해야 한다.
2. 브리프 고유명사를 자동 로어 검색 원본에 포함할지 정해야 한다. 현재 코드 구조상 포함하는 편이 안전해 보인다.
3. 복선 “이번 화 회수 허용”을 브리프에 넣을지, 별도 `context.allowed_foreshadow_ids`로 둘지 정해야 한다.
