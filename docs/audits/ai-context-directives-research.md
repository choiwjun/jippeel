# AI 집필 맥락 지침 정리 — read-only research

- 범위: `docs/audits/소설집필_관리_감사.md` §8의 우선순위 2(공통 AI 맥락 구성·집필 지침 정합성)를 위한 요구사항/도메인 조사.
- 이해한 작업: 상세 설계나 구현이 아니라, 현재 단일/병렬 생성·감수·canon·quality·프론트 입력을 정적으로 읽고, **관계 맥락 전달, 일반 연재화/권말/최종화 구분, 작가 승인 payoff/reveal 예외**에 필요한 최소 계약을 제안한다.
- 하지 않은 것: 소스·테스트·스펙·HANDOFF·브랜치·커밋 변경 없음. 프로젝트 import, 테스트, DB, LLM, 실행 중 서비스 호출 없음.

## 1. 기준 문서에서 요구하는 다음 단계

`소설집필_관리_감사.md` §8은 이번 단계가 “AI 기능 추가”가 아니라 시작부터 완결까지 작가를 돕는 능력 재평가라고 둔다. 특히 회차 집필은 브리프와 장면 계약이 있지만 영속 회차 목표가 아니고, 장기 연재는 현재 설정과 해당 회차 당시 사실이 섞이며, 완결은 결말·인물 변화·핵심 갈등·복선 회수 완료 상태를 연결하지 못한다고 정리한다. `docs/audits/소설집필_관리_감사.md:108-125`

같은 문서는 우선 수정 후보를 세 가지로 좁힌다.

1. 일반 연재화/권말/최종화 목적 구분. `docs/audits/소설집필_관리_감사.md:130-138`
2. 이번 화에서 승인한 복선 회수/공개를 생성과 검사에 함께 전달. `docs/audits/소설집필_관리_감사.md:134-136`
3. 관계 관리 화면의 내용을 실제 집필 맥락으로 연결. `docs/audits/소설집필_관리_감사.md:136-138`

완료 판정도 “단일/병렬 요청의 회차·문체·기획·관계·설정이 일치”하고, “미래 계획과 현재 사실, 일반 연재화/최종화, 이번 화의 허용된 복선 회수”를 구분하는 것이다. `docs/audits/소설집필_관리_감사.md:190-200`

원고 보존 단계의 교훈은 이번 범위의 가드다. 비동기 작업은 소유권과 입력 순서로 완료해야 하며, 자동 응답으로 현재 편집 내용을 초기화하면 안 된다. `docs/audits/preservation-lessons.md:5-9` 실제 경계 증거가 필요하고, 세션 캐시나 mock만으로 보존을 주장하면 안 된다. `docs/audits/preservation-lessons.md:17-21` 또한 승인되지 않은 서사 기억·기획·완결 기능은 별도 설계와 승인 후 진행해야 한다. `docs/audits/preservation-lessons.md:23-24`

## 2. 현재 단일 생성 경로

### 2.1 요청 스키마와 기본값

`GenerateContext`는 `chapter_id`, `character_ids`, `lore_ids`, `auto_lore`, `project_id`, `previous_chapter`, `auto_outline`, `scene_id`, `auto_foreshadow`, `style_profile`, `brief`를 가진다. 백엔드 기본값은 대부분 안전하게 `False`/`None`이다. `auto_lore=False`, `previous_chapter=False`, `auto_outline=False`, `auto_foreshadow=False`, `style_profile=False`가 기본이다. `backend/app/schemas.py:350-372`

프론트 `aiPanelStore` 기본값은 다르다. UI 상태는 `includeChapter=false`, `includeCharacters=false`, `includeLore=false`지만 `autoLore=true`, `autoOutline=true`, `autoForeshadow=true`, `styleProfile=false`다. `frontend/src/stores/aiPanelStore.ts:183-196` 따라서 UI가 보내는 body는 백엔드 기본과 다르다. 단, `chapter_id` 또는 `project_id`가 없으면 백엔드 자동 주입은 실제로 실행되지 않는다. `backend/app/routers/ai_panel.py:181-183`, `backend/app/routers/ai_panel.py:259-275`

### 2.2 컨텍스트 조립

