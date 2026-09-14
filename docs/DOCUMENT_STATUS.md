# 문서 상태 인덱스

최종 대조: 2026-09-14(KST)

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
| 자동 요약/backfill | [별도 설계](superpowers/plans/2026-09-11-long-memory-auto-summary-backfill.md) / [운영 runbook](runbooks/summary-backfill-operations.md) | worker·provider 어댑터·실 브릿지 smoke 완료(draft-only). 아크 요약은 [계층 기억 설계](specs/2026-09-14-hierarchical-memory-500ep.md). 운영 실행·승인 UI 통합 잔여 |
| 운영 적용 절차 | [release runbook](runbooks/long-memory-governance-release.md) | 준비 문서이며 실행 승인 아님 |
| 자문 결정 | [Astra 기록](decisions/2026-09-11-astra-long-memory-release.md) | 자문일 뿐 실행 승인 아님 |
| 실패 계약·테스트 격리 최종 수용 | [B01/B02/B04 수용 기록](audits/failure-contracts-2026-09-12/b04-review-fixes.md) | 새 419P/외부 skip1, 독립 검토 2건 PASS, 보존 근거와 사고 한계. C13 완료 |
| 기억 화면 보정 최종 수용 | [M01~M05 수용 기록](audits/memory-m01-m05-2026-09-12/acceptance.md) | backend421P/기존 skip1·frontend72P, 변경범위 coverage·독립 검토 2건 PASS, 복구·보존 한계 |
| 품질 지표 B03 최종 수용 | [수용·검증·실패 이력](audits/quality-b03-2026-09-12/acceptance.md) / [계약](superpowers/plans/2026-09-12-quality-metric-corrections.md) | backend482P/기존 skip1·frontend77P·국소coverage·독립 E1종결2PASS. 가중치/API/이력 유지 |
| D01 목표 저장 조사·요구 선택 | [질문·근거](superpowers/plans/2026-09-13-d01-contract-questions.md) | 조사 문서 — 구현은 아래 D01 수용 행으로 종결 |
| 후속 순차 진행 승인 | [잔여 순차 실행](superpowers/plans/2026-09-12-remaining-sequence.md) | M01~M05/B03/D01/D03/D04-1 수용 완료로 순차 계약 종결. 잔여는 사용자 수용 + D02/D04 후속·G 게이트 잔여 영역 |
| 지원 backend 테스트 실행 | [격리 runner 가이드](runbooks/isolated-backend-tests.md) | `backend/scripts/run_backend_pytest.py`가 공식 진입점. direct pytest는 fail-closed |
| D01 회차 목표 영속화 수용 | [수용](audits/d01-goal-contract-2026-09-13/acceptance.md) | 목표 저장·이력·복원 계약. backend47P/전체520P, fixture·독립 검토 통과 |
| D03 집필 수명주기 전 단위 수용 | D03-1 [flow](audits/d03-1-flow-stage-2026-09-13/acceptance.md) · D03-2 [resume](audits/d03-2-resume-2026-09-13/acceptance.md) · D03-3 [serial](audits/d03-3-serial-state-2026-09-13/acceptance.md) · D03-4 [근거](audits/d03-4-evidence-links-2026-09-13/acceptance.md) · D03-5 [이관](audits/d03-5-foreshadow-disposition-2026-09-13/acceptance.md) · D03-6 [완결본](audits/d03-6-final-edition-2026-09-13/acceptance.md) · D03-7 [결말영향](audits/d03-7-ending-impact-2026-09-13/acceptance.md) | 흐름 상태 기계·재개 파생·연재 상태·근거 링크·이관 구분·완결본 스냅샷·결말 영향. 전부 독립 검토 2건 통과 |
| D04-1 summary_jobs/fake worker 수용 | [수용](audits/d04-1-summary-worker-2026-09-13/acceptance.md) | 서비스 계층. idempotency·draft-only memory·retry/recovery. 실제 provider smoke는 d04-2 수용 완료 |
| V02 복원 실패 주입 수용 | [수용](audits/v02-restore-verify-2026-09-13/acceptance.md) | 합성 TEMP 백업/검증 9종 실패 코드 15P. 실제 운영 복원·wrong-key는 G01/G03 |
| V04 외부 metrics 버전 검증기 수용 | [수용](audits/v04-metrics-version-2026-09-13/acceptance.md) | AST 전용 계약 비교 20P + **09-14 실물 파일 대조 완료** — Windows 측 실제 metrics_v2.py 전 항목 일치 |
| G-045 audience_knows 유실 수정 수용 | [수용](audits/g045-audience-knows-2026-09-13/acceptance.md) | foreshadow POST 1행 수정. RED 재현→수정→677P 회귀. 독립 검토 PASS |
| V01 프론트 coverage 계측 수용 | [수용](audits/v01-frontend-coverage-2026-09-13/acceptance.md) | PW_COVERAGE=1 opt-in V8 수집→fs 경로 키 union 병합. 11 스위트 128P·측정값 lines 83.27%. 임계 주장 아닌 측정 인프라 |
| G01 실 DB migration·G03/G04 부분 실행 | [수용](audits/g01-production-migration-2026-09-13/acceptance.md) | 실 DB head `9d0e1f2a3747` 적용·데이터 보존 검증(이후 `d1e2f3a4b5c6`까지 추가 적용). 실 crypto 경로 wrong-key 거부·Windows 네이티브 스위트 714P·실기동 프로브(54,300자 43ms). 브라우저/NVDA 수동 실기기·브릿지 로그아웃 잔여 |
| U01~U04·O01~O03·O05·V03·D04 어댑터 실행 수용 | [수용](audits/uo-options-v03-2026-09-13/acceptance.md) / O01 [사양](specs/2026-09-13-o01-card-png-novelwriter-import.md) · O02 [사양](specs/2026-09-13-o02-auto-backup.md) · O03 [사양](specs/2026-09-13-o03-writing-activity.md) | card_json UI·로어 참조 회차·uiScale·카드 PNG/novelWriter·자동 백업·활동 캘린더. O05 ResourceWarning 근본 수정(warnings 0)·V03 다중 프로세스 PASS·summary 실제 provider 어댑터 7P. 전체 721P |
| 플랫폼 AI 규정 재확인 | [규정추적_2026-09-13](../규정추적_2026-09-13.md) | 노벨피아 순수창작/이벤트 AI 금지·약관 시행 8-13 확인, 문피아 신규 AI 공지 없음, 조아라 명문 부재 지속. 게시 전 재확인 필요 |
| G04 실제 브라우저·NVDA 최종 검증 | [최종 수용](audits/g04-real-browser-2026-09-14/acceptance.md) | mock 없는 실제 e2e 10/10 — 실 dist+실 uvicorn+실 DB 복사본. 키보드 Tab·uiScale 실 DOM·5만 자 입력→자동저장 왕복 실증. SPA fallback 결함 발견·수정. **NVDA 실제 음성 발화·포커스 순환·콤보박스 값/상태 발화 실증**, 지정 장치 최종 사인오프 완료 |
| 계층 기억 2차 슬라이스 (권 기억·커버리지) | [설계](specs/2026-09-14-hierarchical-memory-500ep.md) | `kind='volume'` job→`volume_memory` draft(migration `e2f3a4b5c6d7`, `volume-v1`), 승인 상위 층의 하위 요약 커버리지 제외. backend 800P |
| 인지·상태 도메인 설계 | [설계](specs/2026-09-14-cognitive-state-domain.md) | 작가/독자/인물별 knowledge_states + 사건/관계 event_impacts. 설계만 — 구현은 P1~P4 별도 슬라이스 |
| 생성 기억 평가 manifest | [manifest](specs/2026-09-14-summary-eval-manifest.md) | 공통 M1~M6 + 종류별 S/A/V 체크리스트 + JSONL 평가 기록 형식. draft 승인/폐기 판정 기준 |
| 운영 backfill 실행 도구 | `backend/scripts/summary_backfill.py` + [runbook](runbooks/summary-backfill-operations.md) | 계획(provider-free·멱등) + `--run --limit` 실행. 운영 DB 계획 검증 완료(300 skipped_empty, 재실행 전량 duplicate) |
| G02 실제 provider 6-case 파일럿·독립 AI blind 2회 | [수용](audits/g02-pilot-2026-09-14/acceptance.md) · [독립 평가](audits/g02-pilot-2026-09-14/independent-blind-evaluation-2026-09-14.md) | 실제 openai-oauth 브릿지(gpt-5.6-luna) 경유 실 호출 6/6 완결. SSE 2,803건·usage·latency·DB 해시 동일·marginal $0. 독립 AI evaluator A/B 2회: hard-block 없음·축별 lower median 3 이상·최대 차이 1점. 인간 평가자 대체 여부와 작가 accept는 정책/사용자 결정 |
| G03 OAuth 로그아웃·credential 복구 시연 | [최종 범위 수용](audits/g03-oauth-logout-2026-09-14/acceptance.md) | stop→포트 종료·credential 제거→브릿지 기동 거부·복원→실 호출 성공 전 주기 실증. 임시 사본 파기. 서버 측 세션 폐기·완전 재로그인은 bridge 미지원 계정 소유자 선택으로 비차단 분리 |
| G02·G03·G04 병렬 Windows 세션 기록 | [기록](audits/g02-g03-g04-user-actions-2026-09-14/acceptance.md) | Documents checkout 병행 세션(ZCode)의 독립 실행 — 최소 smoke·bridge 재기동·NVDA 2026.1.1 설치·4개 화면 UIA 트리 확인 PASS_WITH_NOTES. 발화·순환 갭은 g04 디렉터리의 speech evidence로 보완 |
| 다른 PC 접근 최소 범위 | [LAN 접속 runbook](runbooks/cross-pc-access.md) | A PC 운영 서버의 LAN 바인딩·접속 주소 출력. B PC는 같은 네트워크에서 동일 SQLite DB를 사용. 로그인·클라우드·인터넷 공개는 범위 밖 |
| 작가 피드백 자가개선 설계 | [전체 설계](specs/2026-09-14-author-feedback-improvement.md) / [E1 사양](specs/2026-09-14-e1-generation-runs-spec.md) | 제안→승인→적용 순서, 작품별 완전 분리. E1(생성 이력)~E7(규칙 UI) 단위 분할 |
| E1·E2 생성 이력+작가 처분 수용 | [수용](audits/e1-generation-runs-2026-09-14/acceptance.md) | generation_runs/outputs append-only·3 surface SSE 기록·generation_saved 이벤트·outcome 상태 기계·프론트 명시 액션 계측. 신규 12P·전체 738P |
| E3~E7 자가개선 전 단계 구현 | [설계](specs/2026-09-14-author-feedback-improvement.md) | E3 결정론 diff 분석·E4 improvement_rules·E5 제안 job(proposed만)·E6 승인 규칙 주입·E7 규칙/이력/폐기 UI. migration `c04b5d6e7f81` |
| 계획→승인→집필 흐름 | HANDOFF §09-14 대량 슬라이스 | `POST /ai/plan`·approved_plan 주입·assistant plan-next·generate-next draft-only·`apply` CAS. 기존 원고 자동 덮어쓰기 없음 |
| D04 실제 provider smoke | [수용](audits/d04-2-summary-smoke-2026-09-14/acceptance.md) / [운영 runbook](runbooks/summary-backfill-operations.md) | 실제 OAuth 브릿지 경유 draft_saved·자동 승인 없음 |
| D02·500화 계층 기억 1차 | [설계](specs/2026-09-14-hierarchical-memory-500ep.md) | 아크 요약 슬라이스 — `summary_jobs.kind='arc'`·`arc_summary` MemoryEntry·migration `d1e2f3a4b5c6`. 권 기억·커버리지 선택은 후속 |

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
