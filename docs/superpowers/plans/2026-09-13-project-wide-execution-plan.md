# 프로젝트 전체 잔여 작업 실행 지도 — 종합 제안서

- 작성일: 2026-09-13
- 상태: **제안서/실행 지도 — 소유자 승인 대기**. 이 문서는 어떤 항목의 구현 승인도 아니며, 승인 전까지 소스·schema·migration·테스트·기존 handoff/spec를 변경하지 않는다.
- 기준 문서: [단일 원장](../../handoffs/2026-09-08-remaining-work.md), [통합 인계·Git 게시 경계](../../handoffs/2026-09-13-commit-handoff.md), [순차 실행 승인](2026-09-12-remaining-sequence.md), [D01 질문·근거](2026-09-13-d01-contract-questions.md), [D01 상세 계약 제안서](2026-09-13-d01-detailed-contract-proposal.md), [자동 요약 설계](2026-09-11-long-memory-auto-summary-backfill.md), [운영 런북](../../runbooks/long-memory-governance-release.md), [격리 runner 가이드](../../runbooks/isolated-backend-tests.md), [문서 상태 인덱스](../../DOCUMENT_STATUS.md).

## 1. Executive summary와 기준점 대조

### 결론

- 완료·수용된 범위(C01~C13, B01~B04, M01~M05, B03, C10 planner)는 **재개하지 않는다**. 잔여 작업은 미구현 제품 범위 **D01~D04**, 검증·계측 **V01~V04**, 실제 자원 승인 대기 **G01~G04**, 축소 UI **U01~U04**, 선택 확장 **O01~O06**다.
- 현재 승인된 실행 순서는 **D01 → D03 → D04(fake worker) → V01/V02/V04 → (필요 시 V03) → G02 → G01 → G03 → G04**다. D02와 U/O 항목은 이 순서에 자동 추가되지 않는다.
- 지금 즉시 가능한 다음 행동은 **D01 소유자 결정(A vs B + Q1~Q7) 요청 → 좁은 상세 사양 작성·검토·승인**이다. 이 문서와 [D01 상세 계약 제안서](2026-09-13-d01-detailed-contract-proposal.md)는 그 결정을 돕는 입력이며 구현 승인이 아니다.
- 실제 provider·운영 DB·credential/keyring·지정 Windows 장치·migration 실행·배포·비용 발생은 각 gate의 환경·예산·접근 허가를 개별 확보하기 전까지 실행하지 않는다.

### 기준점 대조 (2026-09-13 확인)

| 항목 | 실제 확인 값 | 문서 기록과의 관계 |
| --- | --- | --- |
| 현재 HEAD | `c2e4f6a51489b18dba851c4bd21e907adabf812e` (`c2e4f6a feat: finalize GPT OAuth, memory and quality safeguards`) | 문서에 남은 `c1a92c4`는 9월 13일 게시 **이전** 기준점이다. 과거 수치·판정을 현재 상태로 재사용하지 않는다. |
| origin/main | `c2e4f6a51489b18dba851c4bd21e907adabf812e` — 로컬 ref 기준 HEAD와 일치 | [통합 인계](../../handoffs/2026-09-13-commit-handoff.md)의 "HEAD와 원격 main 대조로 확인" 규칙과 일치. push를 배포 성공으로 해석하지 않는다. |
| working tree (이 worktree) | 미추적 1개: `docs/superpowers/plans/2026-09-13-d01-detailed-contract-proposal.md` | 이 worktree는 별도 검토용이다. **main worktree의 기존 dirty/untracked 자료를 추정·삭제·복원하지 않는다.** |
| 문서 기준 | 원장·인덱스·통합 인계가 2026-09-13 대조 완료 | `handoffs/2026-09-08-remaining-work.md`는 파일명만 9월 8일이고 **현재 원장**이다. 하단 "보존된 원문"만 역사 기록. |

## 2. 완료 범위 — 절대로 다시 열지 않음