브리프가 있으면 가장 앞에 들어간다. `backend/app/routers/ai_panel.py:177-180` 회차 본문, 회차 memo, 권 개요, 직전 회차 끝부분, 다음 회차 예고는 `chapter_id`가 있을 때만 조립된다. `backend/app/routers/ai_panel.py:191-242` 선택 캐릭터는 `Character.id.in_(ctx.character_ids)`로만 조회하고, 선택 로어도 `LoreEntry.id.in_(ctx.lore_ids)`로만 조회한다. 프로젝트 소속 검사는 없다. `backend/app/routers/ai_panel.py:244-258`

관계(`Relationship`)는 이 경로에서 import하거나 조회하지 않는다. 라우터 import 목록에 `Relationship`이 없고, 캐릭터 카드 필드는 role/appearance/personality/speech_style/background뿐이다. `backend/app/routers/ai_panel.py:17-30`, `backend/app/routers/ai_panel.py:244-254`

### 2.3 생성/감수 프롬프트

단일 생성 시스템 프롬프트는 브리프 우선, 장면 유형 리듬, 전개, 문체, 금지를 포함한다. `backend/app/routers/ai_panel.py:35-60` 문제는 일반 회차 전제의 지침이 조건 없이 들어간다는 점이다.

- “브리프에 다음 화 훅이 있으면 … 미해결 질문이나 행동으로 화를 끝낸다. 훅이 없어도 장면의 긴장이 완전히 풀리기 전에 끝낸다.” `backend/app/routers/ai_panel.py:47-50`
- “갈등을 다 풀지 마라. 해결은 다음 화에 남긴다.” `backend/app/routers/ai_panel.py:51-55`

단일 감수 프롬프트도 “다음 화 클릭을 유도하는 마무리”를 감수 관점에 포함한다. `backend/app/routers/ai_panel.py:63-78` 감수 입력은 생성 user 메시지 전체와 초안 원고를 합쳐 만든다. `backend/app/routers/ai_panel.py:570-581` 따라서 생성 user 메시지에 새 domain directive가 들어가면 단일 감수도 볼 수 있다. 단, 시스템 프롬프트의 일반 회차 지침이 그대로 남으면 최종화/승인 회수와 충돌할 수 있다.

## 3. 현재 회차 브리프와 장면 계약

### 3.1 EpisodeBrief

`EpisodeBrief`는 요청 단위의 선택 계약이다. DB에 저장되지 않는다. `backend/app/schemas.py:332-338` 현재 필수 필드는 `emotion_goal`, `core_events`, `character_choices`, `cost`, `prohibitions`, `next_hook`이다. `next_hook`은 빈 값일 수 없다. `backend/app/schemas.py:340-346`

프론트도 같은 제약을 강제한다. `parseEpisodeBrief`는 `next_hook`이 없으면 `incomplete`로 보고 브리프를 보내지 않는다. `frontend/src/components/panels/AiPanel.tsx:36-50` UI 라벨도 “다음 화 훅”만 제공한다. `frontend/src/components/panels/AiPanel.tsx:793-801`

결론: 브리프가 있는 최종화는 현재 스키마상 “다음 화 훅”을 반드시 적어야 한다. 브리프를 아예 빼면 최종화 목표·선택·대가 계약도 같이 사라진다. 이것이 최소 계약 변경이 필요한 핵심이다.

### 3.2 ParallelScenePlan

병렬 장면 계약은 `closing_hook`을 필수로 요구한다. `backend/app/schemas.py:395-408` planner 시스템도 모든 장면에 `closing_hook`을 포함하라고 한다. `backend/app/routers/ai_panel.py:642-649` worker 프롬프트도 “closing_hook으로 끝내되”라고 한다. `backend/app/routers/ai_panel.py:701-710` 병렬 감수도 `closing_hook` 달성을 반드시 확인한다. `backend/app/routers/ai_panel.py:778-785`

결론: 병렬 경로는 최종 장면까지 hook/미해결 전제로 설계되어 있다. 권말은 쓸 수 있어도, 시리즈 최종화의 “핵심 갈등 해소, 최종 선택, 여운”과 정면 충돌할 수 있다.

## 4. 현재 복선/payoff 제약

### 4.1 생성

자동 복선 주입은 프로젝트의 `status == "설치"`만 최신순으로 가져온다. `backend/app/routers/ai_panel.py:275-282` 각 블록에는 “아직 회수 전”이고 “결론을 미리 풀지 마라”라는 지시가 붙는다. `backend/app/routers/ai_panel.py:283-288`

