# 장편 기억 거버넌스 제품 사양

- 작성일: 2026-09-11
- 상태(2026-09-12 대조): **기반·승인 P1 네 건 및 M01~M05 수용 완료 / 운영 적용 전**
- 현재 작업·최신 검증: [전체 현황](../../handoffs/2026-09-08-remaining-work.md). error 표시·focus 복귀 등 M01~M05는 [최종 수용](../../audits/memory-m01-m05-2026-09-12/acceptance.md)으로 종결했다. 아래는 제품 계약이며 확장·운영 상태는 원장을 따른다.
- 상위 사양: `대시보드_MVP_사양.md` v0.6
- AI provider 기준: `기술설계_GPT_OAuth_브릿지_v1.md` (고정 OAuth bridge, 실제 provider 수용 전)
- 구현 계획: `docs/superpowers/plans/2026-09-11-long-memory-followup.md`
- 대상 독자: 제품 담당자, 백엔드·프론트엔드 개발자, QA, 운영 승인자

## 1. 문제 정의

장편 집필에서 작가가 원고의 사실·결정·요약을 직접 관리하고, AI가 현재 원고와 승인된 기억만 참고해야 한다. 자동 요약이나 provider 품질은 별도 승인 범위이며, 첫 단계에서는 작가의 명시적 승인과 provenance 확인을 우선한다.

## 2. 목표와 범위

### 포함

- 작품별 장편 기억 생성·목록·필터
- 서버가 계산하는 근거 회차 revision과 SHA-256
- `draft → approved/retired` 명시적 상태 전환
- 현재 원문과 provenance가 다르면 stale 표시 및 AI context 자동 제외
- project/chapter ownership 검증
- 연결된 회차 삭제 시 memory 보존을 위한 `409 Conflict`
- `/projects/:pid/memory` 관리 화면
- provenance, stale 경고, 상태, 적용 범위, 근거 회차 표시

### 제외

- provider를 호출하는 자동 요약·backfill·자동 승인
- 기존 memory body/provenance 수정
- 실제 provider 호출 및 품질 판정
- 운영 DB migration·복원 실행
- 로그인·다중 사용자 권한 모델

## 3. 사용자와 핵심 시나리오

### 작가: 기억 초안 추가

1. 작품 화면에서 `🧠 장편 기억`으로 이동한다.
2. 종류, 내용, 선택적 근거 회차, 적용 sort order 범위를 입력한다.
3. 저장하면 서버가 현재 근거 회차의 revision/hash를 계산한다.
4. 결과는 항상 `draft`이며 원고 본문은 바뀌지 않는다.

### 작가: 검토·승인·폐기

1. 목록에서 body, 근거 회차, revision, hash 일부, provenance, stale 상태를 확인한다.
2. draft는 `승인` 또는 `폐기`할 수 있다.
3. approved는 `폐기`만 가능하다.
4. retired는 terminal 상태이며 재활성화할 수 없다.
5. 모든 상태 변경은 확인 단계와 키보드 focus 이동을 제공한다.

### 작가: 원문 변경 후 stale 확인

1. 근거 회차 원문을 수정하면 revision/hash가 변경된다.
2. 기존 memory는 삭제하지 않고 `stale=true`로 표시한다.
3. stale memory는 AI context에 자동 주입하지 않는다.
4. 새 원문 기준 memory는 별도 초안으로 추가한다.

## 4. 기능 요구사항

| ID | 요구사항 | 완료 기준 |
| --- | --- | --- |
| LM-001 | 작품별 memory 생성 | 다른 작품 chapter를 사용하면 422, 없는 project는 404 |
| LM-002 | 서버 provenance 계산 | client가 revision/hash/visibility를 지정할 수 없음 |
| LM-003 | deterministic 목록 | `kind → source sort order → id`, limit 적용 전 정렬 |
| LM-004 | stale 필터 | 500건 batch 경계를 넘어도 요청 limit까지 stale 결과 검색 |
| LM-005 | 상태 전환 | draft 승인/폐기, approved 폐기, retired 재활성화 거부 |
| LM-006 | ownership 격리 | cross-project PATCH/목록/chapter filter를 거부 |
| LM-007 | 원고 보존 | memory 연결 회차 삭제는 409, memory row 물리 삭제 금지 |
| LM-008 | AI 주입 경계 | approved·non-stale·시간축 조건을 만족한 memory만 주입 |
| LM-009 | 안전한 표시 | body/provenance를 HTML로 해석하지 않고 텍스트로 표시 |
| LM-010 | 접근성 | stale 경고는 텍스트와 상태 속성으로 전달하고 승인/폐기 확인을 keyboard로 조작 |

## 5. API 계약

```text
GET   /api/v1/projects/{pid}/memories
      ?kind=&visibility=&chapter_id=&stale=&limit=1..500

POST  /api/v1/projects/{pid}/memories
      { chapter_id?, kind, body, effective_from_sort_order?, effective_to_sort_order? }

PATCH /api/v1/projects/{pid}/memories/{mid}
      { visibility?, effective_from_sort_order?, effective_to_sort_order? }
```

