# D01 회차 목표 영속화 — 최종 수용

수용일: 2026-09-13 · worktree `d01-contract-analysis` · branch `choiwjun/d01-contract-analysis`
base `c2e4f6a5` (== main tip). **D01 변경은 uncommitted working-tree 변경** — commit/push 없음.

## 수용 범위

승인된 좁은 사양 [2026-09-13-d01-detailed-spec.md](../../superpowers/plans/2026-09-13-d01-detailed-spec.md)
(Q1~Q7 추천안 채택, Q2=option B: 현재값 + append-only 이력 + 최소 목록·복원)의 구현·검증·독립 검토.

- 회차당 목표 1행(`chapter_goals`) + 이력(`chapter_goal_revisions`, `UNIQUE(chapter_id, goal_version)`)
- `goal_version` 단조 증가 — 삭제 후 재생성도 `max(current, history_max)+1`
- `episode_purpose`를 목표와 함께 저장·복원 (`serial|volume_end|series_finale` CHECK)
- API: GET/PUT/DELETE `/chapters/{cid}/goal`, GET `.../goal/history`, POST `.../goal/restore`
- CAS: `expected_goal_version` 필수 — 불일치 409 `{code:"goal_version_conflict", current_goal_version}`
- SQLITE_BUSY → 409 (저장·복원·삭제 쓰기 경로 전부)
- 프론트: 회차별 미저장 작업본 보존, 늦은 응답 격리, 명시적 불러오기/저장/이력/삭제,
  저장본 vN·기준 rM 배지 + stale 원고 안내, Sheet 접근성 이름

## 보존 확인 (검토자 B가 baseline과 직접 대조)

- `services/manuscripts.py`, `routers/ai_panel.py`, `services/gpt_oauth.py` — **전행 동일**
- 목표 저장·복원·삭제가 `Chapter.revision` 증가·`ChapterSnapshot` 생성을 하지 않음 (테스트 검증)
- `Chapter.memo` 미사용·미변경 — 별도 도메인
- 생성 요청은 메모리 폼(`episodeBrief` + 현재 directive)만 사용 — 저장본 자동 주입 없음
- 고정 GPT OAuth provider 계약(`gpt-5.6-luna`/`xhigh`) 무손상, 모델 선택 UI 미복귀
- 자동저장·목표 달성 자동 판정·작품 공통 목표 없음 (스코프 크리프 0)

## 검증 증거 (docs/audits/d01-goal-contract-2026-09-13/)

| 증거 | 결과 |
|---|---|
| backend-red.txt | RED 정직 기록 — `ImportError: ChapterGoal`, `pytest_exit=1` |
| backend-d01-focused.txt | 38 passed · `pytest_exit=0` · violations=[] · subprocess 0 |
| backend-d01-focused-postreview.txt | **47 passed** (검토 수정+잠금 테스트 후) · exit0 · violations=[] |
| backend-full.txt | **520 passed / 1 skipped / 70 subtests** · exit0 · violations=[] · subprocess 0 |
| frontend-chapter-goal-fixture.txt | 8 passed · tripwire no escapes |
| frontend-chapter-goal-postreview.txt | **8 passed** · no escapes |
| frontend-regression-ai-context.txt | 15 passed · no escapes |
| frontend-regression-memory.txt | 31 passed · no escapes |
| frontend-tsc.txt | `TSC_EXIT=0` (출력 포함 재캡처) |
| source-hashes.txt | 검토 후 변경분 포함 17개 sha256 재계산 |

fixture 커버: 정규화 PUT+expected 버전, 재진입 hydrate+purpose 복원, 회차별 작업본 보존,
늦은 응답 격리, 409 입력 유지, 이력 복원(새 버전), 삭제 확인→미저장, axe serious/critical 0.

## 독립 검토 — [review-log.md](review-log.md)

- 검토자 A(7e242186) 계약·정적 검토: **PASS_WITH_NOTES** — LOW 4 + NOTE 4
- 검토자 B(f7e72416) baseline 대조·격리·증거: **PASS_WITH_NOTES** — LOW 3 + INFO 2
- 차단 결함 0. LOW 전부 수정(필수 필드·BUSY 매핑·dirty/stash 보존·전방 참조·증거 로그·manifest)
  후 post-review 재실행 전부 통과.

## 수용하지 않는 것 (게이트 유지)

- 운영 DB migration·배포·실제 적용 (G01) — 합성 TEMP DB에서만 검증
- 실제 provider/계정/credential 호출 (G02/G03) — fake provider만 사용
- 지정 Windows 실기기 수용 (G04) — fixture는 실기기 수용이 아님
- commit/stage/push — 별도 게시 승인 경계 (변경은 worktree에 uncommitted 상태)
- 작품 공통 목표, 자동 목표 달성 판정, 자동저장, provider/모델 선택 UI — 범위 밖 유지

## 잔여 참고 (비차단, 후속 선택)

- `chapter_goals.chapter_id`의 UNIQUE+비고유 인덱스 중복 — 무해, 추후 migration 정리 가능
- stale 배지 문구는 사양의 상위 집합 표기 — 계약 위반 아님
