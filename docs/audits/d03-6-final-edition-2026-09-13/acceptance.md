# D03-6 수용 문서 — 완결본 관리 (완결 점검표 + 완결본 스냅샷)

날짜: 2026-09-13 / 슬라이스: D03-6 / 사양: [d03-6-final-edition-spec.md](../../superpowers/plans/2026-09-13-d03-6-final-edition-spec.md)

## 수용 범위

§6.2 "완결 분리 … 완결본 관리"의 잔여분 + 감사 §8.2 "완결 점검표 … 완결본 스냅샷 생성"을 좁은 단위로 수용한다.

- **`project_final_editions`** (migration `7b8c9d0e1f25`, head): 명시적 POST로 생성하는 불변 스냅샷 — 조립 원고 `content_md`(`## 제목` 절, sort_order+id 순), 회차 `manifest_json`, 동결 `checklist_json`, 캡처 시점 `serial_state` 기록. UPDATE 경로 없음, 삭제만 명시적.
- **`GET /projects/{pid}/completion-checklist`**: 파생 읽기 — 회차 단계별 집계·미확정 수, 복선 open 목록(설치만) + 처분 4버킷(resolved/intentional_unresolved/side_story/closed_unclassified), 미수용 윤문 수, 파손 근거 링크 수, ending_intent 없는 series_finale 목표. 자동 완결 판정 없음.
- **프론트** `/projects/:pid/completion`: 점검표 카드·배지 + 완결본 생성(라벨 선택)·목록·상세(매니페스트+원고 전문)·삭제. 홈 카드 "완결 관리" 링크.

## 계약 검증

- 스냅샷 불변성: 캡처 후 원고 수정·회차 삭제·복선 추가해도 `content_md`·`checklist_json`은 캡처 시점 값 유지(테스트로 단정).
- 조립 순서: sort_order(동률 시 id) — 생성 순서와 무관함을 역순 시드로 단정.
- `serial_state`는 캡처 시점 기록 — completed 게이트 아님(연재 중 스냅샷도 허용).
- POST는 BEGIN IMMEDIATE writer lock, BUSY→409; 목록은 메타만; detail/삭제는 타 프로젝트 404.
- 점검표는 사실 나열만 — 완결 가능 판정·자동 분류 없음(§6.3).

## 검증 결과

| 항목 | 결과 |
|------|------|
| backend 집중 | **31 passed** (test_final_editions + test_migrations) |
| backend 전체 | **605 passed, 1 skipped**, isolation violations 0 |
| frontend final-edition fixture | **6 passed**, tripwire 0 (port 15235) |
| frontend 회귀 fixture | chapter-goal 8·chapter-flow 10·preservation 26·ai-context 15·memory 31·serial-state 6·evidence-links 8·foreshadow-disposition 7 — 전부 green |
| TypeScript | TSC_EXIT=0 |
| 독립 검토 | backend·frontend 각 PASS_WITH_NOTES — 지적 19건 중 9건 수정·10건 수용 ([review-log.md](review-log.md)) |

격리: 합성 TEMP SQLite·fake keyring·fixture 전용 포트만 사용. 운영 DB·실제 provider·credential·배포 없음.
알려진 경고: `wordcount.py:30` SyntaxWarning(선존, 무관).

## 수용하지 않은 것(범위 밖)

- 완결본의 복원(restore-to-chapters) — 읽기 전용 보존만.
- 결말 후보(project ending) 저장·변경 영향 표시 — 다음 슬라이스(D03-7).
- 자동 완결 판정·자동 스냅샷 — 금지 유지.

## 상태

로컬 구현·검증 완료. **uncommitted 유지** — 커밋·푸시·운영 migration 적용은 별도 승인 대기.
