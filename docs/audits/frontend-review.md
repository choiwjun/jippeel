# 프런트엔드 집필·장편 관리 감사

## 범위와 검증 방법

현재 작업 트리의 에디터, AI 생성·감수·반영, 기획·장면 관리 흐름을 읽었다. 구현·실제 DB는 변경하지 않았다. HANDOFF의 과거 완료 표시는 근거로 쓰지 않았다.

- 부모가 현재 소스로 빌드한 `frontend/dist`를 읽기 전용 로컬 정적 서버에서 제공했다.
- 프로젝트에 설치된 Playwright/Chromium으로 실제 화면을 조작했다. 모든 `/api` 응답과 AI SSE는 메모리 fixture로 대체했다. 외부 요청은 차단했다. 실제 DB·유료 모델·외부 LLM 호출은 없다.
- 따라서 아래 브라우저 재현은 **프런트엔드의 표시·요청·생명주기 증거**다. 실제 백엔드 저장 성공이나 소설 품질 평가가 아니다. 백엔드 영향은 별도로 명시한 실제 라우터 코드로 연결했다.
- 재현 원본: `docs/audits/frontend-probe.cjs`, 결과: `docs/audits/frontend-probe-results.json`. 재현 서버: `docs/audits/frontend-static-server.cjs`.
- P0: 원고 손실·다른 작품 덮어쓰기. P1: 집필 맥락·반영 정확성. P2: 장편 관리의 작업량·회복 가능성.

## 강점

1. **작가의 명시적 반영을 기본으로 한다.** AI 초안/수정본은 버튼을 눌러야 편집기에 들어간다. 감수 의견 탭은 본문 반영을 막는다. `frontend/src/components/panels/AiPanel.tsx:885-913,924-927,978-985`.
2. **감수 결과를 비교해서 판단할 수 있다.** 윤문 diff, 진단 span, 변경률 경고·차단, 수락·거절이 있다. 차단 결과는 백엔드에서도 결과 텍스트가 없어 수락하지 못한다. `frontend/src/components/panels/RefineReport.tsx:146-160,174-205,259-267`; `backend/app/routers/refine.py:58-70,96-108`.
3. **장편 집필에 필요한 자료 모델은 마련되어 있다.** 권 개요·감정 곡선·고봉 노트·문체 프로파일, 장면, 캐릭터·로어·복선이 분리되어 있다. 권 개요와 회차 메모를 생성 문맥에 넣는 백엔드 경로도 있다. 단, 아래 문맥 연결 버그 때문에 UI에서 의도대로 쓰인다고 볼 수는 없다. `frontend/src/pages/PlanPage.tsx:27-30,69-107`; `backend/app/routers/ai_panel.py:198-218`.
4. **병렬 집필의 진행 단계를 노출한다.** planner/worker/review 단계와 완료 수를 표시하고 감수 오류를 초안 오류와 구분한다. 생성 결과의 문학적 우수성까지 검증된 것은 아니다. `frontend/src/components/panels/AiPanel.tsx:254-292,554-563`.
5. **기본 안전·반출 경로가 있다.** 미리보기는 HTML 비활성 Markdown 렌더링 뒤 DOMPurify를 적용한다. 회차/프로젝트 txt·md 내보내기도 있다. 다만 내보내기 최신성은 F2의 저장 캐시 문제를 먼저 고쳐야 한다. `frontend/src/components/editor/EditorPreview.tsx:6-9`; `frontend/src/pages/EditorPage.tsx:244-282`.

## 핵심 발견

### F1 · P0 · 확정 버그 — 빠른 회차 전환에서 미저장 원고가 사라진다

- **재현:** 101화에 `UNSAVED_A`를 입력하고 1.5초 전에 102화를 누른다. 이후 가상 시간을 2초 진행해도 저장 요청은 `[]`이고 서버 fixture는 `ORIGINAL_A`다.
- **원인:** 회차 버튼이 `setContext`를 부르면 먼저 전역 `saveState`를 `saved`로 바꾼다. 이전 EditorBody의 cleanup은 타이머를 지운 뒤 `dirty`일 때만 flush한다. 따라서 이전 회차 초안을 보내지 않는다. `frontend/src/components/layout/LeftSidebar.tsx:149-153`; `frontend/src/stores/editorStore.ts:41-44`; `frontend/src/pages/EditorPage.tsx:341-360`.
- **추가 위험(코드 확인):** 저장 중 새로 입력해도 `dirty`로 바꾸지 않고, cleanup은 `saving`/`error`도 보내지 않는다. 저장 요청 직렬화·버전 검사도 없어 늦은 응답이 최신 저장 표시를 덮을 수 있다. `EditorPage.tsx:305-335`; `backend/app/routers/projects.py:205-213`.
- **우선 수정:** 회차별 draft/revision/저장 큐를 두고 이전 회차의 마지막 텍스트를 확인한 뒤 전환한다. 전역 UI 상태를 저장 필요 여부의 유일한 근거로 쓰지 않는다. 실패한 초안은 로컬 복구본으로 보관한다.

