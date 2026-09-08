# AI 집필 맥락 정리 — 착수 기록

## 현재 단계
사용자가 제안 범위 설명 후 “작업진행해”로 구현 진행을 승인했다. 조사 완료; 승인된 범위의 상세 계약·구현 계획 작성과 기준선 재검증 중이다.

## 요청 해석
사용자의 “진행해”는 직전 권고인 **AI 집필 맥락 정리**를 다음 개발 단위로 진행하라는 뜻으로 해석한다. 운영 배포/실제 DB 마이그레이션이나 전체 후속 로드맵 승인이 아니다.

## 조사 범위
- 단일·병렬 생성 및 검사 경로의 작품/회차/문체/기획/인물 관계/설정 전달.
- 일반 연재화·권말·최종화 목적과 집필/검사 지침의 정합성.
- 이번 화에서 작가가 허용한 복선 회수·공개와 현재 사실/미래 계획 구분.
- 기존 원고 보존 계약을 유지하며 구현 가능한 최소 공통 구조와 시험 조건.

## 경계
- 소스 변경 전 접근안과 상세 설계를 제시하고 승인받는다.
- 시점별 작품 기억 시스템, 전체 기획/완결 관리 화면, 새 모델/의존성/외형 개편은 별도 범위다.
- 운영 DB/WAL/SHM, 기존 서비스, 실제 AI 엔드포인트를 사용하지 않는다.
- 원고 보존 완료 브랜치와 기존 미커밋 문서를 보존한다. 별도 구현 브랜치는 설계 승인 후 정한다.
- 조사 결과는 문서로만 남긴다. native Windows 시험 환경을 유지한다.

## 진행
- 공통 맥락 전달 경로와 집필/검사 지침 계약을 별도 읽기 전용 조사자로 나누어 확인 중이다.
- 기존에 확인된 모델 가용성에 따라 조사 모델은 openai-codex/gpt-5.5를 사용한다(요청된 ox-alpha-free 미가용의 기존 대체 경로).
- 조사 결과를 합친 뒤 최소 접근안과 상세 설계 범위를 제안한다. 소스 구현은 아직 시작하지 않았다.

- 맥락 전달 조사 완료: ai-context-flow-research.md. 현재 회차 누락 가능성, 소속 검증 분산, 병렬 문체 누락, 관계 미전달 등을 정적으로 확인했다. 런타임 재현/테스트 결과가 아니며 지침 계약 조사와 함께 상세 설계 범위를 결정한다.

- 지침 계약 조사 완료: ai-context-directives-research.md. 일반화 후크/미해결 지침이 최종화에도 적용되고, 승인된 복선 회수 예외가 생성·감수·검사에 공유되지 않는 것을 정적으로 확인했다.

## 사용자에게 제안할 접근
1. 프롬프트 문구만 수정: 작지만 회차 누락/병렬 불일치/소속 검증 문제를 남긴다.
2. **공통 요청·맥락 조립 + 최소 목적/회수 선택(추천)**: 현재 회차 식별과 본문 포함 여부를 분리하고, 같은 작품 소속을 검증한다. 단일/병렬 생성·감수·모순 검사에 공통 문체/목적/관계/복선 허용 계약을 전달한다.
3. 시점별 기억/기획 DB까지 통합: 다음 단위까지 범위가 커지므로 이번에는 제외한다.

추천 기본 동작: 일반 연재화가 기본이며 권말/최종화는 명시적으로 고른다. 승인된 공개/회수는 요청 단위 허용이며 복선 상태를 자동 변경하지 않는다. 선택 인물의 관계 포함을 표시하고 본문 전송 선택을 존중한다. 영속 회차 목표/역사 기억 시스템은 만들지 않는다.

다음 단계: 사용자에게 추천 접근의 범위·제외 항목·검증 조건을 제시하고 승인받은 뒤 상세 사양과 구현 계획을 확정한다. 아직 코드 수정·테스트 실행·운영 적용은 없다.

