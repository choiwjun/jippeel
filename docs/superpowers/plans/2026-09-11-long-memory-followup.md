# 장편 기억 거버넌스 1차 후속 구현 계획

- 작성일: 2026-09-11
- 상태: 구현·검증 완료 (운영 적용 전)
- 기준: `HANDOFF.md`, `docs/audits/long-memory-design-2026-09-10.md`, 기존 `MemoryEntry` 최소 수직 슬라이스

## 1. 목표

작가가 자동 주입되는 장편 기억을 직접 확인하고 관리할 수 있게 한다. 기억의 작품 소속, 원본 회차, source revision/hash, 시간 범위, visibility, stale 여부를 목록에서 확인하고, 명시적으로 draft를 승인하거나 retired로 전환한다.

첫 후속 수직 슬라이스는 **의존성 없는 memory governance API + 프로젝트별 관리 화면**으로 제한한다. 기존 provenance/revision/hash/time-scope 선택 규칙을 재사용하며, provider 호출이나 원고 자동 변경은 하지 않는다.

## 2. 사용자 스토리

- 작가는 작품별 장편 기억을 목록으로 보고 종류·상태·회차별로 필터링한다.
- 작가는 기억이 어느 회차의 어느 revision/hash에서 파생됐는지 확인한다.
- 작가는 draft 기억을 검토한 뒤 명시적으로 approved 또는 retired로 바꾼다.
- 원고가 수정되어 stale이 된 기억은 자동 주입되지 않고 화면에서 경고된다.
- 작가는 직접 입력한 기억을 draft로 추가할 수 있다. 저장 시 source revision/hash는 서버가 현재 원고에서 계산한다.

## 3. 범위

### 포함

- `MemoryEntry`용 Pydantic 입력/출력 스키마
- 프로젝트 소속을 경로 파라미터로 고정하는 목록·수동 생성·상태/시간 범위 수정 API
- stale provenance를 계산한 응답
- 프로젝트 네비게이션에서 접근하는 memory 관리 화면
- 승인·폐기 전 명시적 사용자 클릭/확인
- backend unit/integration, frontend fixture/E2E, 접근성 검증

### 제외

- 자동 요약, backfill, LLM/provider 호출, 실제 모델 품질 평가
- 기존 `Project.memo`/`Chapter.memo`의 자동 분류·이관
- 새 embedding 또는 검색 인프라
- 원고 본문·revision·snapshot의 자동 변경
- 운영 DB migration, 운영 keyring, 기존 서비스 종료, 배포
- memory 행의 물리 삭제 API. 이 단계에서는 `retired`가 보존 가능한 폐기 상태다. memory가 연결된 회차 삭제도 409로 거부해 provenance 행을 보존한다.

## 4. 불변 계약 및 데이터 경계

1. `MemoryEntry.project_id`는 URL의 `pid`에서만 결정한다. 요청 body의 project ID를 받지 않는다.
2. `chapter_id`가 있으면 해당 회차가 `pid`에 소속되는지 provider/database write 전에 검증한다. 다른 작품 회차는 명확한 422로 거부하고 행을 만들지 않는다.
3. 생성 요청은 `source_revision`·`source_sha256`를 받지 않는다. 서버가 현재 `Chapter.revision`과 `content_md` SHA-256을 읽어 채운다. source chapter가 없으면 project-level memory로 저장하고 기존 빈 source hash 규칙을 유지한다.
4. 수동 생성은 항상 `draft`로 시작한다. approved는 별도 PATCH와 명시적 사용자 동작으로만 만든다.
5. 기존 `kind`(`summary|beat|decision|fact|timeline|relationship_note`)와 `visibility`(`draft|approved|retired`) 제약을 단일 상수/스키마로 공유한다.
6. source chapter의 현재 revision 또는 hash가 저장 provenance와 다르면 응답의 `stale=true`로 표시하고 context 선택에서 계속 제외한다. stale을 자동 승인하거나 source hash를 덮어쓰지 않는다.
7. `effective_from_sort_order > effective_to_sort_order`는 422다. 수정 API에서 생략한 값은 유지하고 `null`은 범위 제거로 해석한다.
8. 상태 전환은 `draft -> approved`, `draft -> retired`, `approved -> retired`만 허용한다. `retired`를 다시 approved로 되돌리는 기능은 이 단계에서 만들지 않는다.
9. 목록은 `limit`(기본 200, 최대 500)으로 제한하고 kind/source chapter sort_order/id의 결정적 순서를 사용한다. stale 계산에 필요한 회차는 현재 프로젝트에 한정한다.
10. memory body는 React text node로만 렌더링한다. HTML/Markdown을 실행하거나 `dangerouslySetInnerHTML`로 넣지 않는다.

## 5. API 계약

새 라우터: `backend/app/routers/memories.py`, prefix는 기존처럼 `/api/v1`.

### `GET /projects/{pid}/memories`

Query:

