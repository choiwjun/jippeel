# D03-1 RED 로그

- 실행 시점: 구현 전 (`flow_stage` 모델/스키마/라우터/migration 미존재 상태)
- 실행 명령: `backend/.venv/bin/python backend/scripts/run_backend_pytest.py tests/test_chapter_flow.py` (backend/ cwd)
- 관측된 RED:
  - `tests/test_chapter_flow.py` 전 테스트 실패 — `GET /chapters/{cid}/flow`,
    `POST /chapters/{cid}/flow/transition`, `GET /chapters/{cid}/flow/events` 미존재로 404/405,
    `Chapter.flow_stage`·`ChapterFlowEvent` 모델 부재로 직접 세션 호출 테스트도 AttributeError/실패.
  - `test_migrations.py::test_upgrade_head_matches_metadata`는 head `3d4e5f6a7b81` 불일치·
    `chapter_flow_events` 테이블 부재로 실패 상태였고, `test_populated_upgrade_backfills_flow_stage`
    는 backfill 컬럼 부재로 실패.
- GREEN 전환: 구현 후 동일 스위트 `66 passed, pytest_exit=0` (backend-focused.txt 참조).
- 프론트 RED: `chapter-flow.spec.ts`는 `ChapterFlowControl`·API 타입 미존재 상태에서
  작성됐고(전이 select/badge/앵커 selector 미존재), 구현 후 6 passed.

이 파일은 사후 기록이다 — 당시 콘솔 출력 원본은 요약 이력(hist_504b9352)에 있다.
