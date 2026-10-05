# 플랫폼 버그 조사 — 2026-10-05

**후속 상태:** 아래는 수정 전 조사 기록이다. 사용자 후속 승인으로 **BUG-01~08 모두 수정·검증·독립 검토 수용 완료**했다. 현재 판정은 [acceptance.md](acceptance.md), 수정 범위는 [fix-plan.md](fix-plan.md)를 참조한다.

현재 코드에서 **8개 결함을 재현**했다. 기존 backend suite는 **950 passed / 1 skipped / 70 subtests passed**, 격리 위반 0이다. 아래 결함은 기존 suite가 통과한 상태에서 추가 시나리오로 확인했다. 제품 구현 수정은 수행하지 않았다.

조사 기준 HEAD: `f0606d07f82040927b11fe57803770fbc7269690`. 범위와 방법은 [scope.md](scope.md), 기존 suite 실행 결과는 [baseline-results.txt](baseline-results.txt)에 기록했다. 과거 기능 수용 기록은 유지하며, 이번 결과는 해당 구현의 구체적인 실패 조건을 추가로 기록한 것이다.

## 확인된 결함

P1은 편집 내용 유실·다른 회차 오염·원문 변경 후 잘못된 기억 사용에 먼저 대응할 우선순위다. P2는 조건부 기능 오류와 API 실패 계약이다.

| ID | 우선순위 | 결함 | 확인 방법 |
| --- | --- | --- | --- |
| BUG-01 | P1 | 메모 저장 대기 중 회차를 바꾸면 다음 회차에 메모 저장 | 실제 React 앱 + Chromium + 합성 API |
| BUG-02 | P1 | 장면 저장 버튼이 편집 내용을 기존 값으로 되돌린 뒤 저장 | 실제 React 앱 + Chromium + 합성 API |
| BUG-03 | P1 | 근거 원고 수정 후에도 승인된 아크 요약이 stale=false로 계속 주입 | 합성 SQLite + 실제 worker + fake provider |
| BUG-04 | P2 | 권별 순서 값이 겹치면 AI 직전·다음 회차가 화면 순서와 달라짐 | 실제 API 목록 + 공유 context builder |
| BUG-05 | P2 | 자동저장 대기 중 내보내면 화면의 최신 원고가 빠짐 | 실제 Chromium 다운로드 파일 읽기 |
| BUG-06 | P2 | 회차 상태 저장 성공 후 에디터 상태가 이전 값에 머묾 | 실제 React 앱 + Chromium + 합성 API |
| BUG-07 | P2 | 캐릭터 퇴장·사망에 연결된 회차 삭제가 500 | 실제 API + 합성 SQLite |
| BUG-08 | P2 | NOT NULL 필드의 명시적 null PATCH를 허용해 500 발생 | 실제 API + 합성 SQLite, 6개 입력 |

### BUG-01 — 빠른 메모가 다른 회차에 저장됨

- 위치: `frontend/src/pages/EditorPage.tsx:193` 및 `:278`.
- 재현: 1화의 빠른 메모에 `MEMO_FOR_CHAPTER_10` 입력 → 800ms debounce가 끝나기 전에 좌측 트리에서 2화 선택 → 저장 요청 대기.
- 실제 결과: `PATCH /chapters/11 {"memo":"MEMO_FOR_CHAPTER_10"}`. 1화(id=10) 메모는 null, 2화(id=11)에 1화 메모가 저장됐다.
- 기대 결과: 입력이 시작된 1화에 저장하거나, 1화 작업본을 보존한 채 전환 처리.
- 원인: timer가 변경 가능한 mutation observer를 사용한다. mutationFn은 현재 렌더의 `chapterId`로 URL을 만들며, 예약 시점의 회차 id를 변수로 보관하지 않는다. 회차 전환 시 timer 정리도 없다.
- 수정 방향: mutation 변수에 `projectId`, `chapterId`, `memo`를 함께 전달한다. 타이머는 입력 문자열을 즉시 복사해 보관하고, 전환·unmount 시 기존 회차 작업본의 저장/보존 정책을 적용한다.
- 근거: [frontend-results.json](frontend-results.json), `memo_chapter_switch`.