## 구현 승인과 실행 결정
- 승인 근거: 공통 맥락/회차 연결·소속 검증·문체/관계·회차 목적·복선 허용의 범위와 전면 재작성 아님을 설명한 뒤 사용자가 “작업진행해”라고 지시했다. 같은 범위의 진행 승인을 다시 묻지 않는다. 새로운 범위/운영 부작용은 별도 승인 대상이다.
- Ruling: 기존 Windows 체크아웃의 새 로컬 브랜치 feat/ai-context-consistency를 사용한다. 원고 보존 브랜치는 유지하고 작업트리는 별도 생성하지 않는다 — 신규 worktree 동의가 없고 native 환경 경로를 보존하기 위해 — 비용: 변경 전환 시 기존 미커밋 문서를 계속 보존해야 한다.
- Base: 70ec67e. native backend222/build 기준선을 임시 DB로 재확인 중이다.
- 원고 보존 코드 수정은 회차 맥락 요청의 저장 완료/오류 연결에 필요한 최소 호출부에 한정하고 기존 coordinator 내부 동작은 재작성하지 않는다.
- 상세 문서→계약 일관성 검토→작업별 구현/독립 검토→실제 격리 통합/최종 검토 순으로 진행한다.

- 새 브랜치70ec67e 기준선 재검증: native Windows 임시 DB backend222 passed/1기존경고, frontend build exit0(기존 Vite build 중복키 경고). 출력 ai-context-baseline-backend.txt 및 ai-context-baseline-build.txt.
- 상세 설계/계획 초안 담당 ai-context-spec-planner(sub-f3b84711) 작업 중. 원본 소스 변경은 아직 없다.

- 사용자 재차 “진행해” 지시: 승인 범위 그대로 연속 진행한다. 계획 초안 작성과 독립 기준선 문제 재현을 병행한다. ai-context-baseline-prober는 새 임시 DB/가짜 LLM의 재현 증거만 작성하며 기능 소스를 수정하지 않는다.

## 문제 재현과 사양 검토
- 기준선 재현 완료: `ai-context-baseline-probes.md/.json`. 임시 SQLite+TestClient+가짜 LLM에서 다른 작품 선택 인물/로어 혼입, 명시 project/chapter 불일치 혼합, 선택 관계 누락, 병렬 planner/workers/reviewer 문체 누락을 실제 전달 메시지로 확인했다. 실제 모델 품질/브라우저 동작을 검증한 것은 아니다.
- 사양 초안 검토 후 `ai-context-contract-rulings.md`에 수정 지시 기록: 저장 충돌 코드 통일, 불필요한 관계범위 옵션 제거, canon flush/입력 revision+hash 고정, 시작 전 비동기 취소·중복 방지, 복선 설치/회수 미래 시점 분리.
- `ai-context-contract-preflight`가 독립 코드/계약 검토를 시작한다. 사양/계획 최종 버전의 SHA256으로 검토 대상을 고정한 후 T1에 진입한다. 소스 구현은 아직 시작하지 않았다.

- 독립 사전 검토: NEEDS FIXES. 최초 초안에 기존 부모 수정 지시 R1–R6 미반영과 제공자 호출 전 검증 회귀 테스트 R7 부족을 확인했다. 작성자가 사양/계획을 동시 수정 중이며 최종 파일 hash 고정 후 재검토한다. 실제 소스 구현은 아직 미착수다.

- 작성자 수정 완료: SPEC SHA256 `a7c4cf0309268369cc455914531e83aa8720fe65b9c8cb28e9c47a999a6eab2c`, PLAN SHA256 `d301b04bad3821b91982192faf7025f3e52a14899147aecb3aadf5ca78607c7a`. 최종 파일을 고정하고 R1–R7 및 작업 간 인터페이스 재검토를 요청했다.

- 사전 검토 R1–R7 주요 수정 반영 확인. 남은 A1–A3(작업1 canon 라우터 파일 권한, 목적 문구의 T2 경계, await 전 전체 폼 복사/취소 연결)을 부모가 제한적으로 문서 보완했다. 최종 보완본을 독립 재검토 중이며 T1 핸드오프를 준비했다.

