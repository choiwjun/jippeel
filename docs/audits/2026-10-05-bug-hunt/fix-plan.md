# 8개 결함 수정 계획 — 2026-10-05

사용자 승인: “모두 수정해. 그리고 커밋 푸시해”. 앞선 조사 보고서의 BUG-01~08 구현 수정·회귀 검증·독립 검토·관련 파일 선별 커밋/푸시가 승인되었다. 운영 DB·실제 provider·credential·migration/배포는 포함하지 않는다.

1. 기존 합성 재현을 정상 동작을 요구하는 회귀 assertion으로 고정한다. Backend는 공식 native 격리 runner, browser는 기존 proxy 없는 fixture 서버의 전용 포트를 사용한다.
2. BUG-01/06: 메타데이터 mutation에 작품·회차·값을 고정하고 pending 메모는 원래 회차로 flush한다. 응답은 해당 상세 캐시에만 병합하며 최신 원고 revision/content를 이전 메타데이터 응답으로 덮지 않는다.
3. BUG-02: 장면 저장에 id와 편집 문자열을 고정한다. 선택한 장면의 편집 내용을 초기화하지 않으며 회차 전환과 늦은 완료를 분리한다.
4. BUG-03: 동일 작품의 기억·근거 회차를 배치 적재해 상위 요약의 출처를 재귀 검증한다. 원문 변경·승인 취소·누락/잘못된 출처는 stale로 전파한다. 목록과 AI 선택에 반영하고 planner/worker의 호출 전후 검증도 연결한다. 기존 승인 이력은 변경하지 않는다.
5. BUG-04: `(volume: null last, sort_order, id)`를 공통 회차 순서로 사용해 AI 이웃·미래 참조와 목록/프론트 정렬을 맞춘다.
6. BUG-05: 회차/전체 내보내기 전 대상 draft coordinator를 저장하고 저장 오류/충돌 시 다운로드를 중단한다.
7. BUG-07/08: lifecycle 참조 회차 삭제는 원고 보존 409로 안내한다. NOT NULL PATCH 필드는 명시적 null을 422로 거부하고 유효한 nullable 필드는 유지한다.
8. 국소 회귀 → 공식 backend 전체 suite → frontend type/build와 합성 browser 회귀 → 읽기 전용 독립 검토. 지적은 수정·재검증한다.
9. 실행 결과와 현재 원장/HANDOFF를 갱신하고 이번 소스·테스트·조사 자료만 선별 stage/commit/push한다. 기존 미추적 작업 자료·DB 백업은 보존한다. 원격 main 변경이 있으면 변경 내용을 확인하고 통합하며 강제 push는 사용하지 않는다.

단일 writer는 현재 에이전트다. 독립 검토자는 읽기 전용으로 작업한다. 기존 UI 구성과 고정 GPT OAuth provider 계약을 유지한다.