현재 요청에는 “이번 화에서 이 복선을 회수/공개해도 된다”는 ID 목록이 없다. 따라서 작가가 이번 화 회수를 승인해도, 같은 복선은 생성 프롬프트에서 계속 미회수/비공개로 취급된다.

### 4.2 canon 검사

canon 시스템 프롬프트는 “독자가 아직 모른다고 표시된 사실”과 “미회수 복선 결론 선공개”를 검사한다. `backend/app/services/canon.py:17-27` canon 컨텍스트는 현재 프로젝트의 `status in ("설치", "보류")` 복선만 가져온다. `backend/app/services/canon.py:66-79` `audience_knows=false`는 “아직 회수 전이므로 본문이 미리 결론을 풀어버리면 지적”이고, `audience_knows=true`는 “이미 알게 된 사실”로 분리한다. `backend/app/services/canon.py:70-79`

현재 `CanonCheckRequest`는 `chapter_id` 하나만 받는다. `backend/app/schemas.py:593-595` 승인된 payoff/reveal 예외나 회차 목적을 전달할 자리가 없다. 따라서 정당한 회수도 canon이 모순 후보로 낼 수 있다.

### 4.3 planned / permitted / completed 구분

현재 데이터 모델에는 `status`, `audience_knows`, `planted_chapter_id`, `resolved_chapter_id`가 있다. `backend/app/models.py:121-143` 그러나 생성은 `planted_chapter_id`/`resolved_chapter_id`를 보지 않고 현재 `status == "설치"`만 본다. `backend/app/routers/ai_panel.py:275-282` canon도 회차 시점을 비교하지 않고 현재 `status in ("설치", "보류")`만 본다. `backend/app/services/canon.py:66-79`

따라서 최소 도메인 구분은 다음 셋이어야 한다.

- **planned**: 미래에 공개/회수할 계획. 생성자가 구조 참고를 할 수는 있어도, 현재 회차의 사실이나 인물/독자 지식으로 쓰면 안 된다.
- **permitted this episode**: 이번 요청에서 작가가 공개/회수를 승인한 ID. 생성과 canon 모두 예외로 처리한다.
- **completed**: 이미 원고 안에서 공개/회수된 사실. 반복 공개·모순 검사의 기준으로 쓰되, “미회수” 금지 블록에는 넣지 않는다.

현재 코드에는 이 세 상태를 요청 단위로 동시에 표현하는 계약이 없다.

주의: `ForeshadowCreate` 스키마에는 `audience_knows`가 있지만, create 라우터는 row 생성 시 이 값을 넣지 않는다. `backend/app/schemas.py:533-540`, `backend/app/routers/foreshadows.py:222-235` 이미 있는 테스트는 create 기본값 false와 patch true를 확인할 뿐, create true 보존은 확인하지 않는다. `backend/tests/test_godohwa_v2.py:89-117`

## 5. 현재 관계 맥락

관계 데이터는 존재한다. `Relationship`은 `from_character_id`, `to_character_id`, `label`, `note`를 가진다. `backend/app/models.py:231-245` 생성 API도 두 캐릭터가 같은 프로젝트 소속인지 검사한다. `backend/app/routers/characters.py:102-119`

하지만 집필 생성과 canon은 관계를 읽지 않는다.

- 단일/병렬 생성의 공통 컨텍스트 조립은 캐릭터 카드만 넣는다. `backend/app/routers/ai_panel.py:244-254`
- canon은 프로젝트 전체 캐릭터 카드만 넣고 관계를 넣지 않는다. `backend/app/services/canon.py:46-58`
- 프론트 관계 UI는 라벨만 입력한다. note 입력은 없다. `frontend/src/pages/CharactersPage.tsx:319-410`

결론: “관계가 있는 캐릭터를 선택했다”는 UI 상태만으로 관계 긴장·변화를 생성/감수/canon이 알 수 없다. 이번 단계는 새 관계 대시보드가 아니라, 기존 관계 row를 언제/어떻게 포함할지 계약하는 것이 최소 범위다.

## 6. 현재 프론트 입력과 caller 추적

### 6.1 AiPanel → 단일/병렬 생성