### BUG-02 — 장면 수정 내용이 저장되지 않음

- 위치: `frontend/src/components/panels/SceneManager.tsx:198`, mutation 본문 `:72`.
- 재현: AI 패널 → 장면 관리 → 장면A 선택 → 본문을 `SCENE_A_EDITED`로 변경 → 해당 장면 행의 저장 클릭.
- 실제 결과: 요청 본문은 `{"title":"장면A","content_md":"SCENE_A_ORIGINAL"}`. 합성 서버의 장면도 이전 내용에 머물렀다.
- 기대 결과: 방금 편집한 문자열을 저장하고 저장 성공을 표시.
- 원인: 저장 버튼이 먼저 `setDraftTitle(s.title)` / `setDraftContent(s.content_md)`로 이전 서버 값을 적재한다. 현재 React/TanStack 실행에서는 변경된 상태가 mutationFn에 반영되어 원래 내용이 전송된다. 저장 성공 메시지는 편집 내용이 반영되지 않아도 표시된다.
- 수정 방향: 저장 버튼에서 기존 값을 다시 적재하지 않고, `{id, title, content_md}`의 편집 시점 값을 mutation 변수로 전달한다.
- 근거: [frontend-results.json](frontend-results.json), `scene_edit_reset_on_save`.

### BUG-03 — 상위 기억에 근거 원문의 stale 상태가 전파되지 않음

- 위치: `backend/app/services/long_memory.py:102`, 상위 기억 생성 `backend/app/services/summary_worker.py:444`.
- 재현: 1·2화의 승인된 회차 요약 → 실제 아크 worker를 fake provider로 실행 → 생성된 아크 요약 명시 승인 → 1화 본문을 revision 1에서 2로 변경 → 기억 목록과 3화 컨텍스트 조회.
- 실제 결과: 원천 회차 요약은 `stale=true`, 아크는 `stale=false`. 3화에 선택된 기억은 `arc_summary / ARC_OLD_FACT`였고, 수정 전 정보를 계속 사용했다.
- 기대 결과: 상위 요약의 원천 요약·근거 원고가 변경되면 상위 요약도 사용을 중지하고 근거 변경을 알림.
- 원인: 아크는 `chapter_id=None`으로 만들어지고, `is_stale`는 chapter_id가 없으면 즉시 false를 반환한다. `arc_source_entry_ids`의 현재 승인 상태와 근거 원고 hash/revision을 선택 단계에서 검증하지 않는다.
- 수정 방향: 출처 그래프를 검증하여 상위 요약의 원천 변경을 기억 목록·선택에 전파한다. 원본 승인 이력은 보존하고 재생성 결과는 다시 draft로 만든다. 계층 기억 설계에 기록된 chapter_id=None 저장 방식은 유지하면서 누락된 유효성 검증을 보강하는 범위다.
- 근거: [backend-results.jsonl](backend-results.jsonl), `arc_stale_source`. 실제 provider 호출 없이 fake 함수 1회 실행.

### BUG-04 — 화면 순서와 AI 연속성 순서가 다름

- 위치: `backend/app/services/ai_context.py:733` 및 `:744`.
- 재현: 1권 1화 sort=1 → 1권 마지막 화 sort=2 → 2권 첫 화 sort=1. 이 값들은 CRUD가 허용한다. 마지막 대상을 기준으로 공유 생성 컨텍스트 구성.
- 실제 결과: API/화면은 1권 전체 다음에 2권 첫 화를 둔다. AI 컨텍스트에는 직전 회차 끝부분이 빠지고, 1권 마지막 화가 “다음 회차”로 들어간다.
- 기대 결과: 2권 첫 화의 직전 회차는 1권 마지막 화이며, 최종 회차라면 다음 화가 없음.
- 원인: 목록/프론트는 `(volume, sort_order)`로 정렬하지만 context builder의 이웃 조회는 volume 없이 `sort_order <` / `>`만 사용한다. 동일 순서 값의 id 비교도 없다.
- 발생 범위: 권 사이 순서 값이 겹치거나 이동·재정렬로 권 순서와 전역 sort_order가 다른 데이터. 기존 bootstrap이 생성하는 전역 순서가 정상인 경우까지 오류라고 주장하지 않는다.
- 수정 방향: UI/API/직전·다음/미래 참조가 같은 정렬 키를 사용하도록 통일한다. 권 없음은 기존 계약대로 뒤에 둔다.
- 근거: [backend-results.jsonl](backend-results.jsonl), `ai_volume_order`.

