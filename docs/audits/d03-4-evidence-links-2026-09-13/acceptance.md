# D03-4 근거 연결 — 수용 문서

날짜: 2026-09-13 / 슬라이스: D03-4 / 사양: docs/superpowers/plans/2026-09-13-d03-4-evidence-links-spec.md

## 범위

저장된 회차 목표 항목(core_events·character_choices·cost)과 원문 발췌(≤500자)를 수동으로 연결하는 근거 링크. 자동 판정·자동 발췌 없음(§6.3). 링크는 생성 시점의 `goal_version`과 `goal_item_text`, `excerpt`를 앵커로 보존하고, 읽기 시점에 파생 상태만 계산한다.

## 구현 내용

### 백엔드
- `chapter_goal_evidence_links` 테이블(migration `5f6a7b8c9d03`, head): `goal_version`·`goal_field`·`item_index`·`goal_item_text`·`excerpt` 앵커 + `chapter_id` FK ON DELETE CASCADE + `ck_evidence_link_field` CHECK + `chapter_id` 인덱스.
- 엔드포인트(routers/projects.py):
  - `GET /chapters/{cid}/evidence-links` — 파생 상태만 계산하는 읽기.
  - `POST /chapters/{cid}/evidence-links` — 발췌가 현재 원문에 존재 + 목표 항목 존재해야 생성(201). `BEGIN IMMEDIATE`로 writer slot 선점 후 검증→INSERT. BUSY→409, 기타 DB 오류→500.
  - `DELETE /chapters/{cid}/evidence-links/{lid}` — 명시적 삭제만, 타 회차 소속은 404.
- 파생 상태: `manuscript_status`(intact|broken, 현재 content_md 부분문자열), `goal_status`(unchanged|drifted|goal_deleted, 저장된 항목 텍스트와 위치 정확 비교), `current_goal_version` 노출.
- schema guard(`database.py`)가 테이블·컬럼·체크 제약 존재를 검증.

### 프론트엔드
- `EvidenceLinksSection`(AiPanel.tsx) — 브리프 섹션 내부 `role="group"`. 저장본 목표에서 항목 목록 구성, CodeMirror 선택 발췌 연결, 파생 배지(원문 파손/목표 변경됨/목표 삭제됨), 명시적 삭제 버튼.
- 선택 검증: 에디터 view 없음/타 회차/빈 선택/500자 초과 → 경고 toast + 요청 없음. POST 전 `flushManuscriptDraft`로 미저장 편집분 동기화.
- 무효화: 링크 생성·삭제, 목표 저장·삭제·복원(+409 경합 경로), 원고 revision 변경(`refreshMemoriesAfterRevision`) 시 `["evidence-links", chapterId]` 무효화.
- 기존 fixture 4종(chapter-goal·chapter-flow·preservation·ai-context)에 최소 GET mock 추가 — POST/DELETE는 여전히 tripwire 599로 향해 실제 mutation을 가리지 않음.

## 불변조건 검증

- 링크 생성·삭제는 원고 `content_md`/`revision`/snapshot/목표 `goal_version`/`flow_stage`/`status`를 건드리지 않음(테스트 잠금).
- 회차 삭제 시 링크는 FK cascade + ORM delete-orphan으로 함께 제거.
- 태어날 때부터 깨진 링크 금지: 생성 시점 원문 존재·목표 항목 존재 검증 + writer lock.

## 검증 증거(동 디렉터리)

- `red-log.txt` — 구현 전 6 failed RED 확인
- `backend-focused.txt` — 22 passed (test_evidence_links.py + test_migrations.py)
- `backend-full.txt` — 576 passed, 1 skipped, 0 isolation violations
- `frontend-evidence-links.txt` — 8 passed, tripwire no escapes
- `frontend-regressions.txt` — chapter-goal 8 / chapter-flow 10 / preservation 26 / ai-context 15 / memory 31 / serial-state 6 전부 통과
- `frontend-tsc.txt` — TSC_EXIT=0
- `source-hashes.txt` — 검증 시점 소스 sha256
- `review-log.md` — 독립 검토 2건(모두 PASS_WITH_NOTES) 지적 처리 기록

## 독립 검토

- 백엔드: PASS_WITH_NOTES — LOW 2(TOCTOU·BUSY 미매핑) 수정, NOTE 2(1건 수용: 관례 일치), 테스트 갭 전부 보강
- 프론트엔드: PASS_WITH_NOTES — LOW 3(2건 수정, 1건 선존 공유 갭 수용), NOTE 4 수용, 테스트 갭 2건 보강

## 수용

D03-4 근거 연결 슬라이스를 **수용**한다. 사양의 계약(수동 링크·앵커 보존·파생 상태·명시적 삭제·자동 판정 없음)이 구현·검증됐고, 기존 수용 범위(D01·D03-1·D03-2·D03-3·보존 계약) 회귀가 없다.

격리 범위: 합성 TEMP SQLite·fixture 전용 포트 15233만 사용. 운영 DB·실제 provider·credential·배포·commit/push 미수행.
