# 문서 상태 인덱스

최종 대조: 2026-09-13(KST)

## 역할과 현재 기준

| 역할 | 문서 | 사용 범위 |
| --- | --- | --- |
| 현재 작업 상태 — 단일 원장 | [전체 작업 현황](handoffs/2026-09-08-remaining-work.md) | 완료/미수정/미구현/미검증/승인 대기/선택 확장, 우선순위와 종결·이관표 |
| 최종 인계·Git 게시 승인 | [9월 13일 통합 인계](handoffs/2026-09-13-commit-handoff.md) | 완료·검증·D01 제안과 미선택·다음 단계·선별 게시/로컬 보존 경계. Git 승인은 기능/운영 승인과 별도 |
| 진입점·작업 이력 | [HANDOFF.md](../HANDOFF.md) | 현재 원장 링크와 날짜별 실행·승인 기록. 과거 “다음 작업”은 현재 지시가 아님 |
| MVP 제품 사양 | [대시보드_MVP_사양.md](../대시보드_MVP_사양.md) v0.6 | 제품 계약. 오래된 백로그의 실행 상태는 원장 참조 |
| GPT OAuth provider 설계 | [기술설계](../기술설계_GPT_OAuth_브릿지_v1.md) | 고정 OAuth provider와 credential 소유 경계 |
| 장편 기억 제품 사양 | [governance 사양](superpowers/specs/2026-09-11-long-memory-governance.md) | 기능·데이터·UI 계약. M01~M05 수용 완료; 확장·운영은 원장 참조 |
| 장편 기억 구현·검증 이력 | [follow-up 계획](superpowers/plans/2026-09-11-long-memory-followup.md) | 기반 구현 및 승인 P1 네 건의 완료·독립 검토 근거 |
| 자동 요약/backfill | [별도 설계](superpowers/plans/2026-09-11-long-memory-auto-summary-backfill.md) | provider-free planner만 완료. worker/schema/provider/운영은 원장 D04와 G gate |
| 운영 적용 절차 | [release runbook](runbooks/long-memory-governance-release.md) | 준비 문서이며 실행 승인 아님 |
| 자문 결정 | [Astra 기록](decisions/2026-09-11-astra-long-memory-release.md) | 자문일 뿐 실행 승인 아님 |
| 실패 계약·테스트 격리 최종 수용 | [B01/B02/B04 수용 기록](audits/failure-contracts-2026-09-12/b04-review-fixes.md) | 새 419P/외부 skip1, 독립 검토 2건 PASS, 보존 근거와 사고 한계. C13 완료 |
| 기억 화면 보정 최종 수용 | [M01~M05 수용 기록](audits/memory-m01-m05-2026-09-12/acceptance.md) | backend421P/기존 skip1·frontend72P, 변경범위 coverage·독립 검토 2건 PASS, 복구·보존 한계 |
| 품질 지표 B03 최종 수용 | [수용·검증·실패 이력](audits/quality-b03-2026-09-12/acceptance.md) / [계약](superpowers/plans/2026-09-12-quality-metric-corrections.md) | backend482P/기존 skip1·frontend77P·국소coverage·독립 E1종결2PASS. 가중치/API/이력 유지 |
| D01 목표 저장 조사·요구 선택 | [질문·근거](superpowers/plans/2026-09-13-d01-contract-questions.md) | 소스 조사 완료, 최신값/과거 목표 조회·복원 범위 결정 대기. 상세 사양·구현 미착수 |
| 후속 순차 진행 승인 | [잔여 순차 실행](superpowers/plans/2026-09-12-remaining-sequence.md) | M01~M05/B03 수용 완료, 다음 D01/D03/D04 상세 계약·기획. 실제 자원은 개별 gate 충족 후 |
| 지원 backend 테스트 실행 | [격리 runner 가이드](runbooks/isolated-backend-tests.md) | `backend/scripts/run_backend_pytest.py`가 공식 진입점. direct pytest는 fail-closed |

## 기록 문서의 해석

- `audits/`의 조사·검증·fixture·review는 작성 당시 범위의 증거다. 오래된 행 번호,
  실패/보류 판정, 검증 수치를 현재 상태로 복사하지 않는다. 과거 감사 내용은 보존한다.
- `handoffs/2026-09-08-remaining-work.md`는 기존 경로를 유지한 **현재 원장**이다.
  하단의 별도 “보존된 2026-09-08 인계 원문”만 역사적 기록이다.
- 2026-09-07~08 AI context 계획/사양과 `고도화_사양_완성도_v1.md`는 설계 근거다.
  이미 구현된 로어 자동 주입·장면·기본 canon을 다시 백로그로 열지 않는다.
- `QA_개발검증_리포트_v3.md`, `테스트플랜_v1.md`, `gates.json`, `traceability.json`의
  오래된 수치·빈 매핑·G7/G8 pass는 현재 전체 기능/운영 수용 판정이 아니다.
- `QA_수동검증_가이드.md`는 역사적 체크 항목 참고용이다. 현재 실행 준비는
  [Windows QA 계획](audits/windows-device-qa-plan-2026-09-10.md)과 원장 G04를 따른다.
  구형 API key UI·기본 DB/port·revision 없는 저장 명령을 그대로 사용하지 않는다.
- `릴리스_노트_MVP_v1.0.md`의 v1.0/v1.1은 과거 release 기록, v1.2는 미릴리스 변경 요약이다.
- `진행중_리서치.md`와 플랫폼/장르 리서치는 최신 정책·시장 근거가 아니다.
  실제 배포·게시 판단에 사용하려면 별도 출처 확인이 필요하다.

## 이번 대조에서 바로잡은 상태

- 이 인덱스가 최신으로 표시하던 backend 108 passed / 전체 외부 script 9건 실패는
  P1 최종 수용보다 오래된 기록이었다. 최신 수치·검증 범위는
  [원장 §9](handoffs/2026-09-08-remaining-work.md#9-검증-수치의-최신성과-근거)에만 모은다.
- 임시 SQLite 백업/복원과 migration rollback/re-upgrade는 완료했다.
  남은 실제 DB/credential/교체 검증과 같은 작업으로 묶지 않는다.
- `ai_endpoints`와 hidden compatibility routes는 보존·migration 호환용이다.
  제거한 endpoint/API key/base URL·모델 선택 UI를 미구현 기능으로 되살리지 않는다.
- 최초 문서 대조 후 승인된 B01/B02 구현과 B04 보강·새 테스트 실행까지 완료했다. 최종 수용 기록과 원장 C13을 따른다. 당시 운영 작업·Git 반영은 하지 않았다. Git 게시만 9월 13일 별도로 승인받았다.