### BUG-05 — 최신 편집 내용이 내보내기 파일에서 빠짐

- 위치: `frontend/src/pages/EditorPage.tsx:335`, 프로젝트 전체 경로 `:310`.
- 재현: 원고를 `VISIBLE_UNSAVED_NEW_BODY`로 수정하고 자동저장이 대기 중인 상태에서 현재 회차 마크다운 내보내기. 합성 저장 요청 응답은 대기시켜 시나리오를 고정했다.
- 실제 결과: 화면에는 새 본문이 있지만 다운로드 파일은 `ORIGINAL_BODY`다.
- 기대 결과: 사용자가 보고 있는 최신 편집 내용을 내보내거나, 저장 완료를 기다린 뒤 내보냄.
- 원인: 현재 회차 내보내기는 draft coordinator 대신 서버 상세 query의 `chapter.content_md`를 사용한다. 자동저장 debounce는 1500ms다. 프로젝트 전체 경로도 draft flush 없이 서버 본문을 읽는다.
- 수정 방향: 대상 회차 작업본을 flush하고 저장 오류·충돌이 있으면 알려준다. 내보낼 시점의 원고를 명시적으로 고정한다.
- 확인 범위: 현재 회차 `.md`의 실제 다운로드를 검증했다. `.txt` 및 전체 회차는 공유된 이전 데이터 사용 경로를 코드로 확인했으며 다운로드 재현 건수에 별도 추가하지 않았다. 서버 원고 자체가 삭제되는 결함은 아니다.
- 근거: [frontend-results.json](frontend-results.json), `export_pending_draft`.

### BUG-06 — 회차 상태 저장 후 상세 화면이 갱신되지 않음

- 위치: `frontend/src/pages/EditorPage.tsx:193`.
- 재현: 1화 상태를 초고 → 수정중으로 선택하고 PATCH 성공 및 회차 목록 갱신을 기다림.
- 실제 결과: 서버 상태와 좌측 회차 트리는 수정중, 에디터 상태 선택 값은 초고다.
- 원인: onSuccess는 `['chapters', pid]`만 invalidate하고 `['chapter', pid, chapterId]` 상세 캐시를 갱신하지 않는다. 상태 선택은 상세 캐시에 바인딩된다.
- 수정 방향: 응답의 회차 id에 대응하는 상세 캐시를 갱신하고 관련 목록·재개 정보를 갱신한다. 늦은 응답이 현재 다른 회차를 변경하지 않도록 변수의 identity를 사용한다.
- 근거: [frontend-results.json](frontend-results.json), `metadata_cache_stale`.

### BUG-07 — 캐릭터 라이프사이클 참조가 회차 삭제를 500으로 만듦

- 위치: `backend/app/routers/projects.py:1039` 및 `:1072`, FK `backend/app/models.py:545`.
- 재현: 캐릭터를 departed로 생성하며 `lifecycle_chapter_id`에 회차 id 연결 → 해당 회차 DELETE.
- 실제 결과: 500 `{"detail":"회차 삭제 중 오류가 발생했습니다."}`. rollback되어 원고는 보존됐다.
- 기대 결과: 참조를 먼저 정리하도록 409로 설명하거나, 명시적으로 정의한 라이프사이클 참조 보존 정책 적용.
- 원인: 삭제 전 복선·기억·사건 영향은 확인하지만 캐릭터 lifecycle FK는 확인하지 않는다. FK에는 ON DELETE 정책이 없어 무결성 오류가 발생한다.
- 수정 방향: 기존 삭제 실패 계약과 같은 참조 검사/409를 추가한다. 자동 null 변경은 provenance 정책 확인 없이 도입하지 않는다.
- 대조: 동일 참조를 가진 프로젝트 전체 삭제는 204로 성공했다. 프로젝트 삭제 오류로 확대 해석하지 않는다.
- 근거: [backend-results.jsonl](backend-results.jsonl), `lifecycle_chapter_delete`, `lifecycle_project_delete`.