### F2 · P0 · 확정 버그 — 저장 직후 미리보기·재편집이 옛 원고를 보여준다

- **재현:** `SAVED_NEW_A` 입력 후 Ctrl+S로 PUT을 확인한다. 바로 미리보기로 가면 `ORIGINAL_A`, 편집으로 돌아와도 `ORIGINAL_A`다.
- **원인:** saveNow는 `['chapters', pid]`의 글자 수만 갱신하고 `['chapter', chapterId]` 본문 캐시를 갱신하지 않는다. 미리보기는 그 상세 캐시를 읽고, 탭 전환은 편집기를 언마운트/재마운트한다. 30초 staleTime 동안 캐시가 신선하므로 즉시 재조회하지 않는다. `frontend/src/pages/EditorPage.tsx:120-127,305-321,366-370`; `frontend/src/components/ui/tabs.tsx:71-74`; `frontend/src/App.tsx:17-23`.
- **영향:** 저장된 문장이 화면에서 사라지고, 그 옛 원고를 이어 편집·저장하면 최신 서버 원고를 다시 덮는다. 단건 내보내기도 같은 상세 객체를 사용한다. 초기 본문으로 직접 되돌리는 입력은 `text === detail.data.content_md` 조건 때문에 저장을 건너뛸 수도 있다. `EditorPage.tsx:277-278,307`.
- **같은 계열:** 제목/상태/메모 PATCH도 목록만 invalidate하여 상세 헤더 상태가 즉시 갱신되지 않는다. `EditorPage.tsx:139-153,175-182`.
- **우선 수정:** 성공한 revision의 상세 캐시를 갱신하되 새로 입력한 draft와 구분한다. 미리보기/내보내기는 현재 draft 또는 저장 확정 snapshot 중 무엇을 쓰는지 명시한다.

### F3 · P0 · 확정 버그 — 작품 B를 열어도 작품 A 원고를 편집·저장한다

- **재현:** 작품 1의 101화를 연 뒤 홈에서 작품 2를 연다. URL은 `/projects/2/write`지만 편집기는 `ORIGINAL_A`다. `THOUGHT_THIS_WAS_B` 입력 후 Ctrl+S는 **101화** 저장 요청을 만든다.
- **원인:** 전역 chapterId가 작품 이동 시 초기화되지 않는다. 첫 회차 선택 effect는 chapterId가 null일 때만 동작한다. 상세 조회·저장은 pid 소속 확인 없이 chapterId만 사용한다. `frontend/src/pages/HomePage.tsx:99-102`; `frontend/src/pages/EditorPage.tsx:38-59,290-310`; `frontend/src/stores/editorStore.ts:41-47`.
- **백엔드 연결:** `/chapters/{cid}/content`는 cid로 찾은 회차를 저장하므로 요청이 가리킨 A가 실제 대상이다. `backend/app/routers/projects.py:205-213`.
- **우선 수정:** 라우트 pid와 chapter.project_id 일치를 렌더·저장 전에 강제한다. 작품별 마지막 회차를 저장하거나 작품 이동 시 안전하게 재선택한다. F1의 flush 수정과 함께 처리해야 한다.

### F4 · P1 · 확정 버그 — ‘현재 회차’가 AI 요청에 들어가지 않는다

- **재현:** 화면에 `현재 회차 (A-one)`이 보인다. 체크박스를 클릭해도 체크 상태는 false다. 생성 요청은 `context.chapter_id: null`이며 `project_id`도 없다. auto_lore/auto_outline/auto_foreshadow는 true지만 기준 회차·작품이 없다.
- **원인:** 편집기의 store와 AI store는 별개다. AI store.chapterId의 초기값은 null인데 편집기 진입/전환에서 이 값을 넣는 호출이 없다. 체크박스는 includeChapter만 변경하고, 표시 조건은 `ctx.chapterId !== null`까지 요구한다. `frontend/src/stores/aiPanelStore.ts:183-205`; `frontend/src/components/panels/AiPanel.tsx:207-220,595-607,649-654`; `frontend/src/pages/EditorPage.tsx:38-59,99-110`.
- **백엔드 연결:** 본문·회차 목표·권 개요·전후 회차 컨텍스트는 chapter_id가 있을 때만 만들어진다. 자동 로어/복선은 project_id가 필요하다. `backend/app/routers/ai_panel.py:182-242,259-278`.
- **우선 수정:** 생성 시 활성 편집기 컨텍스트를 한 곳에서 snapshot한다. 저장되지 않은 본문도 저장 barrier 또는 명시적 draft 전달로 포함한다. 캐릭터/로어/장면 소속을 함께 검사한다. 단일·병렬 요청이 같은 body를 사용하므로 양쪽 테스트가 필요하다.