| ID | 완료된 범위 | 수용 근거 | 분리해서 남긴 범위 (완료의 일부가 아님) |
| --- | --- | --- | --- |
| C01 | 기본 MVP 집필·관리(작품/권/회차, 편집·미리보기,보내기, 인물·로어, AI/윤문 패널, 설정) | MVP 사양·기존 QA | 축소 UI U01~U04, 실기기 수용 G04 |
| C02 | 집필 보조 고도화(기획/목차·인물 생성, 장면, 복선, 로어 자동 주입, canon/품질 진단, 감수·병렬) | HANDOFF 고도화 이력·현재 소스 | 진단 B03 종결, D01~D03, 실제 품질 G02 |
| C03 | 원고 보존 1단계(revision 충돌, 저장 큐, 전환/늦은 응답 방어, 복구 draft, snapshot·복원) | [독립 최종 검증](../../audits/preservation-final-validation.md) | 운영 적용 G01. 모든 삭제의 휴지통까지 구현했다는 뜻 아님 |
| C04 | 공통 AI 맥락 일관성(소속·revision·opt-out·관계·목적, 요청 snapshot/출처 격리) | [최종 검증](../../audits/ai-context-final-validation.md) | M01은 MemoryPage 문제였지 AI 패널 맥락 재개 아님 |
| C05 | 관리 CRUD·검색 무결성(교차 reorder/참조 거부, 삭제 409, FTS scope, `volume:null`) | 9월 9일 결과: 관련 54/전체 277 passed | 관리 후보 재현 작업 종료, B01/B02는 C13에서 종결 |
| C06 | 환경·빌드 정리(Vite 중복 build 제거, AnyIO/Starlette/HTTPX 고정, shell LF) | [호환성 보고](../../audits/anyio-starlette-httpx-compatibility-2026-09-10.md) | ResourceWarning 등 선택 정리 O05, 장치 QA G04 |
| C07 | 장편 기억 기반·수동 거버넌스(MemoryEntry/migration, provenance/stale, API/UI) | [구현 기록](2026-09-11-long-memory-followup.md) | M01~M05 별도 수용, D02 확장, G01 운영 |
| C08 | 승인된 장편 기억 P1 네 건(폐기 오전송, POST 보호, PATCH CAS, 삭제/생성 경쟁) | 독립 무결성 PASS·UI PASS with notes·assertion 보강 | P2 다섯 건은 M01~M05로 수용 완료 |
| C09 | 고정 GPT OAuth 전환(localhost bridge/`gpt-5.6-luna`/`xhigh`, endpoint 선택 제거, legacy 보존) | [기술설계](../../../기술설계_GPT_OAuth_브릿지_v1.md) | 오프라인/fake 계약 완료일 뿐 실제 로그인·provider 수용 G02/G03 미실시 |
| C10 | 자동 요약의 provider-free planner(allowlist, deterministic manifest, 경계 테스트) | [설계·완료 경계](2026-09-11-long-memory-auto-summary-backfill.md) | 실제 job/worker/draft/운영 backfill은 D04 |
| C11 | 백업·복원·migration 임시 검증(합성 데이터 백업 비교, 임시 SQLite 복원, rollback/re-upgrade, 런북) | [dry-run](../../audits/backup-restore-dry-run-2026-09-10.md) | failure injection V02, 실제 DB/credential/rollback G01/G03 |
| C12 | 평가·QA 준비·자동화(실모델 평가 설계, Windows QA 계획, fixture/axe/fake-provider 통합) | 설계 문서들 | 실기기·실모델 수용 아님. V01~V03, G02/G04 잔여 |
| C13 | B01 canon 실패 계약 + B02 bootstrap 정합성 + B04 테스트 격리 | 419P/외부 skip1, 독립 검토 2건 PASS. [최종 근거](../../audits/failure-contracts-2026-09-12/b04-review-fixes.md) | 외부 metrics 비교 V04, 실제 자원 G gate. 과거 격리 사고 한계는 보존 |
| M01~M05 | 기억 화면 보정 5건(작품별 격리, stale 갱신, 오류 표시, focus, 삭제409 안내) | backend 421P/skip1·frontend 72P, 독립 2PASS. [수용](../../audits/memory-m01-m05-2026-09-12/acceptance.md) | 운영 적용 아님 |
| B03 | 품질 지표 최소 보정(계수 2건, 참고점수/빈 원고/essay/이력 안내, dialog 이름) | backend 482P/skip1·frontend 77P·국소 coverage·독립 E1종결2PASS. [수용](../../audits/quality-b03-2026-09-12/acceptance.md) | 가중치/API/이력 유지. 실제 작품 평가 G02 |

과거 사고의 한계(최초 401 실행의 격리·보존 실패, 옛 `.coverage` 미복구, 당시 credential 부수 효과 미확정, 504/ENOMEM/formatter 실패 원문)는 **보존하며 PASS로 고쳐 쓰지 않는다**. 게시 전 보안 참고 **A1 LOW**(`backend/app/routers/ai_panel.py`의 기존 provider 오류 메시지 전달)는 별도 후속 범위이며 완료 항목 재개 사유가 아니다.

## 3. 잔여 작업 inventory

각 항목을 상태 / 근거 / 선행 조건 / 산출물 / 검증 범위 / 승인 필요 여부 / 금지사항으로 분리했다.

### 3.1 미구현 제품 범위 D01~D04

#### D01 — 회차 목표(브리프) 영속화

- **상태:** 소스 조사 완료, 요구 결정 대기. 상세 사양·구현 미착수.
- **근거:** `EpisodeBrief`는 "DB 마이그레이션 없이 요청에만 존재하는 구조체"(`backend/app/schemas.py:407–424`). 프론트 `episodeBrief`는 메모리 병합 setter뿐(`frontend/src/stores/aiPanelStore.ts`, `EpisodeBriefState`/`EMPTY_EPISODE_BRIEF`와 단일 메모리 값). [질문·근거](2026-09-13-d01-contract-questions.md), [상세 계약 제안서](2026-09-13-d01-detailed-contract-proposal.md).
- **선행 조건:** 소유자의 A/B 결정과 Q1~Q7 답변 → 좁은 상세 사양 승인.
- **산출물:** 상세 사양 → 합성 RED → 최소 구현(schema/migration 포함 가능, TEMP DB만) → 회귀 → 독립 검토 → 수용 문서.
- **검증 범위:** §5.10 제안 케이스(교차 소속 422, 재진입 복원, 빈/부분 저장, CAS 409, 원문 revision·snapshot 불변, 늦은 응답 격리, fake provider 생성 연계, B 선택 시 이력).
- **승인 필요 여부:** 구현 전 반드시 필요(상세 사양 승인). 운영 migration은 G01로 별도.
- **금지사항:** 목표 저장을 `Chapter.revision` 증가·snapshot 생성과 혼합 금지, `Chapter.memo` 덮어쓰기 금지, 생성 요청 동결·flush·purpose 의미·브리프 검증 변경 금지, 목표 달성 자동 판정 금지.

#### D02 — 인지·상태를 구분하는 장편 기억 확장

- **상태:** 미착수. 현재 승인 순서의 자동 추가 범위가 아니다.
- **근거:** 원장 §4. 현재 메모리는 provenance/stale·미래 복선 구분까지만 지원.
- **선행 조건:** D01~D04 핵심 흐름 안정화 후 별도 도메인 설계 승인.
- **산출물:** 인지(작가/독자/인물)·고정 설정 vs 변화 상태·사건/관계 영향 추적의 도메인 설계 → 별도 승인 후 구현.
- **검증 범위:** 설계 승인 시 확정. 과거 감사의 "브리프에만 있는 로어 검색 누락"은 D02의 검색 입력·회수 범위에서 재확인.
- **승인 필요 여부:** 전면 필요. 현재 수동 memory 기능 전체의 재구현이 아니라 **추가 도메인 설계**로 접근.
- **금지사항:** C07/C08/M01~M05 수용 범위 재구현 금지, 자동 승인·자동 폐기 도입 금지.

