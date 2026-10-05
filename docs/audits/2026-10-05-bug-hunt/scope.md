# 플랫폼 버그 조사 범위 — 2026-10-05

사용자 요청: “이 플랫폼의 버그찾아줘”. 기존 구현에서 재현되는 결함을 찾고, 발생 조건·영향·코드 위치·검증 근거를 보고한다.

- 조사 대상: 회차와 장면 편집·저장·내보내기, 프로젝트/회차 삭제, AI 컨텍스트의 회차 순서, 계층 기억의 원문 변경 전파, 입력 검증.
- 방법: 현재 코드와 기존 테스트 검토 → 공식 격리 runner 사전 검사 및 전체 backend 테스트 → 합성 DB/API 및 브라우저 fixture로 후보 재현 → 확인된 결함 보고.
- backend는 `tests.isolation_guard`를 앱 import 전에 설치하고 합성 TEMP SQLite를 사용한다. 브라우저는 proxy 없는 fixture 전용 포트와 합성 API를 사용한다.
- 산출물: 이 범위 문서, 재현 스크립트, 실행 결과, 최종 조사 보고서와 HANDOFF 진입점.
- 이번 요청은 결함 조사 범위다. 구현 수정·migration·배포·Git 게시·실제 provider/credential·운영 데이터 접근은 수행 대상에 포함하지 않는다.

기준 문서: `AGENTS.md`, `docs/handoffs/2026-09-08-remaining-work.md`, `docs/DOCUMENT_STATUS.md`, `HANDOFF.md`, `docs/runbooks/isolated-backend-tests.md`.

후속 승인: 사용자의 “모두 수정해. 그리고 커밋 푸시해”에 따라 조사에서 재현한 8건의 수정·회귀 검증·독립 검토·선별 commit/push로 범위를 확장했다. 상세는 [수정 계획](fix-plan.md)과 [최종 수용](acceptance.md)에 기록한다. 위 조사 시점의 실행 경계는 역사 기록이다.