프론트 `generate()`는 하나의 body를 만든 뒤, `generationMode === 'parallel'`이면 `streamParallelGenerate`, 아니면 `streamGenerate`를 호출한다. `frontend/src/components/panels/AiPanel.tsx:180-246` 실제 URL은 각각 `/api/v1/ai/generate`, `/api/v1/ai/generate-parallel`이다. `frontend/src/lib/aiStream.ts:239-245`

현재 body는 `chapter_id`, `character_ids`, `lore_ids`, `auto_lore`, `auto_lore_semantic`, `auto_outline`, `auto_foreshadow`, `scene_id`, `style_profile`, 그리고 조건부 `brief`만 보낸다. `frontend/src/components/panels/AiPanel.tsx:207-222` `previous_chapter`, `project_id`, 관계 포함 여부, 회차 목적, 승인 payoff/reveal ID는 보내지 않는다.

중요한 현재 상태: 편집기의 `chapterId`와 AI 패널의 `contextSelection.chapterId`는 별도 store다. `EditorPage`는 editor store를 갱신한다. `frontend/src/pages/EditorPage.tsx:39-73` AI 패널 body는 AI store의 `contextSelection`만 읽는다. `frontend/src/components/panels/AiPanel.tsx:198-222` `ContextSection`은 editor store의 `chapterId`를 UI 활성화에 쓰지만, body에 들어갈 `ctx.chapterId`를 자동 세팅하지 않는다. `frontend/src/components/panels/AiPanel.tsx:595-607`, `frontend/src/components/panels/AiPanel.tsx:649-654` 따라서 현재 코드상 “현재 회차 포함”이 실제 `chapter_id` 전송으로 이어진다고 단정하면 안 된다.

### 6.2 병렬 경로의 공통성 누락

`generate_parallel`은 먼저 `GenerateRequest`를 만들어 `_build_messages`를 호출한다. `backend/app/routers/ai_panel.py:617-629` 하지만 planner/worker/reviewer는 `base_messages[-1]['content']`만 재사용하고, `_build_messages`가 만든 system prompt는 버린다. `backend/app/routers/ai_panel.py:650-657`, `backend/app/routers/ai_panel.py:701-715`, `backend/app/routers/ai_panel.py:778-785`

이 때문에 `style_profile`처럼 system prompt에만 붙는 맥락은 단일 생성에는 들어가지만 병렬 worker에는 들어가지 않는다. `backend/app/routers/ai_panel.py:312-329`, `backend/app/routers/ai_panel.py:712-715` 새 회차 목적/payoff 지침도 system prompt에만 넣으면 병렬과 단일이 불일치한다. 이번 단계는 “공통 directive block”이 모든 단계에 들어가게 하는 계약이 필요하다.

### 6.3 CanonDialog / QualityDialog

`CanonDialog`는 `chapter_id`만 전송한다. `frontend/src/components/editor/CanonDialog.tsx:47-63` 화면은 context count를 보여주지만 사용자가 회차 목적, 관계 포함, 승인 payoff를 지정할 수 없다. `frontend/src/components/editor/CanonDialog.tsx:65-101`

`QualityDialog`는 `/chapters/{id}/quality`를 열 때 호출하고, 로컬 규칙 기반 점수/제안을 보여준다. `frontend/src/components/editor/QualityDialog.tsx:86-112` 품질 규칙에는 hook 여부가 들어간다. `frontend/src/components/editor/QualityDialog.tsx:165-171`

`EditorPage`는 회차 상태를 `완료`로 바꿀 때 `/quality?record=false`를 호출하고 hook이 없으면 경고한다. `frontend/src/pages/EditorPage.tsx:197-215` 현재 타입은 top-level `hook_present`를 기대하지만 실제 `ChapterQualityOut`은 `metrics.hook_present` 안에 둔다. `backend/app/schemas.py:617-623`, `backend/app/services/quality.py:138-146` 따라서 현재 구현은 최종화 여부와 무관하게 hook 경고를 낼 위험이 있고, 응답 shape도 맞지 않는다.

### 6.4 기타 caller

`scripts/write_volume1.py`는 `/ai/generate`를 직접 호출하며, 각 회차 prompt에 “마지막 문장은 다음 화로 넘어가는 훅”을 하드코딩한다. `scripts/write_volume1.py:70-88` 이 스크립트는 배치 초안 생성 도구라 이번 범위의 주 UI는 아니지만, 새 스키마 기본값은 이 caller를 깨뜨리지 않아야 한다.

