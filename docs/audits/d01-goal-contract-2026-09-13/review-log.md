# D01 독립 검토 기록 — 2026-09-13

검토 대상: `choiwjun/d01-contract-analysis` worktree의 uncommitted 변경 전체
(base `c2e4f6a5` == main tip). 두 검토자 모두 fresh 컨텍스트 subagent.

## 검토자 A (agent 7e242186) — 계약·코드 정적 검토

**판정: PASS_WITH_NOTES** — 10개 검증 질문 전부 PASS, 차단 결함 없음.

| # | 심각도 | 발견 | 처리 |
|---|--------|------|------|
| 1 | LOW | `delete_chapter_goal`의 SQLITE_BUSY 미처리 → 500 | **수정** — `delete_chapter` 패턴으로 BUSY→409 매핑 추가 (projects.py:500-509) |
| 2 | LOW | `expected_goal_version`·`goal` 필드 생략 허용 (사양은 required) | **수정** — `ChapterGoalWrite.goal`, `ChapterGoalWrite.expected_goal_version`, `ChapterGoalRestoreRequest.expected_goal_version`을 required로 조임 (schemas.py:153,155,202) + 계약 잠금 테스트 `test_goal_write_requires_goal_and_expected_version` 추가 |
| 3 | LOW | 삭제 후 폼 잔존값 dirty 미표시 → 회차 전환 시 소실 | **수정** — `deleteGoal.onSuccess`에서 폼에 내용이 남아 있으면 dirty 마킹 (AiPanel.tsx:1239-1246) |
| 4 | LOW | 늦은 저장 응답이 저장 후 추가 입력된 stash를 삭제 | **수정** — `markBriefSaved(projectId, chapterId, savedForm)`가 stash ≠ savedForm이면 보존 (aiPanelStore.ts:470-485) |
| 5 | NOTE | `EpisodePurpose` 전방 참조 — Python ≤3.13이면 import-time NameError | **수정** — 정의를 모듈 상단으로 이동 (schemas.py:9) |
| 6 | NOTE | stale 배지 문구가 사양의 상위 집합 | 유지 — 정보 추가 방향이며 계약 위반 아님 |
| 7 | NOTE | restore 시 `chapter-goal-history` 추가 invalidate | 유지 — 복원이 이력 row를 append하므로 정합성상 필요 |
| 8 | NOTE | UNIQUE + 비고유 인덱스 중복 (chapter_goals.chapter_id) | 유지 — 무해, ORM `index=True`+`unique=True`와 일치 |

## 검토자 B (agent f7e72416) — baseline 대조·격리·증거 검토

**판정: PASS_WITH_NOTES** — baseline(`c2e4f6a5`, main 작업트리)과 파일별 직접 비교.

확인된 핵심 사실:
- worktree HEAD == `c2e4f6a5` (main tip), 커밋 없음 — D01은 전부 uncommitted working-tree 변경
- `services/manuscripts.py` 133행, `routers/ai_panel.py` 796행, `services/gpt_oauth.py` 81행 **완전 동일** — 생성 경로·CAS·snapshot·provider 계약 무손상
- `Chapter.memo`·`ChapterSnapshot` 경로·EditorPage 메모 UI 동일
- `projects.py` diff = import 확장 + goal 블록 삽입뿐, 기존 엔드포인트 전부 verbatim
- migration 체인 선형·단일 head (`1b2c3d4e5f60` → `2c3d4e5f6a70`), downgrade 완전
- 테스트 파일에 네트워크/subprocess/env/`DATABASE_URL` 패턴 0건, fake provider 재사용
- 포트 15230은 다른 fixture config(15202/15212/15225/15227/15228/15229)와 비충돌
- 잔여 산출물(.db/.key/.env/.eval_tmp) 없음, 하드코딩 credential 없음

| # | 심각도 | 발견 | 처리 |
|---|--------|------|------|
| 1 | LOW | `frontend-tsc.txt` 0바이트 — 증거력 없음 | **수정** — `TSC_EXIT=0` 출력 포함해 재캡처 |
| 2 | LOW | `EpisodePurpose` 전방 참조 (검토자 A와 동일 지적) | **수정** — 위와 동일 |
| 3 | LOW | `manifest.json`이 리서치 단계 상태 그대로 | **수정** — `D01_IMPLEMENTATION_VERIFIED_REVIEWED`로 갱신, 증거 파일 매핑 추가 |
| 4 | INFO | UNIQUE + 비고유 인덱스 중복 | 유지 — 무해 |
| 5 | INFO | backend-full.txt의 `u` 마커 = pytest-subtests 통과 표시 | 확인 완료 — 정합 |

## 검토 후 변경 및 재검증

수정 파일: `backend/app/schemas.py`, `backend/app/routers/projects.py`,
`backend/tests/test_chapter_goals.py`(+1 테스트), `frontend/src/stores/aiPanelStore.ts`,
`frontend/src/components/panels/AiPanel.tsx`, `manifest.json`, `source-hashes.txt`.

재실행 (post-review 증거):
- `backend-d01-focused-postreview.txt` — **47 passed**, `pytest_exit=0`, `violations=[]`, `subprocess_attempts=0`
- `frontend-chapter-goal-postreview.txt` — **8 passed**, tripwire `no escapes`
- `frontend-tsc.txt` — `TSC_EXIT=0` (기록 포함)

최종 source-hashes.txt는 수정 반영 후 sha256을 독립 재계산한 값이다
(검토자 지적 "자가 보고 해시" 우려 해소 — 본 로그 작성 시점에 shell로 재산출).