- `kind: MemoryKind | None`
- `visibility: MemoryVisibility | None`
- `chapter_id: int | None` — 지정 시 해당 회차가 작품에 속하는지 먼저 검증
- `stale: bool | None` — 서버 계산값으로 필터
- `limit: int = 200`, `1..500`

각 항목은 기존 필드와 다음 표시용 파생 정보를 반환한다.

- `stale: bool`
- `source_chapter_title: str | None`
- `source_chapter_revision: int | None`
- `source_chapter_sort_order: float | None`
- `source_sha256`와 저장된 `source_revision`
- `provenance`(JSON object)

### `POST /projects/{pid}/memories`

입력:

```json
{
  "chapter_id": 12,
  "kind": "fact",
  "body": "주인공은 북부 관문에서 정체를 숨긴다.",
  "effective_from_sort_order": 12,
  "effective_to_sort_order": null
}
```

- `body`는 공백만 허용하지 않고 합리적인 최대 길이를 둔다.
- `visibility`, source revision/hash, project ID는 클라이언트가 지정하지 않는다.
- 응답은 생성된 `draft`와 서버 계산 provenance를 반환한다.
- 입력 chapter가 현재 프로젝트에 속하지 않으면 422, 프로젝트가 없으면 기존 라우터 관례의 404다.

### `PATCH /projects/{pid}/memories/{mid}`

허용 필드:

```json
{
  "visibility": "approved",
  "effective_from_sort_order": 12,
  "effective_to_sort_order": 30
}
```

- URL의 `pid`와 대상 memory의 project ownership을 함께 확인한다. 다른 작품의 memory ID는 422로 거부한다.
- body, project_id, chapter_id, source revision/hash는 이 단계에서 수정하지 않는다. 원본이 바뀌면 새 draft를 만든다.
- 유효하지 않은 상태 전환은 422다.
- 성공 후 `stale`를 다시 계산해 반환한다.

### 오류 계약

- 프로젝트/memory/chapter가 없으면 기존 API의 404 관례를 따른다.
- 소속 불일치·유효하지 않은 enum/range/state transition은 422다.
- 구조적 DB 오류는 일반 500으로 삼키지 말고 기존 오류 처리 관례에 맞는 사용자 메시지와 서버 로그 맥락을 남긴다.

## 6. 화면 계약

새 경로: `/projects/:pid/memory`.

- 프로젝트 네비게이션에 `🧠 장편 기억` 링크를 추가한다.
- 화면 상단에 작품명/설명과 “자동 요약·AI 호출 없이 작가가 직접 관리하는 기억” 안내를 표시한다.
- 필터: 종류, visibility, stale 여부, source chapter.
- 카드/행: body, kind, draft/approved/retired, stale 경고, source 회차·revision·hash 앞부분, effective range, provenance 요약.
- “기억 추가” 폼은 kind/body/source chapter/effective range만 입력하며 생성 후 draft로 표시한다.
- draft에는 `승인`, draft/approved에는 `폐기` 동작을 제공한다. 상태 변경 전에는 키보드로 접근 가능한 확인 단계가 있고 취소할 수 있다.
- stale은 경고 색상만으로 전달하지 않고 텍스트(`원문 revision 변경으로 자동 주입 제외`)와 상태 속성을 함께 제공한다.
- mutation 성공 시 React Query 목록을 무효화하고, 실패 시 기존 toast 계약으로 사용자 메시지를 표시한다.
- 로딩/빈 목록/오류/저장 중 상태를 명시적으로 렌더링한다. body는 텍스트로만 출력한다.

예상 변경 파일:

- `backend/app/schemas.py`
- `backend/app/routers/memories.py` (신규)
- `backend/app/main.py`
- `backend/app/services/long_memory.py` (stale/표시용 helper가 필요할 때만 최소 수정)
- `backend/tests/test_memories_api.py` (신규)
- `backend/tests/test_long_memory.py` (기존 선택 규칙 회귀 보강)
- `frontend/src/lib/api.ts`
- `frontend/src/pages/MemoryPage.tsx` (신규)
- `frontend/src/components/layout/LeftSidebar.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/ui/*`는 기존 컴포넌트로 부족할 때만 수정
- `frontend/tests` 또는 기존 Playwright fixture 설정/테스트 파일

새 migration은 계획하지 않는다. 이미 존재하는 `memory_entries` migration은 임시 DB에서 head 적용을 검증하고, 운영 DB에는 승인 전 접근하지 않는다.

## 7. TDD 실행 순서

### RED

1. API schema 테스트: body/enum/range/limit/클라이언트 source 필드 차단.
2. service 테스트: chapter 소속 검증, 현재 revision/hash 서버 파생, allowed transition, stale 계산, deterministic order.
3. API 통합 테스트: project isolation, wrong chapter, list filters, manual create, approve/retire, invalid transition, stale response, no physical delete.
4. frontend fixture/E2E 테스트: route 접근, create draft, approve/retire, stale warning, error/toast, keyboard labels/critical serious axe 0.