### BUG-08 — 명시적 null 입력이 검증을 통과한 뒤 500 발생

- 위치: `backend/app/schemas.py:28`, `:115`, `:626`, `:1226` 및 각 PATCH의 직접 setattr/commit.
- 재현한 6개 입력: 프로젝트 `title=null`, 회차 `title=null`, 회차 `status=null`, 캐릭터 `name=null`, 캐릭터 `lifecycle_status=null`, 장면 `content_md=null`.
- 실제 결과: 모두 HTTP 500. Pydantic은 `T | None`을 허용하고 라우터는 exclude_unset 결과의 명시적 null을 NOT NULL DB 필드에 적용한다.
- 기대 결과: 허용하지 않는 값은 422로 거부하고 정상 데이터를 보존.
- 수정 방향: “생략”과 “명시적 null”을 구별해 NOT NULL 필드에 검증을 추가한다. `volume`, `memo`, `concept`처럼 null이 유효한 필드는 계약을 유지한다.
- 발생 범위: 직접 API/연동 클라이언트의 잘못된 입력. 현재 UI가 이 6개 null 요청을 보낸다고 주장하지 않는다.
- 근거: [backend-results.jsonl](backend-results.jsonl), `null_patch` 6건.

## 실행과 재현

재현 스크립트는 결함이 존재한다는 관찰 결과를 assertion으로 검사한다. exit 0은 재현 성공이며 제품 수정 완료를 뜻하지 않는다.

```bash
# 저장소 루트 — native Windows Python 내부에서 먼저 격리 guard 설치
backend/.venv/Scripts/python.exe -I -B docs/audits/2026-10-05-bug-hunt/backend_probe.py

# 별도 터미널 / cwd: frontend — 전용 포트, production proxy 없음
JIPPEEL_FIXTURE_API_VIOLATIONS="$(mktemp /tmp/jippeel-bughunt-tripwire-XXXXXX)" \
  ./node_modules/.bin/vite --host 127.0.0.1 --port 15483 --strictPort --config vite.fixture.config.ts

# Vite ready 후 저장소 루트
node docs/audits/2026-10-05-bug-hunt/frontend_probe.cjs
```

Backend: 합성 TEMP SQLite, 앱 import 전 `tests.isolation_guard.install`, TestClient 내부 IPC, fake keyring, fake provider만 사용. 최종 `violations=[]`, `subprocess_attempts=0`. Browser: 실제 소스의 React 앱과 headless Chromium, `/api`는 전부 합성 응답, 외부 origin 차단, 서버의 API tripwire 0 bytes, 최종 mock 누락/외부 요청 0건.

이번 조사에서 앱 소스·기존 테스트·운영 DB·credential·실제 provider·migration·배포·stage/commit/push는 변경하지 않았다. 조사 파일과 문서 진입점만 추가했다. 이번에 만든 fixture 서버는 조사 종료 후 중지했다.

## 한계와 후속 확인

실제 provider의 출력 품질·OAuth 상태·운영 DB의 데이터·실기기 검증은 이 결과에 포함하지 않는다. 전체 플랫폼이 무결함이라는 판정도 아니다. 추가 브라우저 검증은 4개 실패 조건에 한정했다.

수정 시 BUG-01/02는 회차/장면 전환과 저장 지연, BUG-03은 원천 수정·폐기와 다단계 요약, BUG-04는 권 경계·같은 sort_order·권 없음, BUG-05는 저장 중·저장 실패·revision 충돌, BUG-06은 저장 후 회차 전환, BUG-07은 참조 해제 후 삭제, BUG-08은 null 허용/불허 필드의 차이를 회귀 검증해야 한다. 기존 원고 보존·승인 게이트·고정 provider 계약을 유지한다.