#### D03 — 기획→집필→퇴고→완결·재개 흐름

- **상태:** 미착수. D01 이후 얇은 단위로 승인.
- **근거:** 원장 §4·§8, [상세 계약 제안서 §6](2026-09-13-d01-detailed-contract-proposal.md).
- **선행 조건:** D01의 회차 소속·`goal_version`·`base_manuscript_revision`(B 선택 시 이력) 계약 확정.
- **산출물:** 얇은 단위의 흐름 계약·상태 전이·근거 연결 사양 → 승인 → 구현·검증. 상세 입력/출력/불변조건/테스트 matrix는 §6.
- **검증 범위:** 흐름 상태 전이·재개·근거 연결·완결 분리·이관(§6 matrix).
- **승인 필요 여부:** 단위별 승인 필요. 로드맵 존재를 상세 설계/구현 승인으로 대신하지 않는다.
- **금지사항:** 집필 확정과 연재 완결 혼합 금지, 원문 CAS/보존 계약 변경 금지, D02 자동 포함 금지.

#### D04 — 실제 자동 요약·backfill (summary job/idempotency/worker/draft)

- **상태:** C10 planner만 완료. job 저장·schema·worker·draft·중단/재개·실패 미구현.
- **근거:** `backend/app/services/summary_jobs.py`(deterministic manifest만 생성, provider 호출·MemoryEntry 쓰기·job table 없음 — 모듈 docstring으로 확인), [설계 §9 체크리스트](2026-09-11-long-memory-auto-summary-backfill.md).
- **선행 조건:** job/idempotency 저장 방식 결정(별도 `summary_jobs` table + unique constraint vs deterministic comparison 유지), fake worker 범위 승인.
- **산출물:** job schema/migration(TEMP 검증), fake worker, draft 저장·상태 기계, 중단/재개·실패 계약, 회귀.
- **검증 범위:** §7 matrix — fake worker로 먼저 검증. 실제 provider/운영 실행은 G01/G02/G03 추가 게이트.
- **승인 필요 여부:** schema 저장 방식·worker 범위에 승인 필요. planner 재작성 불필요.
- **금지사항:** `draft_saved`를 승인으로 취급 금지, 기존 approved/retired 덮어쓰기 금지, 자동 승격 금지, 운영 backfill은 G gate 없이 금지.

### 3.2 검증·계측 V01~V04

#### V01 — 프론트 source-mapped coverage

- **상태:** 미실시. 현재까지는 **국소 변경범위** coverage만 존재(B03: quality 19/20·10/10, QualityDialog 278/284·42/48, Dialog 41/41·14/14; M01~M05: Memory 60/60·33/33 등).
- **근거:** 원장 §5/§9.
- **선행 조건:** 계측 도구·범위·실행 방식 승인(owned TEMP 설치 한정 원칙).
- **산출물:** source-mapped line/branch coverage 수치 + raw 데이터 + manifest.
- **검증 범위:** 전체 프론트 소스. 국소 수치를 전체로 과장 금지, E2E 통과만으로 80% 주장 금지.
- **승인 필요 여부:** 계측 설정에 대한 승인 필요.
- **금지사항:** 프로젝트 의존성·전역 설치 변경 금지, N/A를 100%로 해석 금지.

#### V02 — 복원 실패 시나리오 failure injection

- **상태:** 미실시. C11의 합성 데이터 백업/복원·migration 검증은 완료.
- **근거:** 원장 §5.
- **선행 조건:** 주입 시나리오 목록 승인.
- **산출물:** manifest 불일치·파일 누락·잘못된 schema·disk-full 등 각각의 재현 로그와 복구/거절 결과.
- **검증 범위:** 합성 TEMP DB만. wrong-key 검증은 G03 승인 범위와 분리.
- **승인 필요 여부:** 시나리오 승인 필요.
- **금지사항:** 운영 DB·실제 키 사용 금지, 기존 C11 검증을 미실시로 되돌리지 않음.

#### V03 — 추가 환경/부하 범위

- **상태:** 미실시·조건부. 승인 순서에서 "필요 시"만 채택.
- **근거:** 원장 §5. 실제 독립 SQLite 세션의 CAS·잠금 경합 검증은 완료.
- **선행 조건:** 배포 구성상 필요성 판단 + 범위 승인.
- **산출물:** 다중 HTTP 프로세스 부하·다른 DB/transaction 설정의 동시성 증거.
- **검증 범위:** 승인된 구성에 한함.
- **승인 필요 여부:** 채택 자체가 승인 대상.
- **금지사항:** 완료된 경쟁 테스트를 실패로 되돌리지 않음, 무차별 부하 범위 확장 금지.

#### V04 — 외부 im-not-ai metrics 버전 동기화