## T1 구현 착수
- 사전 검토 최종 PASS: R1–R7 및 A1–A3 해소. `ai-context-preflight-review.md`의 SPEC/PLAN hash를 부모가 대조했다.
- 부모가 승인된 범위의 상세 계약을 확정했다. 새 backend implementer가 T1만 구현하고, 이후 독립 task review로 실제 diff/테스트를 확인한다. 목적/복선 의미 지침 T2, 프론트 T3, 실제 통합 QA T4는 후속 순차 작업이다.

- 계획/재현/사전 검토 문서 commit `49b813933d2c5d11a1a811ce42b742f615f698f8`. T1 작업자 `ai-context-backend-context-impl` (`sub-12be2769`), 리뷰 기준도49b8139. 구현자는 소스/테스트 한정 소유, 부모 승인 전 커밋 금지. 완료 보고 뒤 새 독립 task reviewer를 배정한다.

- T1 구현자 완료 보고: focused18/owned49/full backend240 통과(임시 DB·가짜 LLM); 아직 독립 승인 전이다. 고정 diff와 새 파일 전체를 `ai-context-task-1-review-diff.txt`에 기록했다. 독립 `ai-context-task-1-reviewer` (`sub-5a22485d`)가 Spec/Quality 실제 diff 검토와 native owned tests를 진행한다. 원 구현자 `sub-12be2769`는 수정 대기, 아직 커밋 없음.

- T1 독립 검토: owned49 통과했으나 Spec/Quality NEEDS FIXES. F1: 현재 identity 없이 approved_foreshadow_ids만 전달하면 작품 추론/여러 작품 혼합 차단과 복선 참조 회차 소속 검증이 빠지는 경로를 테스트로 재현했다. 부모가 확인 후 원 구현자에 fix round1 배정, 프로젝트 의존 맥락 조립 이전 추론 및 gen/parallel no-provider 회귀 테스트를 요구했다. T2 진입/커밋 보류.

- T1 fix round1 완료 보고: 프로젝트 추론을 조립 앞단으로 이동하고 복선 자체/요청 작품 양쪽 참조 소속을 검증, 공유 RevisionConflict helper 재사용. 신규 회귀 RED5실패→bundle23/owned56/full247통과(구현자 기록). 원 검토자가 고정 hash로 F1 재검토 중이며 부모도 전체 backend를 임시 DB로 재실행 시작했다. 독립 PASS 전 커밋/T2 없음.

## T1 검증 완료
- 독립 재검토 Spec PASS / Quality PASS. F1 해소; 별도 reviewer 재현4 + owned56 통과.
- 부모가 최종 소스 hash를 재대조하고 native 임시 DB 전체 backend247개 통과를 새로 확인했다(`ai-context-task-1-parent-backend.txt`); diff check 통과.
- T1만 검증 완료했다. 목적/복선 의미 T2, 프론트 T3, 실제 브라우저/제공자 QA T4는 아직 미완료이며 배포하지 않는다.

## T2 구현 착수
- T1 검증 소스 commit `da49ff3da852def210a99d4b5792dd5b376d8e6f`. T1 구현/검토자는 작업 종료, 공유 소스 수정 금지.
- 새 `ai-context-backend-directives-impl` (`sub-fd691921`)가 T2만 맡는다. 목적별 brief/parallel/generation/review/canon 지침, 승인 복선 예외와 시점 라벨, 로컬 후크 점수 적용/이력 구분을 구현한다. `docs/superpowers/tasks/2026-09-08-ai-context-task-2.md` 참조.

- T2 구현자 완료 보고: RED9실패→focused58/T1+T2 owned87/full265통과. 아직 독립 승인 전이다. `ai-context-task-2-review-diff.txt`에 추적 변경+신규 테스트 및 hash를 고정했고 `ai-context-task-2-reviewer`가 실제 diff/메시지 계약/선택 예외/후크 점수와 native 테스트를 검토한다. T2 소스는 검토 중 동결, 커밋 및 T3 진입 보류.