`backend/scripts/evaluate_parallel.py`도 `/ai/generate-parallel`에 최소 payload를 보낸다. `backend/scripts/evaluate_parallel.py:92-110` 새 필드는 모두 optional이어야 한다.

## 7. 기존 테스트 커버리지와 빈 곳

있는 커버리지:

- 브리프 전송 시 user 메시지에 계약 블록이 들어가고, 미전송 시 빠진다. `backend/tests/test_ai_generate_stream.py:448-497`
- 브리프 빈 값/개수/길이 제한은 422다. `backend/tests/test_ai_generate_stream.py:500-545`
- 직전 회차 끝부분 주입은 API 플래그로 검증한다. `backend/tests/test_ai_generate_stream.py:309-335`
- auto outline은 현재 memo와 다음 회차 memo 주입 및 SSE 공개를 검증한다. `backend/tests/test_outline_injection.py:40-85`
- 권 개요 주입은 `auto_outline`에서 검증한다. `backend/tests/test_godohwa_v2.py:54-86`
- 미회수 복선 자동 주입과 회수 상태 제외, SSE 공개를 검증한다. `backend/tests/test_foreshadows_canon.py:54-91`
- canon 성공, 이력 저장, audience_known count를 검증한다. `backend/tests/test_foreshadows_canon.py:94-132`, `backend/tests/test_godohwa_v2.py:89-117`
- 병렬 orchestration은 worker 순서, review 시작 시점, preset 보존, reviewer endpoint/model, worker 실패를 검증한다. `backend/tests/test_ai_generate_stream.py:597-757`
- 병렬 scene contract 검증과 meta marker leak 방지는 있다. `backend/tests/test_parallel_quality.py:1-54`, `backend/tests/test_parallel_writer.py:26-80`
- 규칙 기반 quality hook metric과 제안은 있다. `backend/tests/test_quality.py:16-60`
- 프론트 E2E는 AI 결과가 자동 삽입되지 않고, 명시 클릭 후 반영되는 것을 검증한다. `frontend/e2e/app-flow.spec.ts:190-250`
- 병렬 프론트 E2E는 병렬 요청이 가고 draft/review가 표시되며 자동 저장되지 않는 것을 검증한다. `frontend/e2e/parallel-writing.spec.ts:34-79`

없는 커버리지:

- 일반 연재화/권말/최종화별 system/user/review/canon/quality 지침 차이.
- `next_hook` 없이도 최종화 브리프가 유효한지.
- 병렬 최종 장면에서 `closing_hook` 대신 해소/여운 계약을 쓰는지.
- 승인된 payoff/reveal ID가 생성과 canon 양쪽에서 예외로 처리되는지.
- 미승인 복선은 여전히 “결론을 미리 풀지 마라”로 남는지.
- 관계 row가 선택 캐릭터/프로젝트 기준으로 생성·병렬·canon에 포함되는지.
- 다른 프로젝트의 character/lore/scene/foreshadow/payoff/relationship ID가 거부되는지.
- 프론트 AI 패널이 현재 editor chapter를 실제 생성 body에 넣는지.
- CanonDialog가 생성과 같은 domain directive를 보낼 수 있는지.
- 최종화에서 quality hook penalty/완료 경고가 비활성 또는 다른 기준으로 바뀌는지.
- generate/canon/quality가 story state를 자동 변경하지 않는지.

## 8. 추천 최소 도메인/request 계약

상세 설계가 아니므로 필드명은 제안이다. 핵심은 “문구”보다 **공통 계약**이다.

### 8.1 Episode purpose

요청 단위에 optional enum을 추가한다.

```text
episode_purpose: "serial" | "volume_end" | "series_finale"
```

보수 기본값: `serial`.

의미:

- `serial`: 현재 동작과 가장 가깝다. 다음 화 훅, 미해결 질문 유지 가능.
- `volume_end`: 권의 핵심 질문/감정 payoff는 해소한다. 단, 다음 권으로 넘길 큰 질문은 허용한다.
- `series_finale`: 핵심 갈등·인물 최종 선택·승인된 회수는 해소한다. “다음 화 클릭”과 “갈등을 다 풀지 마라”는 금지 또는 비적용.