응답은 다음 provenance와 상태 정보를 포함한다.

```text
id, project_id, chapter_id
source_revision, source_sha256
kind, body, visibility
provenance, stale
source_chapter_title, source_chapter_revision, source_chapter_sort_order
effective_from_sort_order, effective_to_sort_order
```

서버 오류 계약:

- project/memory/chapter 없음: 404
- project/chapter/memory 소속 불일치: 422
- enum/range/state transition 오류: 422
- 연결 chapter 삭제: 409

## 6. 데이터 불변식

- `Chapter.content_md`와 `Chapter.revision`이 원문 정본이다.
- memory 생성 시 source revision/hash는 서버가 계산한다.
- memory body와 provenance는 이 범위에서 수정하지 않는다.
- project/chapter FK와 API ownership을 함께 검증한다.
- stale 판정은 source revision 또는 source SHA-256 불일치로 계산한다.
- retired memory는 다시 approved/draft로 전환하지 않는다.
- memory 연결 chapter는 provenance 보존을 위해 삭제하지 않는다.

## 7. UI 요구사항

- 작품명·설명과 수동 관리 범위를 상단에 표시한다.
- 종류·상태·stale·근거 회차 필터를 제공한다.
- loading, error, empty, saving 상태를 표시한다.
- stale에는 `원문 revision/hash가 달라 자동 주입하지 않습니다`라는 설명을 제공한다.
- hash는 전체 원문 대신 앞부분만 표시한다.
- body는 `whitespace-pre-wrap` 텍스트로 렌더링한다.
- mutation 성공 시 목록을 invalidate하고, 실패 시 사용자 메시지를 표시한다.

## 8. QA acceptance

필수 자동 검증:

- 임시 SQLite backend 전체 회귀
- schema/ownership/range/state transition API 테스트
- 500건 정렬 bound 및 stale batch 경계 테스트
- 회차 삭제 409 보존 테스트
- memory Playwright flow 및 axe critical/serious 0
- frontend build
- native Windows temp DB/fake provider integration은 실제 provider나 운영 DB 없이 수행

P1 보정 전 증거(역사적 기록):

전체 suite의 아래 외부 script 실패는 이후 P1 최종 실행에서 재현되지 않았다.
최신 검증 수치와 한계는 [전체 현황 §9](../../handoffs/2026-09-08-remaining-work.md#9-검증-수치의-최신성과-근거),
상세 실행·독립 검토는 구현 계획의 P1 최종 수용 기록을 따른다.

- OAuth 변경 전 기준선 backend **292 passed**
- OAuth 변경 후 변경 범위 회귀 **108 passed** (고정 provider·memory·legacy compatibility 선택집합)
- 전체 backend suite 관찰값은 `294 passed, 9 failed, 1 skipped`; 실패는 누락된 im-not-ai
  외부 script 환경 의존이며 provider/memory 변경범위 실패는 아니다.
- 핵심 4개 모듈 합산 line coverage **93.59%** (표시 94%; branch 전체 91%, `pytest-cov==7.1.0`, `coverage==7.16.0`)
  - memories router 80%, schemas 98%, long_memory 92%, summary_jobs 85%
- memory E2E/axe **1 passed**

## 9. 운영·승인 게이트

구현과 테스트가 통과해도 다음은 별도 승인 전 실행하지 않는다.

- 기존 운영 DB migration 및 restore
- 실제 provider 품질 평가와 비용 발생
- 암호화 keyring 접근
- 지정 Windows 실기기 QA
- 자동 요약/backfill 구현·실행

운영 준비 절차는 `docs/runbooks/long-memory-governance-release.md`를 따른다. 자동 요약/backfill의 별도 설계는 `docs/superpowers/plans/2026-09-11-long-memory-auto-summary-backfill.md`를 따른다.

## 10. Astra 결정 결과와 남은 승인

결정 기록: `docs/decisions/2026-09-11-astra-long-memory-release.md`.

1. Coverage: `pytest-cov==7.1.0` + `coverage==7.16.0`, 핵심 모듈 80% gate를 채택했다.
2. Provider pilot: 고정 `ChatGPT OAuth` / `gpt-5.6-luna` 6-case, 독립 평가자 2명, USD 20 hard cap을 평가 대상으로 둔다. 실제 호출은 bridge availability/정책·비용과 source owner 승인 후다.
3. Windows QA: Windows 11 x64 물리 장치 1대, 전용 QA 계정, disposable SQLite, dummy credential, Edge/NVDA를 기준으로 한다. 장치와 시간 창 확정 전 실행하지 않는다.
4. Auto-summary/backfill: provider 호출·자동 승인·운영 backfill은 보류한다. provider-free deterministic planner와 fake worker 계약만 구현·검증했으며, schema/migration 및 운영 실행은 별도 승인 후 진행한다.
5. backfill 대상 project/chapter, 작가 승인 UX, production backup/restore owner는 별도 확정한다.