- **상태:** 미검증. 기존 **미설치 skip 1건**을 부모가 분리·허용(todo #18).
- **근거:** 원장 §5/§9.
- **선행 조건:** 실제 외부 `metrics_v2.py` 소스 접근 경로 확보.
- **산출물:** 상수 비교 로그 — 소스 확보 시 PASS/FAIL, 미확보 시 skip 유지를 명시.
- **검증 범위:** 상수 비교만. B01/B02/B04 수용을 다시 차단하지 않는다.
- **승인 필요 여부:** 외부 소스 접근 방법에 대한 확인 필요.
- **금지사항:** 미설치 skip을 PASS로 기록 금지, 외부 스크립트 실행을 위해 호스트 파일 생성·설치 금지.

### 3.3 실제 자원 승인 대기 G01~G04

#### G01 — 기존 DB migration·운영 적용

- **상태:** 승인 대기. migration 코드·임시 검증·운영 런북은 준비 완료.
- **근거:** 원장 §6, [운영 런북](../../runbooks/long-memory-governance-release.md). "기존 DB가 head보다 뒤처졌다"는 마지막 확인 기록이며 이번에 재조회하지 않음.
- **선행 조건:** 승인자·변경 창·백업/복원 담당자 분리, 대상 DB 확정.
- **산출물:** 일관된 백업 + manifest(SHA-256·`integrity_check`·`foreign_key_check`·row count) + 복원 증거 → 승인 migration → 데이터 보존/negative corpus/앱 smoke → 교체·rollback 증거.
- **검증 범위:** [런북 §2~§4](../../runbooks/long-memory-governance-release.md)의 백업→migration→smoke. 운영 DB에서 즉흥 downgrade 금지.
- **승인 필요 여부:** 명시 승인 + 변경 창 필수.
- **금지사항:** 승인 전 운영/기존 DB 접근 금지, 백업 없이 upgrade 금지.

#### G02 — 실제 OAuth/provider 수용·문학 품질 파일럿

- **상태:** 승인 대기. fake 계약·평가 설계는 준비 완료.
- **근거:** 원장 §6, [평가 설계](../../audits/ai-model-quality-evaluation-design-2026-09-10.md).
- **선행 조건:** bridge availability/정책/모델 확인, 승인 원고 6사례·source owner, 블라인드 독립 평가자 2명, 기대/금지 결과, **USD 20 hard cap** 확정.
- **산출물:** raw usage/latency/비용 증거 + 블라인드 평가 결과표.
- **검증 범위:** 짧은 파일럿. 실제 장편 1/20/50/100화 평가는 별도 후속 단계.
- **승인 필요 여부:** 비용·계정·평가자 모두 확정 후 호출.
- **금지사항:** 조건 미충족 시 provider 호출·비용 발생 금지.

#### G03 — credential·키 복구/로그아웃 검증

- **상태:** 승인 대기. credential 소유 경계·키 분리 설계만 존재.
- **근거:** 원장 §6, [기술설계](../../../기술설계_GPT_OAuth_브릿지_v1.md).
- **선행 조건:** 지정 테스트 credential/계정과 접근 승인.
- **산출물:** 복구·로그아웃·rollback 절차 확인 기록 + 잘못된 키의 실패 검증.
- **검증 범위:** 지정 테스트 credential만.
- **승인 필요 여부:** 필수.
- **금지사항:** 실제 개인 credential 조회·변경 금지, legacy endpoint key 저장 UI 재도입 작업 아님.

#### G04 — 지정 Windows 실기기 수용

- **상태:** 승인 대기. native 임시 DB 자동화·WSL 정적 점검은 완료.
- **근거:** 원장 §6, [Windows QA 계획](../../audits/windows-device-qa-plan-2026-09-10.md).
- **선행 조건:** Windows 11 x64 지정 장치·QA 계정·전용 port·test DB/dummy key·시간 창.
- **산출물:** batch·경로·인코딩·공존·복원, DPAPI/keyring, 브라우저·NVDA·키보드·zoom, 5만 자 입력/검색 성능 **결과표**.
- **검증 범위:** 지정 장치 수동 수용. 이미 수행한 native pytest와는 다른 시험.
- **승인 필요 여부:** 장치·계정·시간 창 지정 필수.
- **금지사항:** 비지정 장치·실제 운영 DB/keyring 우회 금지.

### 3.4 축소 구현 UI U01~U04 (없던 일로 지우거나 출시 결함으로 단정하지 않음)

| ID | 항목 | 상태·선행 조건 | 산출물·검증 | 승인·금지 |
| --- | --- | --- | --- | --- |
| U01 | 캐릭터 `card_json` 자유 확장 UI | DB/API 확장·기본 7필드 UI 있음, `CharactersPage` 자유 확장 편집 없음. 사용자 수요 확인 필요 | UI 범위 승인 후 편집 UI + 회귀 | 범위 승인 필요 |
| U02 | 로어 참조 회차 표시 | 기본 검색/편집 있음, `LorebookPage` 참조 회차 목록 없음 | 채택 시 연결 UI + 회귀 | 선택 채택 승인 |
| U03 | 윤문 명령 프리셋 UI | 미연결 항목, 현재 RefineTab은 강도·고지 중심 | 필요성 재결정 후 설계 | 임의 shell 실행 UI 추가 금지 |
| U04 | 시니어 확대 모드 | 다크/라이트·본문 폰트·행간 있음, 전용 확대 토큰 없음 | G04 zoom/가독성 결과로 필요성 판단 | G04 결과 선행 |

### 3.5 선택 확장 O01~O06 — 현재 우선순위 밖

| ID | 항목 | 메모 |
| --- | --- | --- |
| O01 | SillyTavern 카드 PNG import/export, novelWriter import | 핵심 안정화·실사용 결과 후 선택 |
| O02 | 자동 주기 백업·클라우드 동기화·Git 버전 관리·추가 삭제 복구 UI | 기존 snapshot·수동 백업 검증과 별개 |
| O03 | 연재 캘린더·멀티 작품 통계·플랫폼 직접 발행 연동 | 정책 확인 전 발행 연동 보류 |
| O04 | 새 provider/모델 선택지, KoboldCpp native, 임베딩 검색·병렬 작업자 확대 | 고정 OAuth 계약에서 우선하지 않음 |
| O05 | 비차단 ResourceWarning·호환 helper 중복 정리·모니터링 | 해결된 Vite/AnyIO 경고 미포함 |
| O06 | 플랫폼 규정·의존성/라이선스 최신 근거 재확인 | 오래된 리서치를 최신 사실로 취급 금지 |

**되살리지 않을 것:** 신규 endpoint/API key/base URL·모델 선택 UI(의도적 제거), AI 자동 삽입·무검수 자동 승인·탐지 회피 기능. legacy `ai_endpoints`/hidden routes는 migration 호환용 보존이지 재도입 할 일이 아니다.

## 4. 의존 그래프·실행 순서

```text
[완료·동결] C01~C13 / B01~B04 / M01~M05 / B03 / C10 planner
        │
        ▼
D01  소유자 결정(Q1~Q7, 특히 Q2: A vs B) → 상세 사양 승인 → 구현·검증·수용
        │  (산출: 회차 소속·goal_version·base_manuscript_revision [+이력(B)])
        ▼
D03  얇은 단위 승인 → 기획→집필→퇴고→완결·재개 계약 구현
        │
        ▼
D04  job/idempotency 저장 방식 승인 → fake worker로 상태 기계·중단/재개·실패 검증
        │  (실제 provider/운영 backfill은 아래 G gate와 결합 시에만)
        ▼
V01 / V02 / V04  검증 보강 (병렬 가능, 각각 별도 승인)
        │  (V03: 배포 구성상 필요할 때만)
        ▼
G02 실제 OAuth/품질 파일럿 → G01 운영 DB migration → G03 credential 복구 → G04 지정 실기기
        │  ※ 각 gate는 환경·예산·계정·백업·장치·시간 창을 개별 확보한 뒤에만 실행
        ▼
U01~U04 / O01~O06  실사용 결과 뒤 선택 (자동 추가 아님)
```

- D02는 D 묶음의 자동 추가 범위가 아니며, 핵심 흐름 안정화 후 별도 도메인 설계로 승인한다.
- 각 묶음은 완료·검토 후 다음으로 진행한다. 코드 변경에 필요한 국소 검증은 즉시 하되, 그 결과를 후속 묶음(예: V01 전체 coverage)의 완료로 확대 해석하지 않는다.
- main worktree 단일 writer 원칙, 기존 dirty/미추적 자료 보존, stage/commit/push는 별도 승인 경계.

## 5. D01 결정 프레임 — 상세 사양 승인 전까지 구현 불가

[D01 상세 계약 제안서](2026-09-13-d01-detailed-contract-proposal.md)가 현재 기준이다. 핵심만 요약한다.

### 5.1 A vs B

| 비교축 | A. 최신 목표만 저장 | B. 변경 이력 조회·복원 |
| --- | --- | --- |
| 저장 형태 | 회차당 현재 목표 1행 + 독립 목표 버전 + 기준 원고 revision | 동일 현재값 + append-only 목표 이력 |
| 과거 내용 조회/복원 | 불가 | 가능(복원은 항상 새 버전 기록) |
| 비용 | 테이블 1개 또는 컬럼 | + 이력 테이블·목록/선택 API·얇은 이력 UI |
| D03 연결 | 목표 변경 후 과거 판단 근거 소실 | 목표 버전 ↔ 원문 revision 근거 쌍 유지 |
| 위험 | 나중에 이력 필요 시 이관 비용 | 이력 기능 팽창 — UI를 목록·복원으로 제한 필요 |

**권장: B(얇게)** — 현재값 저장 + append-only 이력 + 목록·복원 최소 API/UI. 단 **미승인**이며 A를 선택해도 현재값 계약(제안서 §5)은 동일하게 적용된다.

### 5.2 미결정 질문 Q1~Q7

| # | 질문 | 제안 기본값 | 상태 |
| --- | --- | --- | --- |
| Q1 | 작품 공통 목표 필요 여부 | 이번 범위 제외, 회차 목표만 | 미결정 |
| Q2 | A vs B | **B 추천** | 미결정 |
| Q3 | `episode_purpose`를 목표와 함께 영속화·복원할지 | 함께 저장(검증·문구 불변) | 미결정 |
| Q4 | 전 필드 빈 값 = 비우기인가, 별도 삭제인가 | 명시적 비우기/삭제 + 확인(B 시 이력 보존 여부 별도) | 미결정 |
| Q5 | B 시 회차 삭제 허용될 때 이력도 함께 삭제할지 | 회차 생애와 동일(cascade), D03 근거 참조 도입 시 재확인 | 미결정 |
| Q6 | 생성 시 "저장된 목표 사용" 모드를 둘지 | 기본 현재 입력값, 저장본 사용은 선택 토글 + 출처 metadata | 미결정 |
| Q7 | 자동저장 필요 여부 | 명시적 저장 버튼(자동저장 채택 시 큐·충돌·이탈 보존 별도 명세) | 미결정 |

### 5.3 D01 구현 전 필수 순서

1. 소유자가 Q1~Q7 답변(특히 Q2).
2. 답변을 반영한 **좁은 상세 사양** 작성·검토·승인.
3. 승인 후에만 합성 RED → 최소 구현 → 회귀 → 독립 검토 → 수용.
4. **이 문서와 제안서는 D01 구현 승인으로 취급하지 않는다.**

## 6. D03 다음 handoff용 — 입력·출력·상태·불변조건·테스트 matrix (구현 아님)

### 6.1 D01이 제공해야 하는 접점(입력)

| 의존성 | D01에서 확정할 것 | D03 사용 방식 |
| --- | --- | --- |
| 회차 소속·식별 | 목표의 `chapter_id` 소유 계약 | 근거 연결의 고정 키 |
| 목표 버전 | `goal_version` 단조 증가 | "어느 목표에 대해 집필했는가"의 근거 |
| 기준 원고 revision | `base_manuscript_revision` | 목표↔원문 시점 쌍, 변경 추적 |
| 이력(B 선택 시) | 과거 목표 내용 조회 | 결말 변경 영향·이관 판단 근거 |

### 6.2 D03 범위의 출력

- 흐름 상태 전이 계약: 기획 → 집필 → 퇴고 → 완결과 불법 전이 거절.
- 재개 계약: 미해결 감수/다음 장면에서 재개 시 목표 버전·원문 revision 표시.
- 근거 연결: 목표 필드(사건/선택/대가) ↔ 원문 범위의 링크 보존·파손 안내.
- 완결 분리: 집필 확정과 연재 완결 상태의 분리, 완결본 관리.
- 이관: 해결 / 의도적 미해결 / 외전 이관의 구분 표시.

### 6.3 불변조건

- 목표 저장은 목표 달성 판정이 아니다. 자동 달성·완결 자동 분류 금지.
- 원문 `revision`/CAS·snapshot·flush·요청 동결 계약 불변.
- 집필 확정(원문 상태)과 연재 완결(작품 상태)은 서로 다른 수명주기.
- 과거 감사의 "짧은 장면도 완료 처리/앞 장면 결과 없는 병렬 집필"은 D03의 분량·사건 이행·순차/병렬 조건에서 재확인하되, 새 재현 없이 해결로 닫지 않는다.

### 6.4 테스트 matrix (다음 handoff에서 상세화)

| 축 | 케이스 |
| --- | --- |
| 흐름 상태 | 정상 전이와 불법 전이 거절, 상태별 허용 동작 |
| 재개 | 미해결 감수·다음 장면 재개 시 목표 버전·원문 revision 표시 정확성 |
| 근거 연결 | 목표↔원문 링크 보존, 원문/목표 변경 시 파손 안내 |
| 완결 분리 | 집필 확정 ≠ 연재 완결, 완결본 관리 |
| 이관 | 해결/의도적 미해결/외전 이관의 구분과 조회 |
| 경쟁 | 목표 CAS·원문 CAS와 흐름 상태 변경의 충돌 처리 |

## 7. D04 다음 handoff용 — 입력·출력·상태·불변조건·테스트 matrix (구현 아님)

### 7.1 입력

- 완료물: `summary_jobs.py`의 provider-free deterministic manifest. `SummaryManifestItem` 필드: `project_id, chapter_id, source_revision, source_sha256, source_sort_order, source_content_length, kind="summary", prompt_version, provider_identity, model_snapshot, request_options_hash, idempotency_key, status` — **목표 필드는 없다**(확인함).
- 설계 게이트: [auto-summary 설계 §9 체크리스트](2026-09-11-long-memory-auto-summary-backfill.md).

### 7.2 출력

- job/idempotency 저장 방식 결정: (a) 별도 `summary_jobs` manifest table + unique constraint, 또는 (b) schema 승인 전 deterministic comparison 유지. 논리 중복키: `(project_id, chapter_id, source_revision, source_sha256, kind, prompt_version, provider_identity, model_snapshot, request_options_hash)`.
- worker: fake provider로 먼저 상태 기계·경계 검증.
- draft: 생성 결과는 항상 `draft`로 저장, 수동 승인만 `approved`.

### 7.3 상태 기계

```text
planned → running → draft_saved
                ├→ skipped_empty      (빈 회차)
                ├→ stale_source       (생성 완료 시점 revision/hash 불일치)
                ├→ provider_error     (retry 허용 유일)
                ├→ rejected           (retired/소유권 불일치)
                └→ duplicate_skipped  (동일 manifest 재실행)
```

### 7.4 불변조건

- `draft_saved`는 승인 상태가 아니다. 수동 승인만 `approved` 전환.
- `stale_source`는 자동 retry 금지 — 최신 revision으로 새 작업 계획.
- 기존 `approved`·`retired` row를 backfill이 수정·삭제하지 않는다.
- 중단 시 저장된 draft 보존·manifest 재사용, partial batch를 전체 성공으로 표시 금지.
- rollback은 row 삭제가 아니라 해당 batch draft의 `retired` 전환 절차.
- 요약 worker 입력에 목표를 **포함하지 않는 것**이 기본 제안. 채택 시 목표 버전/hash를 idempotency key·stale 검사에 넣을지 D04에서 결정하며, planner를 지금 재작성하지 않는다.

### 7.5 테스트 matrix (fake worker 우선)

| 축 | 케이스 |
| --- | --- |
| job 저장·idempotency | 동일 manifest 재실행 → 기존 draft 재사용/`duplicate_skipped`; unique 조합 선택안 검증 |
| 상태 기계 | `planned→running→draft_saved`와 각 분기(skipped_empty/stale_source/provider_error/rejected) |
| 중단·재개 | 중단 시 draft 보존·manifest 재사용, partial batch 미표시 |
| 실패 | `provider_error`만 retry, `stale_source`는 새 계획 |
| draft·승인 | 항상 draft, 수동 승인만 approved, 기존 approved/retired 보존 |
| 경쟁 | 생성 완료 시점의 원문 revision/hash 재검사(설계 §3) |
| migration | TEMP DB upgrade/downgrade·기존 행 보존(선택 a 시) |

## 8. V01~V04 정확한 증거 요건

| ID | 수용에 필요한 증거 | 과장 금지·구분 |
| --- | --- | --- |
| V01 | 전체 프론트의 **source-mapped** line/branch 수치 + raw coverage 데이터 + manifest(경로·sha256·byte). 계측 설정과 실행 로그 포함 | 기존 **국소** 수치(B03/M01~M05 변경범위)를 전체로 표기 금지. E2E/axe 통과 ≠ coverage. N/A ≠ 100% |
| V02 | 승인된 failure 시나리오 각각의 재현 로그 + 시스템의 거절/복구 동작 기록(성공·실패 모두 원문 보존). 합성 TEMP DB만 | wrong-key는 G03 범위와 분리. C11 완료를 미실시로 되돌리지 않음 |
| V03 | 채택된 경우만: 승인된 다중 프로세스/DB/transaction 구성의 동시성 실행 로그와 결과표 | 미채택 시 "불필요 판단 근거"를 기록. 완료된 CAS·잠금 경합 테스트를 실패로 되돌리지 않음 |
| V04 | 실제 외부 `metrics_v2.py` 소스 확보 경로 + 상수 비교 diff 로그(PASS/FAIL) 또는 미확보 시 skip 유지 명시 | 현재 **미설치 skip 1건**과 PASS를 구분. B01/B02/B04 수용을 재차단하지 않음 |

공통 규칙: 좁은 fixture/test 결과를 전체 수용으로 과장하지 않는다. 기존 failure log(BLOCKED·ENOMEM·504·axe 실패·격리 사고)와 현재 PASS를 구분해 보존하며, 실패 기록을 소급 PASS로 고쳐 쓰지 않는다.

## 9. G gate 실행 조건 — 필요한 사람·환경·비용·계정·백업·포트·중단 조건·완료 증거

이 지시와 이 문서는 실제 provider·운영 DB·credential/keyring·지정 장치에 접근하지 않는다.

| Gate | 사람 | 환경·계정 | 비용 | 백업 | 포트·장치 | 중단 조건 | 완료 증거 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G02 실제 OAuth/품질 파일럿 | 승인 원고 source owner, 블라인드 독립 평가자 2명, 실행 승인자 | bridge availability·정책·`gpt-5.6-luna` 확인, 지정 계정 | **USD 20 hard cap**, raw usage 기반 비용 기록 | 평가 입력 manifest(원고 원문·key·secret 미포함) | 전용 port, 임시 DB | cap 초과·오류율 초과·정책 위반 징후 시 즉시 중단 | 6사례 결과표, usage/latency/오류/비용 증거, 평가자별 채점 |
| G01 운영 DB migration | 승인자, 백업 담당과 복원 판정자 분리 | 승인된 변경 창, 대상 DB 확정 | — | 사본 SHA-256·크기·시각, Alembic current/heads, row count, `integrity_check`/`foreign_key_check`를 별도 보관 | 기존 서비스 종료 없이 계획된 창 | manifest·hash 불일치, migration/검증 실패 시 앱 재개 없이 백업 복원으로 전환 | `current==head`, 기존 row 보존, 런북 §4 smoke 통과, rollback 경로 증거 |
| G03 credential 복구/로그아웃 | credential 소유자 승인, 실행자 | 지정 테스트 credential/계정만 | — | 키 분리 설계에 따른 복구 절차 | 지정 테스트 환경 | 잘못된 키로의 우회·실제 개인 credential 접근 필요 시 중단 | 복구·로그아웃·rollback 기록, 잘못된 키 실패 검증 |
| G04 Windows 실기기 | 지정 장치 사용자/QA 계정 | Windows 11 x64 지정 장치, test DB·dummy key | — | test DB만 사용, 복원 시나리오 기록 | **전용 port** 확인, 기존 프로세스 종료 금지, 합의된 시간 창 | 장치 미지정·운영 DB/실제 keyring 우회 필요 시 중단 | batch·경로·인코딩·공존·복원, DPAPI/keyring, 브라우저·NVDA·키보드·zoom, 5만 자 성능 결과표 |

실행 순서는 G02 → G01 → G03 → G04다. 각 gate는 앞 gate와 무관하게 **자체 승인 패키지**(대상·예산·계정·백업·장치·시간 창·실행 허가)를 갖춰야 한다.

## 10. 위험 및 scope creep 방지 — 보존 계약

| 보존 대상 | 내용 |
| --- | --- |
| 고정 GPT OAuth 계약 | `ChatGPT OAuth` / `gpt-5.6-luna` / 기본 `xhigh`, localhost bridge. endpoint·모델 선택 UI 재도입 금지. legacy `ai_endpoints`/hidden routes는 호환용 보존 |
| request snapshot | directive·브리프·설정의 `structuredClone` 복제, 생성 전 `flushManuscriptDraft` + `expected_revision` 고정, 시작 토큰·회차 일치 재검사 |
| revision/CAS·원고 보존 | `expected_revision` 조건부 갱신 + `ChapterSnapshot` 생성 + 409, 같은 회차 복원만 허용 |
| memory/quality 수용 결과 | C07/C08/M01~M05의 provenance·stale·경쟁 계약, B03의 가중치/API/이력 유지. 재구현·재작성 금지 |
| fake provider·격리 runner | backend는 `backend/scripts/run_backend_pytest.py`만(Windows 내부 fresh TEMP·guard·fake keyring). frontend는 fixture-only/no-proxy/tripwire·전용 포트 |
| 생성 실패 계약 | 불완전 브리프 미전송(incomplete)·invalid 경고·실패 시 입력 유지·toast |
| 목표 분리 원칙 | 목표 저장은 `Chapter.revision` 증가·snapshot 생성과 무관, `Chapter.memo`와 혼용 금지 |

**scope creep 방지:** 완료 기능 재구현 금지. D02·U·O 자동 추가 금지. A1 LOW 참고는 별도 후속 범위로 유지하고 D01 등에서 제품 오류 계약을 바꾸지 않는다. 새 의존성·검증 도구는 먼저 근거를 제시하고 승인받는다.

## 11. Owner decision 목록과 첫 handoff prompt 초안

### 11.1 소유자 결정 대기 목록

| # | 결정 | 블로킹 대상 | 참조 |
| --- | --- | --- | --- |
| D-1 | D01 Q1~Q7 답변(특히 Q2: A vs B) | D01 상세 사양 | [질문·근거](2026-09-13-d01-contract-questions.md), [제안서 §8](2026-09-13-d01-detailed-contract-proposal.md) |
| D-2 | D01 좁은 상세 사양 승인 | D01 구현 | 결정 후 작성 |
| D-3 | D03 얇은 단위 범위 승인 | D03 구현 | §6 |
| D-4 | D04 job/idempotency 저장 방식(table vs deterministic) + fake worker 범위 승인 | D04 구현 | §7, 설계 §5 |
| D-5 | V01/V02/V04 개별 착수 승인(V03 필요 여부 포함) | 검증 보강 | §8 |
| D-6 | G02→G01→G03→G04 각 gate의 승인 패키지 | 실제 자원 수용 | §9 |
| D-7 | U01~U04·O01~O06 채택 여부 | 선택 확장 | §3.4~3.5 |
| D-8 | A1 LOW 후속(고정 일반 메시지·정제 진단·fake sentinel 회귀) 착수 여부 | 별도 후속 | 원장 §3.2 |

### 11.2 첫 handoff prompt 초안

> 다음 세션의 첫 작업은 **D01 요구 결정 요청**이다.
>
> 1. `AGENTS.md`, `docs/handoffs/2026-09-08-remaining-work.md`(원장), `docs/handoffs/2026-09-13-commit-handoff.md`, `docs/superpowers/plans/2026-09-13-d01-contract-questions.md`, `docs/superpowers/plans/2026-09-13-d01-detailed-contract-proposal.md`, 이 문서를 읽는다.
> 2. 소유자에게 Q1~Q7(특히 Q2: A 최신 목표만 vs B 이력 조회·복원)을 제시하고 답변을 받는다.
> 3. 답변을 반영해 좁은 D01 상세 사양(저장/복원/purpose/생성 연계 계약, 합성 TEMP DB·fake provider 회귀 계획)을 작성·검토한다.
> 4. **상세 사양 승인 후에만** 구현에 착수한다. 이 prompt와 기존 문서는 구현 승인을 대신하지 않는다.
> 5. 완료된 C01~C13/M01~M05/B03/C10을 재구현하지 않고, 운영 DB·실제 provider·credential·지정 장치·Git 변경·migration 실행·배포는 각 gate 승인 전 금지다.

## 12. 수용 기준·evidence manifest·독립 review·rollback 경계

### 12.1 수용 기준(각 작업 공통)

- **backend:** `backend/scripts/run_backend_pytest.py`만 사용. exit 0 + 위반 latch 0 + 실제 subprocess 시도 0을 함께 확인한다. 기존 `.coverage`(a8db…)·crypto/canon/bootstrap·Git index/HEAD를 불변 기준으로 둔다.
- **frontend:** fixture-only/no-proxy/tripwire·전용 포트·공유 Vite cache 순차 실행. axe serious/critical 0, TS/build PASS.
- **coverage:** 승인된 국소 목록에 한한 변경범위 line/branch 근거. 전체 V01로 확대 해석 금지.
- **독립 검토:** fresh 2축(제품/회귀, 데이터·격리·보존) 후 부모 수용. 검토 전후 대상 소스·보호 대상 hash 불변 확인.
- **원장 갱신:** 각 ID의 완료 범위·남은 범위·근거·승인 조건을 [전체 작업 현황](../../handoffs/2026-09-08-remaining-work.md)에서만 갱신한다.

### 12.2 Evidence manifest 규칙

- RED 로그 원문 → 최종 실행 로그 → manifest(경로·sha256·byte) → 수용 문서 순으로 보존한다.
- 실패·차단 기록(BLOCKED/ENOMEM/504/격리 사고)을 PASS로 고쳐 쓰지 않는다.
- 선별 사본과 원본 경로를 구분한다. 수용 원본의 byte archive(`.md.txt` 등)에 공백 정리·hash 교체를 하지 않는다.
- 과거 manifest의 `.git/index`·문서 hash·HEAD는 그 수용 시점의 증거다. 재계산해 덮어쓰지 않는다.
- 로컬 전용 미게시 자료(과거 감사의 로그/probe 링크)를 원격 재실행 가능 도구로 해석하지 않는다.

### 12.3 독립 review 규칙

- fresh 독립 검토는 구현 writer와 분리된 컨텍스트에서 수행한다(정적 검토임을 명시 — reviewer가 테스트를 독립 실행했다고 주장하지 않는다).
- 지적은 해결 후 retained 재검토로 종결하고, 검토 중단(BLOCKED) 이력은 보존한다.
- 부모가 근거(manifest·hash·로그)를 직접 확인한 뒤 수용을 선언한다.

### 12.4 Rollback/복구 경계

- 제품 코드 롤백은 승인된 수정 범위의 diff 역적용으로 한정한다.
- D04 backfill의 rollback은 row 삭제가 아니라 해당 batch draft의 `retired` 전환이다.
- 운영 DB rollback은 즉흥 downgrade가 아니라 검증된 백업 복원 + manifest/smoke 재확인이다.
- Git 이력 재작성·force push·자동 merge/rebase 금지. main과 원격이 다르면 중단·재조정한다.
- 이 worktree는 별도 검토용이며, main worktree의 dirty/untracked 자료를 추정·삭제·복원하지 않는다.

---

## 요약

- **생성 파일:** 이 문서 1개(`docs/superpowers/plans/2026-09-13-project-wide-execution-plan.md`). 소스·schema·migration·테스트·기존 handoff/spec 변경 없음.
- **미해결 결정:** D01 Q1~Q7(Q2 A/B가 최우선), D01 상세 사양 승인, D03 단위 승인, D04 저장 방식·fake worker 승인, V01/V02/V04 착수, G01~G04 승인 패키지, U/O 채택, A1 후속 여부.
- **즉시 가능한 다음 작업:** 소유자에게 D01 Q1~Q7 답변 요청 → 좁은 상세 사양 작성·검토·승인(§11.2 prompt). 문서·조사·계획 작업은 read-only로 가능.
- **실행 금지 작업:** D01 구현(사양 승인 전), D03/D04 구현 착수, 운영/기존 DB 접근·migration 실행·배포, credential/keyring 조회·변경, 실제 OAuth/provider/model 호출·비용 발생, 지정 장치 접근, 유료 외부 자원, stage/commit/push·Git 설정 변경, 완료 범위 재구현, legacy endpoint/모델 선택 UI 부활, 테스트·build 실행(이번 정리에서는 read-only 확인만 수행함).