`EpisodeBrief.next_hook`은 `serial`에서만 필수로 두고, `volume_end`/`series_finale`에서는 `ending_intent` 또는 `resolution_note` 같은 필드로 대체해야 한다. 병렬 `closing_hook`도 목적에 따라 `closing_intent`로 일반화하는 것이 최소 충돌 제거다.

### 8.2 Approved payoff/reveal IDs

요청 단위에 optional ID list를 둔다.

```text
approved_payoff_foreshadow_ids: number[] = []
approved_reveal_foreshadow_ids: number[] = []  # payoff와 공개만 분리해야 한다면
```

보수 기본값: 빈 배열.

규칙:

- ID가 없으면 현재 미회수 복선 금지 지침을 유지한다.
- ID가 있으면 생성 컨텍스트에서 해당 복선을 “이번 화에서 회수/공개 허용” 블록으로 분리한다.
- canon은 해당 ID가 본문에서 드러나도 “미리 결론을 풀었다”로 지적하지 않는다.
- 검사 후 `Foreshadow.status`나 `audience_knows`를 자동 변경하지 않는다. 변경은 별도 사용자 승인 액션이어야 한다.

초기에는 Foreshadow ID만 다루는 것이 보수적이다. 범용 reveal registry나 전체 작품 기억은 이번 범위를 넘는다.

### 8.3 Relationship context inclusion

요청 단위에 optional relationship 포함 계약을 둔다.

```text
include_relationships: boolean = false
relationship_ids?: number[]
```

보수 기본값: `false`. 기존 API caller의 출력 변화를 최소화한다.

허용 방식:

- `relationship_ids`가 있으면 그 ID만 포함한다.
- 없고 `include_relationships=true`이면 선택 캐릭터 사이의 관계, 또는 현재 회차/프로젝트에서 선택한 캐릭터와 직접 연결된 관계만 포함한다.
- canon은 `chapter_id`의 프로젝트 전체 관계를 검사 대상으로 포함할지, 사용자가 선택한 관계만 볼지 결정이 필요하다. 보수 기본은 `include_relationships=false`, UI에서 명시 켜기다.

### 8.4 Planned / permitted / completed fact labels

프롬프트에는 같은 복선/사실을 다음 라벨로 분리해 넣어야 한다.

```text
[계획된 미래 사실 — 현재 사실/독자 지식으로 쓰지 말 것]
[이번 화 공개/회수 허용 — 작가 승인 ID]
[이미 공개/회수된 사실 — 반복 공개/모순 기준]
[아직 미공개/미회수 — 결론 선공개 금지]
```

이 구분은 단일 생성, 병렬 planner, 병렬 worker, 병렬 reviewer, 단일 review, canon에 같은 의미로 들어가야 한다. system prompt에만 넣으면 병렬이 누락될 수 있으므로, 공통 user directive block 또는 모든 phase의 system prompt에 주입하는 규칙이 필요하다.

## 9. 권한/소유권 검증

추천 authority 기준은 다음과 같다.

1. `chapter_id`가 있으면 그 회차의 `project_id`가 요청의 기준이다.
2. `chapter_id`가 없고 `scene_id`가 있으면 scene→chapter→project가 기준이다.
3. 둘 다 없으면 자동 주입/관계/payoff에는 `project_id`를 요구한다.
4. `chapter_id`와 `project_id`가 같이 있으면 반드시 일치해야 한다.
5. `scene_id`는 `chapter_id`가 있으면 같은 회차여야 하고, 없으면 같은 프로젝트여야 한다.
6. `character_ids`, `lore_ids`, `relationship_ids`, `approved_*_foreshadow_ids`는 모두 기준 프로젝트 소속이어야 한다.
7. 관계는 직접 `project_id`가 없으므로 양끝 캐릭터의 프로젝트로 검증한다.
8. 위반은 조용히 제외하지 말고 422로 반환한다. 그래야 사용자가 “맥락이 들어간 줄 알았는데 빠짐”을 알 수 있다.

현재 생성 경로는 선택 캐릭터/로어에 소속 필터가 없다. `backend/app/routers/ai_panel.py:244-258` scene도 `scene_id` 조회 뒤 요청 chapter/project와 일치하는지 확인하지 않는다. `backend/app/routers/ai_panel.py:183-190` foreshadow 라우터의 chapter ref 검증도 존재 여부만 보고 같은 프로젝트인지 확인하지 않는다. `backend/app/routers/foreshadows.py:201-205`