- T2 독립 검토: owned87 통과이나 Spec/Quality NEEDS FIXES(S1). canon 실제 요청 문구가 미래 설치 복선을 현재 미회수 비밀로 분류하는 오류를 재현해 원 구현자 fix round1 배정. 메타데이터가 아니라 실제 전달 문구와 공개/승인/시점 조합을 검증한다.
- Ruling Q1: HANDOFF/progress의 전역 git diff는 부모의 기존/진행 기록 변경이며 worker 소유권 위반 증거가 아니다. diff 패키지를 Task2 source/test 한정이라고 명시해 해소 — 기존 미커밋 문서를 보존하고 worker 소스 검토에서 제외한다 — 잘못 판단 시 코드 재작업보다 기록 손실 위험이 커 임의 정리를 금지한다.

- T2 S1 fix round1 완료 보고: 실제 canon 문구에 미래 설치/현재 설치+미래 회수/승인/이미 공개 구분을 반영. RED3실패→메시지조합4/owned91/full269통과(구현자 기록). 원 검토자가 고정 hash로 S1 및 관련 조합을 재검토하며 부모도 전체 native backend를 새로 실행 중이다. 독립 PASS 전 커밋/T3 없음.

## T2 검증 완료
- 독립 Spec PASS / Quality PASS. S1 해소; 실제 전달 문구 재현 및 조합4/owned91 통과.
- 부모가 최종 hash를 재대조하고 native 임시 DB 전체 backend269개 통과를 확인했다(`ai-context-task-2-parent-backend.txt`). 회차 목적·복선 허용 규칙의 백엔드 검증 완료이며 화면/실제 통합은 아직 남아 있다.

- T3 구현자 완료 보고: native build + 신규 fixture4 + 기존 보존 fixture17 + backend호환35 통과. 아직 독립 승인 전. `ai-context-task-3-review-diff.txt`에 source/test/config 한정 변경과 신규파일/hash를 고정했고 새 `ai-context-task-3-reviewer`가 실제 lifecycle/브라우저 요청·편집 결과 및 native build/fixture를 검토한다. 원 구현자는 수정 대기, T4 실행/커밋 보류.

- T3 독립 검토: build/신규fixture4/보존fixture17 통과이나 Spec/Quality NEEDS FIXES. High: 회차A canon POST를 지연시키고 B로 이동 후 이전 응답을 받으면 B dialog에 A issue가 보이는 것을 실제 브라우저로 재현했다. 부모가 원 구현자에 응답 시점 token/회차/수정본 소유권, 닫기/재열기/왕복 이동, 늦은 오류·결과와 새 요청 경합까지 fix round1 배정했다. T4/커밋 보류.

- T3 fix round1 완료 보고: CanonDialog와 fixture 테스트만 수정. 늦은 응답 token/lifetime/작품·회차 소유권 확인 및 origin revision/hash 표시를 추가했다. RED 재현→신규fixture7/별도재현2/보존17/build 통과(구현자 기록). 원 검토자가 고정 hash로 재검토하고 부모도 native build 실행 중이다. T4/커밋은 여전히 독립 PASS 후 진행한다.

## T3 검증 완료
- 초기 독립 검토의 단일 High stale-canon 결함이 scoped 재검토 Spec/Quality PASS로 해소됐다. reviewer가 별도재현2/신규fixture7/보존fixture17/build를 새로 통과하고 전후 소스 hash 일치를 확인했다.
- 부모도 최종 hash와 native build PASS를 확인했다(`ai-context-task-3-parent-build.txt`). 이 단계는 UI fixture 검증이며 실제 API/SQLite/provider 통합 T4는 아직 실행 전이다.

## T4 실제 격리 통합 QA 착수
- T3 검증 소스 commit `03bad73239e861b0f122d176fe6b014b28b278af`. 기존 native CRLF를 보존했고 CR-at-EOL을 인식하는 diff check도 통과했다(코드 변경 없이 검토 hash 유지).
- 새 `ai-context-integration-qa-impl` (`sub-57021bb6`)이 QA 파일만 소유한다. 전용15212/18112/18113, strict Alembic 임시DB, 실제 browser/API 및 독립 가짜제공자 JSONL, 원고·복선 상태 무자동변경과 제공자호출 전 오류를 검증한다. 상세 Task4 handoff와 환경 rulings 참조. T4 구현자 보고 이후 독립 QA 검토 및 최종 브랜치 검토가 남아 있다.