### F5 · P1 · 확정 동작·안전장치 누락 — AI 결과를 다른 회차에 그대로 반영한다

- **재현:** A-one에서 생성한 `GENERATED`를 남겨두고 패널을 닫는다. A-two로 바꾸고 다시 열어 끼워넣기를 누르면 A-two 본문이 `ORIGINAL_TWO … GENERATED`가 된다. 원래 회차가 다르다는 확인은 없다.
- **원인:** 결과는 전역 store의 텍스트이고 요청 당시 작품·회차·본문 revision을 보관하지 않는다. 끼워넣기/선택 교체는 클릭 순간의 전역 EditorView에 쓴다. `frontend/src/stores/aiPanelStore.ts:117-140,160-165,237-255`; `frontend/src/components/panels/AiPanel.tsx:885-913`.
- **구분:** 명시 클릭에 따른 동작이며 자동 덮어쓰기 버그는 아니다. 그러나 여러 회차를 오가는 장편 작업에서는 출처 없는 결과의 잘못된 반영 위험이 확정적으로 존재한다. 브리프·sceneId도 회차별 자료가 아닌 전역 상태다. `frontend/src/stores/aiPanelStore.ts:183-205,234-235`.
- **우선 수정:** 결과에 작품/회차/revision/생성 설정을 묶는다. 원래 대상과 다른 곳에 반영할 때 명시 확인을 받는다. 회차별 브리프와 결과 이력을 저장한다.

### F6 · P1 · 확정 버그 — 장면 관리 버튼이 렌더되지 않아 CRUD에 들어갈 수 없다

- **재현:** fixture 장면 2개가 있어 ‘현재 장면’ 선택지는 기본값 포함 3개다. 그러나 `장면 관리 열기` 버튼 수와 ‘장면 관리’ 텍스트 수는 모두 0이다.
- **원인:** SceneManager의 open 초기값은 false이고, 유일한 열기 버튼을 `<Dialog open={open}>` 안에 넣었다. 이 프로젝트의 Dialog는 닫혀 있으면 children 전체를 `null`로 반환한다. `frontend/src/components/panels/SceneManager.tsx:35-39,105-116`; `frontend/src/components/ui/dialog.tsx:12-22`.
- **같은 코드 패턴:** 품질 진단과 canon 모순 검사도 열기 버튼을 닫힌 Dialog 안에 넣는다. 이 두 버튼은 코드 추적으로 확인했으며 별도 브라우저 count 시험은 하지 않았다. `frontend/src/components/editor/QualityDialog.tsx:86-87,134-147`; `frontend/src/components/editor/CanonDialog.tsx:47-48,70-83`.
- **우선 수정:** 열기 버튼을 Dialog 바깥에 두거나 실제 Trigger 계약을 도입한다. 그 뒤 장면 생성·편집·삭제·본문 합치기의 왕복 테스트를 수행한다. 현재 도달 불가능한 행별 저장 동작은 정상이라고 평가하지 않았다.

### F7 · P0 · 코드로 확정한 충돌 방지 결함 — 오래된 윤문 수락이 후속 집필을 덮어쓴다