각 테스트가 처음에는 새 endpoint/component 부재로 실패하는 것을 확인한다. 기존 `backend/.eval_tmp/run_backend_pytest.py`와 새 TEMP DB 규칙을 재사용한다.

### GREEN

1. 공통 Literal/response schema를 추가한다.
2. 기존 `create_memory_entry`를 호출하는 얇은 ownership/transition service boundary를 만든다. 중복 hash/stale 로직을 만들지 않는다.
3. memory router를 등록하고 bounded deterministic query를 구현한다.
4. API 타입과 프로젝트 memory 화면을 기존 Foreshadow/Lore/Plan 화면 패턴으로 구현한다.
5. route/nav와 React Query invalidation을 연결한다.

### REFACTOR

- 중복 ownership/response mapping을 작은 helper로 추출한다.
- mutation 시 이전 query data를 직접 mutate하지 않고 immutable update 또는 invalidate를 사용한다.
- 함수 50줄 미만, 파일 800줄 미만을 유지한다.
- body/프로비넌스 XSS 경계를 재점검하고 aria-label, focus, live region을 확인한다.

## 8. 검증 게이트

### Unit/integration

- 신규 API 테스트와 기존 전체 backend 회귀가 통과해야 한다.
- 새 TEMP SQLite + import 전 환경 설정으로 실행한다. 실제 `jippeel.db`를 사용하지 않는다.
- 테스트에서 실제 OpenAI/provider 호출을 금지한다.
- coverage는 신규 코드 포함 80% 이상을 목표로 한다.

### Frontend/E2E

- `npm run build` 통과(TS 오류 0).
- 기존 E2E/fixture와 memory 관리 critical flow를 통과한다.
- fixture와 실제 API 경계를 혼동하지 않는다. 실제 통합이 필요해지면 전용 port/임시 DB/Alembic head를 별도 준비한다.
- axe critical/serious 0, 키보드만으로 추가·승인·폐기·취소가 가능해야 한다.

### 독립 검토

- backend/API 경계는 fresh-context reviewer 또는 QA가 project ownership, stale, state transition, no-delete, migration scope를 검토한다.
- frontend는 fresh-context reviewer가 stale 표시, mutation ownership, focus/aria, body escaping을 검토한다.
- 발견된 CRITICAL/HIGH는 수정 후 해당 테스트와 전체 회귀를 다시 실행한다.

## 9. 중단 조건과 다음 단계

다음 중 하나면 구현을 멈추고 범위를 재승인한다.

- 기존 `MemoryEntry` provenance/hash 의미를 바꿔야 하는 경우
- 새 migration 또는 기존 운영 DB 접근이 필요해지는 경우
- 자동 요약/backfill/provider 호출 없이는 acceptance를 만족할 수 없는 경우
- memory 내용의 자동 삭제·자동 승인 요구가 생기는 경우
- 원고 저장/revision/snapshot 경계를 변경해야 하는 경우

이 슬라이스가 완료되고 검증된 뒤에만 자동 요약/backfill을 별도 설계한다. 운영 DB migration은 백업·manifest·restore 검증과 별도 명시 승인이 선행되어야 한다.

## 10. 완료 기준

- 작가가 project-scoped memory를 생성하고 목록에서 provenance/stale를 확인한다.
- draft를 approved 또는 retired로 명시적으로 전환할 수 있다.
- 다른 작품의 memory/chapter를 읽거나 쓸 수 없다.
- stale memory는 계속 AI context에서 제외된다.
- 원고 데이터는 자동 변경되지 않는다.
- backend 전체 회귀, frontend build, memory UI fixture/E2E, 접근성 검증이 통과한다.
- 운영 DB/provider/device는 사용하지 않는다.

## 11. 구현 및 검증 기록

- project-scoped memory CRUD/목록 필터 API와 수동 draft 생성, 서버 provenance revision/SHA-256 계산, stale 표시, 명시적 승인/폐기 전환을 구현했다.
- 다른 project의 chapter/memory 접근을 거부하며, memory가 연결된 회차 삭제는 409로 거부해 memory row와 provenance를 보존한다.
- 목록은 `kind → source sort order → id` 순으로 DB에서 먼저 정렬한 뒤 bounded limit을 적용한다.
- 프로젝트별 React Query 관리 화면에서 작품 정보, provenance, stale 경고, 상태 변경 확인 focus, 키보드 접근 가능한 조작을 제공한다. 자동 요약/provider 호출은 추가하지 않았다.
- 검증: 임시 SQLite backend 전체 `288 passed`, frontend `npm run build` 성공, memory Playwright E2E 및 critical/serious axe 검사 `1 passed`.
- 운영 DB migration/provider/Windows 실기기 QA는 실행하지 않았다. 테스트 환경에서 Starlette/AnyIO dependency deprecation warning 1건이 남지만 기능 테스트는 통과한다.
