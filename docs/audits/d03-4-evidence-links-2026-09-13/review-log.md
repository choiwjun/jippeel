# D03-4 근거 연결 — 독립 검토 기록

날짜: 2026-09-13 / 검토자: 독립 서브에이전트 2인(백엔드·프론트), fresh 컨텍스트, 읽기 전용

## 판정

| 검토 | 판정 | 지적 |
|------|------|------|
| 백엔드 | PASS_WITH_NOTES | LOW 2 + NOTE 2 + 테스트 갭 |
| 프론트엔드 | PASS_WITH_NOTES | LOW 3 + NOTE 4 + 테스트 갭 |

차단(BLOCKER/HIGH) 지적 없음.

## 백엔드 지적 처리

| # | 지적 | 처리 |
|---|------|------|
| B1 | 링크 생성에 writer lock 없음 — 검증↔INSERT 사이 TOCTOU로 태어날 때부터 깨진 링크 가능 | **수정** — `BEGIN IMMEDIATE`를 읽기 전에 배치(`delete_chapter` 패턴 재사용, projects.py:817) |
| B2 | POST/DELETE에 SQLAlchemyError 미처리 — SQLITE_BUSY가 500으로 새어 나감 | **수정** — 형제 엔드포인트와 동일하게 BUSY→409, 기타→500 로깅 매핑 |
| B3 | `test_links_cascade_with_chapter(client, db_session=None)` dead param | **수정** — 인자 제거 |
| B4 | 모델 `created_at`에 `nullable=False` 누락(migration과 drift) | **수용** — 다른 모든 모델의 `created_at`도 동일 패턴(server_default만). 코드베이스 관례와 일치하므로 변경 없음 |

백엔드 테스트 갭 처리: `character_choices` 성공 생성, `item_index=-1`, excerpt>500자, 알 수 없는 추가 키, 항목 누락(목록 축소) 드리프트, 미존재 회차 GET/POST/DELETE 404, 삭제 시 보존 assertion, migration `chapter_id` 인덱스 존재 assertion — **전부 추가**(test_evidence_links.py, test_migrations.py).

## 프론트엔드 지적 처리

| # | 지적 | 처리 |
|---|------|------|
| F1 | `aria-label` on plain `<div>` — naming-prohibited role, AT가 그룹명을 읽지 못함 | **수정** — `role="group"` 부여(형제 섹션과 동일 패턴) |
| F2 | `saveGoal`/`restoreGoal`의 409 경로가 evidence-links를 무효화하지 않음 | **수정** — 두 onError 409 분기에 `["evidence-links", chapterId]` 무효화 추가 |
| F3 | `freezeConflict`/`initFromServer` adopt 경로가 revision 갱신 시 evidence-links 미무효화 | **수용** — memories·chapter-resume이 공유하는 선존 갭. D03-4가 악화시키지 않으며, 공유 무효화 정책 변경은 별도 슬라이스 범위 |
| F4 | 미저장 편집분 발췌 시 서버 content_md와 불일치 → 422 경합 창 | **수정** — POST 전 `flushManuscriptDraft(projectId, chapterId)` 호출(generate()와 동일 패턴). fixture에 PUT /content 핸들러 추가 |
| F5 | 항목별 버튼/비활성 사양 vs Select+클릭 시 toast 구현 | **수용** — 기능 등가. CM 선택은 비반응형이라 선택 기반 비활성 불가 |
| F6 | 목표 축소 후 stale pick 키 | **수용** — Select가 빈 값으로 렌더되고 버튼 비활성, 무해 |
| F7 | 중복 링크 생성 가능 | **수용** — 사양이 금지하지 않음 |

프론트엔드 테스트 갭 처리: `cost` 스칼라 POST `item_index:null` 계약, `목표 삭제됨` 배지(fixture `goalPresent` 플래그 추가) — **추가**. >500자/공백 선택/교차 회차 가드는 경고 toast 경로로 부분 커버됨(선택 없음 테스트). 무효화 기반 배지 갱신 e2e는 fixture 복잡도 대비 보류(백엔드 파생 로직 테스트로 커버).

## 검토 후 재검증

- backend focused: 22 passed (test_evidence_links.py + test_migrations.py)
- backend full: 576 passed, 1 skipped, 0 isolation violations
- evidence-links fixture: 8 passed, tripwire no escapes
- 회귀 fixture: chapter-goal 8 / chapter-flow 10 / preservation 26 / ai-context 15 / memory 31 / serial-state 6 — 전부 통과
- tsc --noEmit: exit 0