- T4 QA scripts/config/실제 통합 spec 초안 생성. 작업자가 native backend 회귀 테스트를 비동기로 시작한 뒤 대기 턴을 종료해 부모가 기존 handle 결과 확인 및 실제 integration 단계 재개를 지시했다. 아직 QA 검증 리포트/전체 완료 보고가 없으며 이를 통합 통과로 간주하지 않는다.

- T4 최초 실제 실행은 QA TypeScript Windows 경로 escaping 오류로 시작 실패, QA 설정만 보정해 재실행했다. 다음 실행은 strict Alembic 임시DB와 provider/backend health까지 확인했으나 QA seed 로어 category가 실제 enum과 달라422로 중단됐다. API 검증을 바꾸지 않고 seed만 스키마에 맞추며, 실패 근거/소유 프로세스 정리를 보존한다. 아직 브라우저 통합 통과 아님.

- T4 run4는 실제 단일생성+감수 요청까지 동작했고, 열린 AI 모달이 sidebar 클릭을 막아 QA 시나리오가 timeout됐다(앱 오류 아님). QA만 정상 닫기→회차이동 순서로 수정했고 seed-ready 대기 및 테스트의 강제 current identity 주입도 제거해 자연스러운 편집기 연결을 검증하도록 강화했다. run5 단일 통합 실행 중; 아직 최종 통과/커밋 없음.

- T4 run5는 회차 이동 후 패널을 다시 여는 QA 동작 누락으로 중단돼 QA만 보정했다. run6 첫 실제 브라우저 시나리오 1개 통과, 병렬 planner/worker×2/reviewer까지 제공자 로그 확보. 병렬 검증이 원시 enum을 자연어 제공자 지시문에서 찾던 assertion을 실제 HTTP enum / 제공자 지시문 경계별 확인으로 고쳤다. run7 실행 중이며 validation 초안은 아직 READY가 아니다.

## T4 독립 검토 착수
- 최종 구현자 검증: 실제 browser/FastAPI/strict Alembic 임시SQLite/가짜provider 통합 3개 PASS, native backend 전체269 PASS, build PASS. 실제 provider JSONL은 draft2/review1/planner1/worker2/parallel-review1/canon1이며, 문서·DB·PID/listener 근거를 보존했다.
- 새 독립 `ai-context-task-4-reviewer`가 6개 QA 파일의 고정 hash와 실제 통합 재실행을 검토한다. 구현자는 동결 상태다. 아직 T4 커밋/최종 브랜치 검토/전체 완료 아님.

- T4 독립 통합3PASS/중점 backend91PASS/buildPASS, 부모 backend269PASS. 다만 독립 검토는 NEEDS FIXES: canon 화면의 검사 기준을 일반 라벨로만 확인해 정확한 작품·회차·revision·hash 표시 검증이 부족하다. 부모가 실제 소스를 확인하고 지적을 수용했다. 원래 QA 구현자에게 저장된 본문에서 독립 계산한 hash와 정확한 표시·이력을 대조하는 테스트 보강만 요청했다. 앱 변경 없이 재실행하고 같은 독립 검토자가 재검토해야 한다.

## T4 독립 재검토 통과
- 정확한 canon 화면 작품/회차/revision/hash, 저장 본문 SHA256, API 및 DB 이력 대조를 보강했다. 독립 재실행 통합3PASS, Spec/Quality PASS, 남은 지적 없음. 두 worker/조립 순서, 오류 요청8건의 제공자 호출 없음, 창작 데이터 무자동변경 및 소유 서버 정리도 유지됐다. 부모 backend269PASS 및 검토 hash 일치를 확인했다.
- T4 변경을 로컬 커밋한 뒤 최종 전체 브랜치 사양/품질 검토로 이동한다. 아직 운영 반영/merge/push 없음.