- **경로:** 실행 버튼은 chapter_id만 보내므로 서버 저장본을 윤문한다. 실행 전 저장 barrier가 없다. 수락은 run_id만 보내며 최신 본문 확인이 없다. `frontend/src/components/panels/RefineReport.tsx:42-59`; `backend/app/routers/refine.py:41-50`.
- **백엔드 근거:** 원문은 report_json.original_text에 보관하지만 accept는 현재 본문과 비교하지 않고 result_text로 바로 교체한다. `backend/app/routers/refine.py:58-70,96-115`.
- **손실 시나리오:** 원고 R1 윤문 → 작가가 R2로 추가 집필·저장 → 이전 윤문 수락 → R2 대신 R1 기반 수정본 저장. 원문 비교가 없다는 결함은 코드로 확정했다. 이 감사에서는 실제 윤문/LLM을 실행하지 않았다.
- **추가 경로:** 장면 합치기도 기존 본문과 저장 revision 비교 없이 교체한다. 이는 명시적 교체 기능이나, autosave와 조정할 저장 장벽·복구본이 필요하다. `frontend/src/components/panels/SceneManager.tsx:89-97,205-210`; `backend/app/routers/scenes.py:99-117`.
- **우선 수정:** 실행 전 draft 저장을 확인하고 원본 hash/revision을 실행에 고정한다. 수락 시 불일치하면 409와 비교 화면을 제공한다. 수락 전 snapshot과 복구 경로를 보관한다.

### F8 · P2 · 설계 한계 — 장편 기획·순서·초안의 지속 관리가 약하다

- **기획 저장:** 권 개요는 blur/저장 버튼, 문체 프로파일은 1.5초 타이머다. 문체 편집기는 타이머 cleanup/pagehide flush/로컬 복구본이 없다. 탭 종료 직전 변경 보존은 보장되지 않는다. `frontend/src/pages/PlanPage.tsx:127-168,177-199`.
- **순서 관리:** 회차 트리는 선택과 추가만 제공하고 순서/권 변경·회차 삭제·검색 UI는 없다. 장면 관리에도 재정렬 UI가 없다. 서버 reorder API가 있다는 사실과 사용자가 화면에서 활용할 수 있다는 사실은 다르다. `frontend/src/components/layout/LeftSidebar.tsx:132-181`; `frontend/src/components/panels/SceneManager.tsx:146-215`; `backend/app/routers/projects.py:234-264`; `backend/app/routers/scenes.py:75-96`.
- **순서값 결함(코드):** 새 회차·장면은 `Date.now() % 1e7`을 sort_order로 쓴다. 약 2시간 46분 40초마다 값이 순환하므로 나중에 만든 항목이 앞에 놓일 수 있다. `frontend/src/components/layout/LeftSidebar.tsx:98-104`; `frontend/src/components/panels/SceneManager.tsx:50-55`. 이 시각 경계는 별도 브라우저 재현하지 않았다.
- **권장 개선:** 일관된 문서 저장 서비스와 복구함을 먼저 만든다. 이후 회차/장면 순서 편집, 전체 목차 검색, 회차별 브리프·서사 진행표를 연결한다. 문체·브리프를 다시 입력하게 하는 자동화보다 작성한 자료를 잃지 않고 재사용하는 쪽이 우선이다.

## 권장 실행 순서와 통과 조건

1. **저장·작품 경계:** F1/F2/F3/F7. 빠른 회차 전환·미리보기·작품 이동·저장 실패·저장 중 추가 입력·과거 윤문 수락에서 원고를 보존해야 한다. 기존 저장 버튼 표시만 보는 테스트로는 부족하다.
2. **AI 문맥과 반영:** F4/F5. 생성 요청의 작품/회차/본문 snapshot과 반영 대상이 일치하는지 요청 body와 결과를 검사한다. 실제 모델 비용 없이 mock SSE로 우선 검증 가능하다.
3. **장편 관리 도달성:** F6. 장면·진단 진입 버튼과 저장 왕복을 실제 화면에서 검증한다.
4. **기획의 지속성:** F8. 회차별 자료·순서·복구 이력을 한 작업 흐름으로 묶는다. 생성량 확대는 그 다음이다.

## 검증 한계·자기 검토

- 원고 품질, 병렬 작성의 비용/속도, 외부 플랫폼 규정은 이 감사의 검증 대상이 아니다.
- 일반 타이핑 뒤 Ctrl+Z는 브라우저 시험에서 정상 작동했다. CodeMirror history 확장이 안 보인다는 이유만으로 ‘실행 취소 불가’라고 판정하지 않았다. probe 결과에 반증을 남겼다.
- SceneManager 행별 저장은 진입 버튼 문제로 도달하지 못했다. 내부 상태 코드만 보고 실제 편집 손실을 재현했다고 쓰지 않았다.
- `sip` 검토에서 mocked API 증거와 실제 백엔드 증거를 분리했고, `mandela` 관점에서 fixture가 서버 성능/품질을 입증하는 듯한 표현을 제거했다. 외부 사실을 주장하지 않으므로 외부 검색은 하지 않았다. 추가 작업자 금지에 따라 별도 `shower`는 실행하지 않았고 최종 통합 리뷰는 부모에게 맡긴다.