## 10. 자동 persisted state 변경 원칙

추천: **서사 상태의 자동 변경 금지는 유지한다.**

허용:

- 사용량 기록 같은 telemetry. 현재 generate/review/parallel/canon은 usage를 기록한다. `backend/app/routers/ai_panel.py:564-568`, `backend/app/routers/quality.py:61-63`
- canon/quality 실행 이력 같은 감사 로그. canon은 `CanonRun`을 저장한다. `backend/app/routers/quality.py:56-67` quality는 `record=true` 기본일 때 본문 hash가 바뀌면 `QualityCheck`를 저장한다. `backend/app/routers/quality.py:80-105`

금지:

- 생성/감수/canon 결과로 원고 본문 자동 교체.
- approved payoff로 전달했다는 이유만으로 `Foreshadow.status` 또는 `audience_knows` 자동 변경.
- LLM이 추출한 관계/사실/기억 후보를 승인 없이 정본으로 저장.

근거: 현 프론트는 AI 결과 자동 삽입 금지를 명시하고 버튼 클릭만 허용한다. `frontend/src/components/panels/AiPanel.tsx:320-325`, `frontend/src/components/panels/AiPanel.tsx:885-913` 보존 교훈도 승인되지 않은 서사 기억·기획·완결 기능을 별도 설계 후 진행하라고 둔다. `docs/audits/preservation-lessons.md:23-24`

## 11. UI/API 범위 옵션

### 옵션 A — Backend/API 계약만 추가

- 내용: `GenerateContext`, `CanonCheckRequest`, 병렬 내부 prompt에 optional directive 필드 추가. 프론트는 아직 노출하지 않거나 dev/API caller만 사용.
- 장점: 기존 UI 변경 적음. 기존 caller는 default로 유지.
- 단점: 사용자가 최종화/승인 회수를 실제 화면에서 지정하기 어렵다. CanonDialog와 생성 지침 불일치가 남을 수 있다.
- 적합도: 낮음. 이번 사용자의 “관계/최종화/payoff” 요구를 제품 표면에서 검증하기 부족하다.

### 옵션 B — AiPanel/CanonDialog에 최소 컨트롤 추가 (추천)

- 내용: 시각 redesign 없이 기존 섹션에 작은 입력만 추가.
  - 회차 목적 select: 일반 연재화 / 권말 / 최종화.
  - 관계 포함 checkbox.
  - 승인 회수/공개 복선 선택: 기존 `foreshadows/match` 배지 또는 프로젝트 복선 목록을 재사용해 ID list 전송.
  - CanonDialog에도 같은 목적/승인 ID/관계 포함을 보낼 수 있게 한다.
- 장점: 단일·병렬·canon이 같은 request contract를 받는다. 테스트가 명확하다. 새 의존성 없음.
- 단점: 최종화 판단과 payoff ID 선택은 여전히 사용자가 해야 한다.
- 보수 기본값: `serial`, `include_relationships=false`, approved ID 빈 배열.

### 옵션 C — 회차별 directive 저장

- 내용: 회차마다 purpose, approved payoff/reveal, 관계 포함 설정을 저장하고 재진입 시 복원한다.
- 장점: 장편 재개성이 좋아진다.
- 단점: 영속 모델/마이그레이션/복구/권한/상태 전이 설계가 필요하다. 이번 “상세 설계 미승인” 범위를 넘기 쉽다.
- 적합도: 후속 단계. 이번에는 request-only + 테스트로 먼저 정합성을 검증하는 것이 안전하다.

## 12. 사용자 결정이 필요한 점과 보수 기본값

필요 결정:

1. 권말의 의미: 권 내부 갈등은 풀고 다음 권 hook은 남길지, 권말도 최종화처럼 닫을지.
2. 관계 포함 기본값: 캐릭터를 선택하면 관계도 자동 포함할지, 별도 checkbox로만 포함할지.
3. 승인 ID 범위: 이번 단계에서 Foreshadow ID만 다룰지, 별도 reveal/payoff registry를 만들지.
4. CanonDialog가 생성 때 쓴 directive를 자동 이어받을지, 검사 실행 시 다시 지정할지.
5. quality hook 지표를 최종화에서 끌지, “여운/해소” 체크로 대체할지.

제안 기본값:

- `episode_purpose='serial'`.
- 자동 추론으로 최종화 판단 금지. “다음 회차가 없음”은 미작성일 수 있다.
- `include_relationships=false`로 시작하되, UI에는 “관계 포함”을 명시 제공.
- approved payoff/reveal ID는 빈 배열. 사용자가 고른 ID만 예외.
- 서사 상태 자동 저장 금지. 로그/usage/history는 유지 가능하되 story state와 구분.
- 기존 caller를 깨지 않도록 새 필드는 모두 optional.

## 13. 추천 acceptance test cases

문학적 품질이 아니라 prompt/요청 정합성을 검증한다.

1. **기존 caller 보존**: 새 필드 없는 `/ai/generate`와 `/ai/generate-parallel` payload가 기존처럼 200/SSE를 반환하고, 브리프 없는 요청의 user prompt label도 기존과 동일하다.
2. **serial 기본**: `episode_purpose` 생략 또는 `serial`이면 next hook 지침이 유지되고, 브리프 `next_hook`은 기존처럼 유효성 검사를 받는다.
3. **series_finale 단일**: `episode_purpose='series_finale'`이면 system/user prompt에 “다음 화 클릭”, “갈등을 다 풀지 마라”, “해결은 다음 화”가 없거나 비적용으로 명시되고, `next_hook` 없이도 finale용 ending/resolution 필드가 주입된다.
4. **volume_end 단일**: `volume_end`는 권 내부 payoff/해소 지침과 다음 권 여지 지침을 모두 포함하고, serial/finale 문구와 구분된다.
5. **parallel consistency**: 같은 request로 planner, worker, parallel reviewer가 동일 `episode_purpose`, approved payoff IDs, relationship block, style profile을 본다. system-only 누락이 없어야 한다.
6. **approved payoff split**: 복선 A/B가 모두 `설치`일 때 A만 approved list에 있으면 A 블록은 “이번 화 회수/공개 허용”, B 블록은 “결론 선공개 금지”로 들어간다.
7. **canon approved exception**: 같은 A 승인 request로 canon을 실행하면 A 공개는 미회수 위반 지시 대상에서 빠지고, B 공개는 여전히 검사 대상이다.
8. **relationship inclusion**: `include_relationships=true`이면 선택 캐릭터 사이 관계 label/note가 단일, 병렬, canon prompt에 포함된다. false이면 포함되지 않는다.
9. **ownership rejection**: 다른 프로젝트의 character/lore/scene/foreshadow/relationship ID를 보내면 422이고, 조용히 제외하지 않는다.
10. **frontend current chapter body**: 편집기에서 AI 패널을 열고 “현재 회차”를 켠 단일/병렬 요청 모두 실제 body에 현재 `chapter_id`를 보낸다.
11. **CanonDialog directives**: CanonDialog 실행 body에 `chapter_id`뿐 아니라 purpose/approved IDs/include relationships가 들어간다.
12. **finale quality**: `series_finale`에서는 hook absence가 감점/완료 경고 기준이 아니며, serial에서는 기존 hook 제안이 유지된다.
13. **no story auto-persist**: generate/review/canon/quality 뒤 원고, Foreshadow status/audience_knows, Relationship rows는 변하지 않는다. 단, usage/canon run/quality history 같은 로그성 기록은 명시 범위로 분리 검증한다.

## 14. 최소 추천 범위

추천은 옵션 B의 request-only 최소판이다.

- API: optional `episode_purpose`, `approved_payoff_foreshadow_ids`, optional `approved_reveal_foreshadow_ids` 또는 payoff 하나로 통합, `include_relationships`, optional `relationship_ids`를 generation과 canon request에 추가.
- Prompt: 단일 생성, 단일 review, 병렬 planner, 병렬 worker, 병렬 review, canon에 같은 directive block을 전달.
- Frontend: AiPanel과 CanonDialog에 기존 스타일의 작은 controls만 추가. visual redesign 없음.
- Validation: 모든 ID는 request 기준 프로젝트 소속인지 검증. 위반 422.
- Tests: 위 acceptance tests 중 prompt/body/validation 중심을 추가. LLM 품질 평가는 하지 않음.
- Persist: story state 자동 변경 금지 유지. approved ID는 요청 예외일 뿐 status 변경이 아님.

이 범위는 역사적 기억, 전체 기획/완결 dashboard, production deployment, 새 dependency를 포함하지 않는다.
