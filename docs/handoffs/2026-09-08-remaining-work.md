# 전체 작업 현황 — 완료·잔여·승인 대기

최종 대조: **2026-09-13(KST)**. 기존 링크 유지를 위해 파일명은 변경하지 않았다.

**현재 작업 상태의 단일 기준은 이 문서다.** `HANDOFF.md`는 진입점과 작업 이력,
`docs/DOCUMENT_STATUS.md`는 문서 인덱스다. 아래 보존된 9월 8일 원문과 과거 문서의
“다음 작업/미완료”는 현재 할 일 목록이 아니다.

## 1. 현재 결론과 판정 기준

**2026-09-13 별도 Git 승인:** 사용자가 “핸드오프에 모두 남기고 커밋 푸시해”를 요청했다. [통합 인계·게시 경계](2026-09-13-commit-handoff.md)에 완료/증거/D01 제안·미선택/다음 순서를 기록한다. 초기 로컬·원격 main은 c1a92c4로 확인했으며, 아래 수용 당시 Git 미실행 기록을 이번 승인과 구분한다. D01 구현·운영/외부 실행 승인은 추가되지 않았다.

**후속 순차 진행 승인:** 사용자가 M01~M05 → B03 → 회차 목표/완결·재개/summary worker → V01/V02/V04 → 실제 자원 수용의 순서를 승인했다. M01~M05와 B03은 회귀·독립 검토·부모 수용을 완료했으며 다음은 D01/D03/D04 상세 계약·기획이다. [실행·승인 기록](../superpowers/plans/2026-09-12-remaining-sequence.md)을 따르며, 실제 자원은 대상·예산·계정·백업·장치와 실행 허가가 갖춰지기 전 접근하지 않는다.

- 기본 집필·관리 기능, 원고 보존, 공통 AI 맥락, 관리 무결성 보정, 수동 장편 기억 기반과
  **승인된 기억 P1 네 건은 완료**다. 같은 범위를 처음부터 다시 구현하지 않는다.
- 남은 일은 **실제 결함/후보, 미구현 제품 범위, 검증만 남은 범위, 운영·외부 승인 대기,
  선택적 확장**으로 분리한다. 프로젝트 전체나 장편 로드맵 전체를 완료로 표시하지 않는다.
- **B01/B02 실패 계약과 B04 테스트 격리 보강은 최종 수용 완료**다. 새 격리 실행 **419 passed / 외부 비교 1 skipped / 70 subtests / 19 warnings**, 독립 재검토 2건 PASS, 검토 후 소스·보존 대상 hash 불변을 확인했다.
  [최종 수용·원시 근거](../audits/failure-contracts-2026-09-12/b04-review-fixes.md)를 프로젝트에 보존했다. 실행 중인 worker/reviewer는 없다.
  최초 401개 실행의 [격리·보존 사고](../audits/failure-contracts-2026-09-12/validation-isolation-incident.md)는 소급 PASS로 바꾸지 않는다. 사용자 승인에 따라 재생성 `.coverage` a8db…를 유지했고, 옛 d6ad… 원본 미복구·당시 credential 부수 효과 미확정은 그대로 남긴다.
  당시 실제 provider/운영 DB/새 migration 파일/배포/commit/stage/push는 범위 밖이었다. Git만 위의 9월 13일 새 승인으로 분리했다.
- `main`, HEAD `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`은 B03 수용과 D01 조사까지 불변이었다.
  9월 13일 게시 사전점검에서 원격 main도 같은 SHA임을 확인했다. 누적 프로젝트 변경은 명시 목록으로 게시하고 미추적 로컬 자료는 별도 보존한다.
- **완료**는 적힌 구현·검증 범위의 완료이며 운영 적용·문학 품질 보증이 아니다.
  **후보**는 정적 근거가 있지만 이번에 새 실행 재현하지 않은 항목이다.
  **승인 대기**는 지금 실행해도 된다는 뜻이 아니다.
- **2026-09-12 사용자 정정:** prime-agent는 사용하지 않는 도구다. `AGENTS.md`의 강제 경로를 폐기하고
  현재 Pi 도구로 진행한다. 예전 P1 한정 예외를 확대 승인받을 필요가 없으며, 이 도구 때문에 작업을 막지 않는다.
  첫 안정화 범위 B01/B02는 재현을 마쳤고 [최소 수정 계획](../superpowers/plans/2026-09-12-failure-contracts.md)을 작성했다.
  기획 중복에서 첫 유효 항목을 유지하는 기준과 수정→회귀→독립 검토는 사용자 승인을 받았다. 운영/외부 승인 gate는 유지한다.

## 2. 완료 — 재작업 목록에서 제외

| ID | 작업 | 완료된 범위·근거 | 분리해서 남기는 것 |
| --- | --- | --- | --- |
| C01 | 기본 MVP 집필·관리 | 작품/권/회차, 마크다운 편집·미리보기, 상태·메모·글자 수, txt/md 내보내기, 인물·관계·로어 관리, AI/윤문 패널, 설정·라이선스 고지. [MVP 사양](../../대시보드_MVP_사양.md), [기존 QA](../../QA_개발검증_리포트_v3.md) | 축소 구현 UI는 U01~U04; 비개발자 실기기 수용은 G04 |
| C02 | 기존 집필 보조 고도화 | 기획/목차·인물 생성, 권 개요·문체 프로파일, 장면 CRUD/조립/AI, 복선 CRUD·reminder·제안, 자동 로어 주입, canon/품질 진단·이력, 감수·병렬 집필 기능. `HANDOFF.md` 고도화 이력 및 현재 소스 | 진단 B01/B02/B03 종결, 영속 작업 흐름 D01~D03, 실제 품질 G02 |
| C03 | 원고 보존 1단계 | revision 충돌, 회차별 저장 큐, 전환/늦은 응답 방어, 복구 draft, snapshot·복원, 윤문/장면 반영 안전성. [독립 최종 검증](../audits/preservation-final-validation.md) | 운영 적용 G01; 모든 삭제의 휴지통 기능까지 구현했다는 뜻은 아님 |
| C04 | 공통 AI 맥락 일관성 | 단일/병렬/감수/canon 소속·revision·본문 opt-out·관계·목적·회수 허용, 미래 계획 구분, 요청 snapshot/출처 격리. 최종화에 일반 연재 훅 점수를 강제하지 않음. [최종 검증](../audits/ai-context-final-validation.md) | M01은 **MemoryPage** 문제로, 완료된 AI 패널 맥락 수정을 다시 여는 것이 아님 |
| C05 | 관리 CRUD·검색 무결성 | 타 회차 scene reorder/타 작품 복선 참조 거부, 관계 있는 인물·복선 참조 회차 삭제 409, 회차 0개 reminder, FTS project/category scope 후 limit, 명시적 `volume:null`. `HANDOFF.md` 9월 9일 결과: 관련 54/전체 277 passed | 9월 8일의 관리 후보 재현 작업은 종료. 별도 B01/B02도 C13에서 종결 |
| C06 | 환경·빌드 정리 | Vite 중복 build 제거, AnyIO/Starlette/HTTPX 호환성 고정, 실행 shell LF 정규화. [호환성 보고](../audits/anyio-starlette-httpx-compatibility-2026-09-10.md), Windows 계획의 정적 점검 결과 | ResourceWarning 등 선택적 정리 O05; 지정 장치 QA G04 |
| C07 | 장편 기억 기반·수동 거버넌스 | MemoryEntry/migration, provenance/revision/hash/적용 시점, 승인·stale 주입 경계, generate/canon 연결, API/UI·필터·500건 이후 stale 탐색. [구현 기록](../superpowers/plans/2026-09-11-long-memory-followup.md) | UI·안내 M01~M05도 수용 완료. 더 넓은 인지 모델 D02, 운영 G01은 별도 |
| C08 | 승인된 장편 기억 P1 네 건 | 초안 폐기 오전송, POST pending 입력 보호, PATCH CAS 경쟁, chapter 삭제/기억 생성 경쟁 수정. 독립 무결성 PASS·UI PASS with notes 및 assertion 보강 완료. [최종 기록](../superpowers/plans/2026-09-11-long-memory-followup.md) | 원래 P2 다섯 건도 아래 M01~M05로 수용 완료. 테스트 assertion 지적과 worker timeout은 해결됨 |
| C09 | 고정 GPT OAuth 전환 | localhost bridge / `gpt-5.6-luna` / 기본 `xhigh`, 신규 AI 경로에서 endpoint 선택 제거, S5/S7 상태 안내, legacy 호환 경로 보존. [설계](../../기술설계_GPT_OAuth_브릿지_v1.md) | 오프라인/fake 계약 완료일 뿐 실제 로그인·provider 수용 G02/G03 미실시 |
| C10 | 자동 요약의 provider-free planner | 명시 chapter allowlist, deterministic manifest, provider 없는 계획·경계 테스트. [설계·완료 경계](../superpowers/plans/2026-09-11-long-memory-auto-summary-backfill.md) | 실제 summary job 저장/worker/draft 생성·운영 backfill D04 미구현 |
| C11 | 백업·복원·migration 임시 검증 | 원고 보존 검증의 **선택 11개 테이블 합성 데이터 full-row 백업 비교**, [9월 10일 임시 SQLite 복원](../audits/backup-restore-dry-run-2026-09-10.md), 기존 데이터 포함 migration 회귀, memory downgrade/re-upgrade, [운영 런북](../runbooks/long-memory-governance-release.md) 작성 완료 | 새 failure injection V02, 실제 DB/credential/교체·rollback G01/G03. 임시 검증 자체를 다시 할 일로 올리지 않음 |
| C12 | 평가·QA 준비와 자동화 | [실모델 평가 설계](../audits/ai-model-quality-evaluation-design-2026-09-10.md), [Windows QA 계획](../audits/windows-device-qa-plan-2026-09-10.md), 브라우저 fixture/axe·임시 실제 API/SQLite/fake-provider 통합 검증 완료 | 전체 실기기·실모델 수용이 아님. V01~V03 및 G02/G04만 잔여 |
| C13 | B01/B02 실패 계약·B04 테스트 격리 | canon 전체 구조 검증·1회 repair, bootstrap exact 슬롯·metadata 정합성, native pre-import 테스트 격리·공식 runner. 419P/외부 skip1, 독립 검토 2건 PASS·부모 수용. [최종 근거](../audits/failure-contracts-2026-09-12/b04-review-fixes.md) | 외부 metrics 비교 V04, 실제 provider/credential/운영 G gate. 과거 사고의 한계는 보존 |

## 3. 실패 계약 종결·미수정 후보

### 3.1 장편 기억 P2 다섯 건 — M01~M05 수용 완료

사용자 후속 승인 범위를 구현·회귀·독립 검토 2건 PASS 후 부모가 수용했다. [최종 수용·근거·한계](../audits/memory-m01-m05-2026-09-12/acceptance.md). 기존 P1/C13과 별도 수용이며 운영 적용을 뜻하지 않는다.

| ID | 작업 | 완료 조건 | 상태 |
| --- | --- | --- | --- |
| M01 | 작품 직접 전환 시 MemoryPage 입력·필터·pending callback 소속 분리 | A→B→A의 늦은 응답도 현재 폼·toast·focus를 건드리지 않고 원래 작품만 갱신 | **수용 완료** |
| M02 | 원문 변경 후 memory cache stale 표시 갱신 | 저장/복원 revision 성공 갱신, editor unmount 이후 save acknowledgement와 통지 예외 보존 | **수용 완료** |
| M03 | project/chapter/memory 조회 오류 표시 | 실패/loading/빈 목록 구분, 키보드 재시도·입력 보존 | **수용 완료** |
| M04 | 승인·폐기 확인 취소/완료 후 focus 복귀 | 호출 버튼 또는 사라진 버튼의 목록 fallback, 다른 화면 초점 보존 | **수용 완료** |
| M05 | 연결 회차 삭제 409 안내 수정 | retired memory도 provenance 때문에 삭제를 막는 정확한 안내·데이터 보존 | **수용 완료** |

### 3.2 실패·진단 계약 — 종결 기록과 남은 후보

| ID | 작업 | 현재 근거·이미 끝난 부분과의 구분 | 판정·다음 행동 |
| --- | --- | --- | --- |
| B01 | canon 잘못된 `issues` 응답 계약 | 구조 전체 거부·기존 1회 repair·실패 성공이력 미생성. 새 격리 전체 suite 및 독립 검토 통과 | **수용 완료 — C13**, 재작업하지 않음 |
| B02 | bootstrap 권별 슬롯·metadata 정합성 | 첫 유효 항목 선택·빈 슬롯 보충, 목차/title index/VolumeNote 정합성. 신규 회귀 32건 포함 새 전체 suite 통과 | **수용 완료 — C13**. 기존 작품 재번호 부여·스키마 변경 없음 |
| B03 | 로컬 품질 지표의 의미·계수 정확성 | tilde 없는 약한 어미·긴 닫힌 인용 계수 보정, 문체 참고점수/빈 원고/essay/이력 안내, 선택적 dialog 이름. 가중치/API/기존 이력 유지 | **수용 완료(2026-09-13)**. [최종 수용·증거](../audits/quality-b03-2026-09-12/acceptance.md). backend482P/기존 skip1·frontend77P·국소 coverage 충족, 독립 검토 E1 종결2PASS. 실제 작품 평가는 G02 |

**B04 — 테스트 격리 보강 수용 완료(C13):** Windows 내부 fresh TEMP와 import 전 guard/fake-keyring, 실제 Fernet 의미 유지, 공식 `backend/scripts/run_backend_pytest.py`를 제공했다. 첫 독립 검토의 Windows 파일명 비교·실행 가이드 지적을 보정하고 재검토 2건 PASS를 확인했다. 보호 범위는 writable-open/알려진 민감 읽기 등 명시된 검사이며 일반 OS sandbox가 아니다.

[최종 수용](../audits/failure-contracts-2026-09-12/b04-review-fixes.md), [지원 실행 가이드](../runbooks/isolated-backend-tests.md), [승인 계획](../superpowers/plans/2026-09-12-failure-contracts.md)을 따른다. 기존 401개 assertion 실행의 보존 실패·credential 부수 효과 미확정, 옛 `.coverage` 미복구는 [사고 기록](../audits/failure-contracts-2026-09-12/validation-isolation-incident.md)에 남긴다. 사용자가 유지 승인한 a8db… 생성본은 새 실행 동안 보존했다. 실제 키 저장소 조사·정책 변경·Git 반영은 수행하지 않았다.
B03은 [집필·관리 감사](../audits/소설집필_관리_감사.md)의 후보를 새 공식 격리 runner로 재현·수정·수용했다. [원래 RED·로그](../audits/quality-b03-2026-09-12/manifest.json)와 [수용 사본 manifest](../audits/quality-b03-2026-09-12/accepted-evidence/manifest.json)를 구분한다. 504·axe·formatter 계측·ENOMEM 실패 원문은 유지하고 최종 현재 파일 검증으로 해결했다. 실제 외부 metrics/provider는 실행하지 않았다.

### 게시 전 보안 참고 A1 — 낮음·별도 후속 범위

2026-09-13 게시 검토 2건은 PASS/차단0이다. 다만 `backend/app/routers/ai_panel.py:280`의 **기존** 일반 provider 오류 메시지 전달에 upstream 민감 정보가 로컬 화면으로 반영될 가능성이 있다는 LOW 참고를 남겼다. 새 회귀·실제 유출은 관측하지 않았으며 수용된 C13/B03을 재개하지 않는다. 고정 일반 메시지·정제 진단·fake sentinel 회귀의 별도 후속 범위를 검토할 수 있다. [검토 원문·범위](../audits/publication-2026-09-13/security-review.md.txt). 현재 사용자 승인은 인계·Git 게시이며 이 참고의 구현은 하지 않았다.

## 4. 미구현 제품 범위 — 구현된 기반과 분리

| ID | 작업 | 이미 있는 것 | 실제 남은 범위·착수 조건 |
| --- | --- | --- | --- |
| D01 | 영속 회차 브리프/목표 | EpisodeBrief 입력·요청 전달, Chapter.memo, 회차 목적 지시 | **소스 조사 완료 / 목표 이력 요구 결정 대기**. [질문·근거](../superpowers/plans/2026-09-13-d01-contract-questions.md). 최신값만 저장할지 과거 내용 조회·복원까지 포함할지 먼저 결정. 상세 사양·구현은 미착수 |
| D02 | 인지·상태를 구분하는 장편 기억 확장 | 근거·적용 시점·승인/stale, 미래 복선 구분, 복선의 audience_knows | 모든 사실의 작가/독자/인물별 인지, 고정 설정과 변화 상태, 사건/관계 영향 추적. 현재 수동 memory 기능 전체의 재구현이 아니라 추가 도메인 설계 |
| D03 | 기획→집필→퇴고→완결·재개 흐름 | 권 개요·인물 설정·장면·감수·원고 이력, 최종화 목적 | 목표/사건/선택/대가와 원문 근거 연결, 미해결 감수·다음 장면 재개, 결말 변경 영향, 해결/의도적 미해결/외전 이관, 집필 확정과 연재 여부 분리·완결본 관리. D01 이후 얇은 단위로 승인 |
| D04 | 실제 자동 요약·backfill | C10의 provider-free manifest planner | job/idempotency 저장 방식·schema, worker, draft 저장, stale/중복/중단·재개·실패 처리. 먼저 승인된 fake-worker 구현·검증; 실제 provider/운영 실행은 추가로 G01/G02/G03 필요 |

근거: [원래 집필 로드맵 §8.4–8.5](../audits/소설집필_관리_감사.md),
[자동 요약 설계](../superpowers/plans/2026-09-11-long-memory-auto-summary-backfill.md), 현재 모델·store.
로드맵이 있다는 사실을 상세 설계/구현 승인으로 바꾸지 않는다.

과거 감사의 “브리프에만 있는 로어 검색 누락”은 D02의 검색 입력·회수 범위에서,
“짧은 장면도 완료 처리/앞 장면 결과 없는 병렬 집필”은 D03의 분량·사건 이행·순차/병렬 조건에서
재확인한다. 새 실행 재현 없이 해결됐다고 닫거나 확정 결함으로 늘려 세지 않는다.

## 5. 검증·계측만 남음 — 기존 구현 재작업 아님

| ID | 작업 | 완료된 근거 | 미실시 범위 |
| --- | --- | --- | --- |
| V01 | 프론트 source-mapped coverage | TS/Vite build, Memory E2E/axe 통과 | 계측 설정·수치 coverage. E2E 통과만으로 프론트 80%를 주장하지 않음 |
| V02 | 복원 실패 시나리오 보강 | C11의 합성 데이터 백업/복원·migration 검증 완료 | manifest 불일치·파일 누락·잘못된 schema·disk-full 등 미수행 failure injection. wrong-key 검증은 G03 승인 범위와 분리 |
| V03 | 추가 환경/부하 범위 | 실제 독립 SQLite 세션을 이용한 CAS·잠금 경합 검증 완료 | 다중 HTTP 프로세스 부하·다른 DB/transaction 설정 검증은 미실시. 배포 구성상 필요할 때 범위를 정하며 완료된 경쟁 테스트를 실패로 되돌리지 않음 |
| V04 | 외부 im-not-ai metrics 버전 동기화 | 내부 경계 회귀 유지. 부모가 기존 미설치 skip 1건을 분리해 허용 | 실제 외부 `metrics_v2.py` 상수 비교 미실시(todo #18). B01/B02/B04 수용을 다시 차단하지 않음 |

## 6. 운영·외부·장치 승인 대기 — 지금 자동 실행하지 않음

| ID | 승인 단위 | 준비 완료 | 필요한 입력/실행과 완료 증거 |
| --- | --- | --- | --- |
| G01 | 기존 DB migration·운영 적용 | migration 코드·임시 검증·운영 런북 | 승인자/변경 창/백업·복원 담당자 → 실제 DB의 일관된 백업·manifest·복원 증거 → 승인 migration 및 데이터 보존/negative corpus/앱 smoke → 교체·rollback. 기존 DB가 head보다 뒤처졌다는 것은 마지막 확인 기록이며 이번에는 재조회하지 않음 |
| G02 | 실제 OAuth/provider 수용·문학 품질 파일럿 | 고정 provider fake 계약·평가 설계 | bridge availability/정책/모델 확인, 승인 원고 6사례와 source owner, 블라인드 독립 평가자 2명, 기대/금지 결과, raw usage/latency/비용, **USD 20 hard cap** 확정 후 호출. 실제 장편 1/20/50/100화 평가는 짧은 파일럿과 별도 후속 단계 |
| G03 | credential·key 복구/로그아웃 | bridge credential 소유 경계와 키 분리 설계 | 지정 테스트 credential/계정과 접근 승인, 복구·로그아웃·rollback 및 잘못된 키의 실패 검증. 앱이 legacy endpoint key 저장 UI를 다시 제공하는 작업은 아님 |
| G04 | 지정 Windows 실기기 수용 | Windows native 임시 DB 자동화와 WSL 실행 경로 정적 점검 | Windows 11 x64 장치/QA 계정/전용 port/test DB·dummy key/시간 창 지정. batch·경로·인코딩·공존·복원, DPAPI/keyring, 브라우저·NVDA·키보드·zoom, 5만 자 입력/검색 성능 결과표. 이미 수행한 native pytest와는 다른 수용 시험 |

운영 DB, 실제 OAuth/provider, keyring, 지정 장치에 이번 정리로 새 승인이 생기지 않는다.
실행 순서는 [운영 런북](../runbooks/long-memory-governance-release.md)과 각 승인서에서 확정한다.

## 7. 축소 구현 UI·선택 백로그·제외 정책

### 기존 사양의 축소 구현 — 없던 일로 지우거나 출시 결함으로 단정하지 않음

| ID | 항목 | 상태·다음 판단 |
| --- | --- | --- |
| U01 | 캐릭터 card_json 자유 확장 UI (F-011) | DB/API 확장과 기본 7필드 UI는 있음. `CharactersPage`에 자유 확장 편집 UI는 없음. 기존 mapping 문서와 사용자 수요를 확인해 UI 범위를 승인 |
| U02 | 로어 참조 회차 표시 (F-016, 선택 기능) | 기본 검색/편집 UI는 있음. `LorebookPage` 상세에 참조 회차 목록 UI 없음. 선택 범위를 채택할 때 연결 |
| U03 | 윤문 명령 프리셋 UI | 과거 디자인/인계의 미연결 항목. 현재 RefineTab은 기본 강도·고지 중심. 고정 OAuth/외부 humanize 경계에 맞춰 필요한지 재결정; 임의 shell 실행 UI를 추가하지 않음 |
| U04 | 시니어 전용 확대 모드 | 다크/라이트·본문 폰트·행간은 있음. 전용 글자 확대 토큰은 없음. G04의 zoom/가독성 결과로 필요성을 판단 |

### 현재 우선순위 밖의 선택 확장

- O01: SillyTavern 카드 PNG import/export, novelWriter import.
- O02: 자동 주기 백업·클라우드 동기화·Git 기반 버전 관리·추가 삭제 복구 UI. 기존 snapshot·수동 백업 검증과 별개.
- O03: 연재 캘린더·멀티 작품 통계, 플랫폼 직접 발행 연동(정책 확인 전 보류).
- O04: 새 provider/모델 선택지, KoboldCpp native, 임베딩 검색·병렬 작업자 수 확대. 현재 고정 OAuth 계약에서는 우선하지 않음.
- O05: 비차단 ResourceWarning/호환 helper 중복 정리·유지보수 모니터링. 해결된 Vite/AnyIO 경고를 포함하지 않음.
- O06: 배포/게시 판단 전 플랫폼 규정·의존성/라이선스 최신 근거 재확인. 오래된 리서치를 최신 사실로 취급하지 않음.

**되살리지 않을 것:** 신규 endpoint/API key/base URL·모델 선택 UI는 의도적으로 제거했다.
legacy `ai_endpoints`/hidden routes는 보존·migration 호환용이지 재도입 할 일이 아니다.
AI 자동 삽입·무검수 자동 승인·탐지 회피 기능도 추가하지 않는다.

## 8. 후속 순서 — 사용자 순차 진행 승인 반영

실행 순서는 [9월 12일 순차 승인 기록](../superpowers/plans/2026-09-12-remaining-sequence.md)을 따른다. 아래는 기존 의존성 참고이며, 실제 자원에 대한 대상/비용/접근 승인은 별도로 충족해야 한다.

1. **안정화 종결:** B01/B02/B04는 C13, M01~M05와 B03도 수용 완료다. 완료된 범위를 다시 열지 않는다.
2. **다음 승인 묶음:** D01 → D03 → D04의 상세 요구·저장/상태/job 계약·기획부터 진행한다. 로드맵을 상세 구현 승인으로 대신하지 않으며 기존 planner를 재구현하지 않는다. D02는 이 묶음의 자동 추가 범위가 아니다.
3. **검증 보강:** 그 다음 V01/V02/V04. V03은 배포 구성에 필요할 경우만 채택한다.
4. **실제 자원 수용:** G02 → G01 → G03 → G04 순서로 환경·예산·접근 허가 등 개별 gate를 충족한 뒤만 실행한다.
5. U/O 항목은 핵심 안정화와 실제 작가 사용 결과 뒤에 선택한다.

## 9. 검증 수치의 최신성과 근거

| 증거 층 | 가장 최근 확인한 결과 | 해석 한계 |
| --- | --- | --- |
| 전체 backend — B03 최종 | **482 passed / 1 skipped / 70 subtests / 19 warnings** | native isolated runner, exit0·guard 위반0·실제 subprocess 시도0. 기존 외부 metrics skip(V04) 유지 |
| B03 frontend·접근성 | **quality5 + memory31 + preservation26 + AI15 = 77 passed**, app/helper TS·build PASS | 전용 fixture-only/no escapes. quality fullaxe3회 violations/incomplete 0, 지정 실기기 아님 |
| B03 변경범위 coverage | quality **19/20·10/10**, QualityDialog **278/284·42/48**, Dialog **41/41·14/14** (line·branch) | Python L34는 미계측 실행행으로 미충족 유지. source/map 일치·raw merge/Istanbul 독립 재구성. 전체 V01 아님 |
| B03 독립 검토·보존 | 제품 지적0, E1 현재 보조 파일 증거 종결 **2 PASS** | 218원래+25retry artifacts·16source/protected hashes, 초기 BLOCKED/ENOMEM과 최신 helper hash 구분 |
| M01~M05 당시 전체 backend | **421 passed / 1 skipped / 70 subtests / 19 warnings** | 당시 수용 결과이며 B03의 482개와 합산하지 않음 |
| B01/B02/B04 coverage | bootstrap line **96.19%** / branch **81.52%**, canon **87.10% / 83.33%**, guard **93.44% / 91.67%** | 3모듈만 계측. 전체 backend/프론트 coverage 아님 |
| B04 독립 재검토·보존 | 코드 **PASS**, 격리·보존 **PASS** → 부모 수용 | read-only 검토. 37개 app 소스 및 승인된 coverage 보존; LSP **clean 0 / inconclusive 5** |
| M01~M05 frontend | **Memory 31 / preservation 26 / AI fixture 15 = 72 passed**, TS/helper TS/build PASS, axe serious/critical 0 | fixture-only positive no escapes. 지정 Windows 실기기 수용 아님 |
| M01~M05 변경범위 coverage | Memory line **60/60**, branch **33/33**; drafts **2/2**, branch N/A; queryClient **11/11, 5/5**; App N/A; projects literal **1 → 실행문장 1** | source-mapped 국소 계측. N/A≠100%, raw Python L299 미계측. 전체 V01 미완료 |
| M01~M05 독립 검토·보존 | 상태/접근성 **PASS**, 격리/계측 **PASS**, 부모 수용 | 356 artifact·29 source·5 protected hash 직접 확인. LSP diagnostics0 / clean1 / inconclusive4 |
| P1 당시 전체 backend | **317 passed** | 역사적 P1 수용 로그. 최신 전체 결과는 위의 482개 |
| P1 관련 backend + coverage | **64 passed** | 전체 317과 합산하지 않음 |
| P1 당시 Memory Playwright/axe | **6 passed**, assertion 보강 후 부모 재통과 | 다른 모든 UI의 현재 재실행 결과는 아님 |
| TypeScript/Vite build | **PASS** | 지정 Windows 기기 수용과 다름 |
| 핵심 3모듈 branch 포함 coverage | memories **93%**, projects **85%**, long_memory **93%**, 합산 **90%** | 전체 저장소/프론트 coverage 아님; 예전 4모듈 93.59%와 분모가 다름 |
| 독립 검토 | 무결성/security **PASS**, UI **PASS with notes** → assertion 보강 | 정적 검토. reviewer가 테스트를 독립 실행했다고 주장하지 않음 |

저장소 내 최신 근거: [B03 최종 수용](../audits/quality-b03-2026-09-12/acceptance.md), [B03 최종 사본 manifest](../audits/quality-b03-2026-09-12/accepted-evidence/post-write-manifest.json).
M01~M05 수용 당시: [최종 수용](../audits/memory-m01-m05-2026-09-12/acceptance.md), [사본 manifest](../audits/memory-m01-m05-2026-09-12/accepted-evidence/post-write-manifest.json).
B04 수용 당시 근거: [B01/B02/B04 최종 수용](../audits/failure-contracts-2026-09-12/b04-review-fixes.md), [필수 실행·검토 증거 manifest](../audits/failure-contracts-2026-09-12/accepted-evidence/manifest.json).
기존 P1/UI 수치는 당시 [P1 수정·최종 수용 기록](../superpowers/plans/2026-09-11-long-memory-followup.md)이며 B04에서 UI/build를 재실행하지 않았다.
로컬 근거(원격 checkout에 자동 제공되지 않음):

- 최종 수용: `/home/hunter8891/.pi/agent/sessions/--mnt-c-Users-wj941-Documents-jippeel--/subagent-artifacts/outputs/2c5a47a8-9c26-4766-8b62-2b1981a198ac/parent-acceptance.md`
- 최초 기억 검토: 같은 sessions 하위 `subagent-artifacts/outputs/a3b64221-53bb-476a-b99d-533595151ec7/reviews/parent-synthesis.md`
- 실행 로그: `/tmp/jippeel-memory-p1.Ge5TLu/{full-final-backend,coverage-final-backend,final-build,parent-reviewed-frontend}.txt`

예전 **108 passed / 294 passed·9 failed·1 skipped**는 당시 기록으로 보존한다.
P1 당시 im-not-ai 외부 script 실패는 최종 실행에서 재현되지 않았다. B04에서는 mocked executor 테스트의 파일 존재 전제만 owned TEMP의 fail-if-executed sentinel로 충족했으며 실제 호스트 스크립트는 실행하지 않았다. 외부 metrics 소스 비교 1건(V04)은 미검증이다. 영구 환경 해결이나 실제 외부 호환성 PASS로 확대하지 않는다.

## 10. 옛 목록의 종결·이관표

| 옛 항목 | 현재 판정 |
| --- | --- |
| 9월 8일 §2 “다음 작업: 관리 후보 재현” / 우선순위 1 | C05 완료 — 재개하지 않음 |
| 9월 8일 우선순위 2 “canon/기획 생성 실패 계약” | B01/B02/B04 **C13 수용 완료** — 419P/기존 외부 skip1, 독립 검토 2건 PASS. 과거 사고의 한계는 보존 |
| 9월 8일 우선순위 3 “독립 평가 설계” | 설계 C12 완료 / 실제 평가 G02 대기 |
| 9월 8일 우선순위 4 “장편 기억” | 기반·수동 UI C07/C08 및 M01~M05 보정 완료 / D02 확장 / D04 자동화 / G01 운영 분리 |
| 9월 8일 우선순위 5 “영속 목표·완결” | D01/D03 미구현 유지 |
| 9월 8일 우선순위 6 “백업·복원” | 임시 검증·런북 C11 완료 / V02 실패 보강 / G01/G03 실제 실행 대기 |
| 9월 8일 우선순위 7 “Windows QA” | 계획·정적 점검 C06/C12 완료 / G04 지정 장치 수용 대기 |
| Vite/AnyIO 경고, memory prompt 연결/UI, 임시 rollback | C06/C07/C11 완료 — 과거 HANDOFF에서 다시 가져오지 않음 |
| MVP §7의 로어 자동 주입·장면·연속성 검사 “백로그” | 기본 기능 C02 완료. 더 넓은 품질·시간축 요구만 B/D/G로 분리 |
| QA v3의 axe “전부 pending” | 자동화한 범위 C12 완료 / M04 및 G04 수동 영역만 구분 |
| 원래 P2 5건과 새 테스트 assertion 지적 | M01~M05 수용 완료. assertion은 C08에서 해결 |
| prime-agent 부재 / worker timeout | P1 timeout은 복구 완료. 이후 사용자가 prime-agent 미사용을 명시해 강제 경로도 폐기했다. 현재 Pi 도구를 사용하며 prime-agent 승인 대기는 종료 |

상태 변경 시 해당 ID의 **완료 범위·남은 범위·근거·승인 조건**을 여기서 갱신한다.
사양·runbook은 동작/절차를 정의하고 작업 상태는 이 문서를 링크한다.
수치가 없는 제품 확장/수동 QA를 섞은 “전체 완료율”은 계산하지 않는다.

---

## 보존된 2026-09-08 인계 원문 — 현재 실행 목록 아님

아래는 당시 승인·소스·후보를 보존한 이력이다. 당시 commit/push 승인은 이번 정리에 재사용하지 않는다.
완료/잔여 판단은 위의 종결·이관표와 현재 작업표가 우선한다.

## 1. 현재 상태와 이번 요청의 경계

- 작업·게시 대상: **main**. 기존 검증 브랜치의 변경을 fast-forward로 main에 통합했다. 새 기능 브랜치는 만들지 않는다.
- 기능 검증 기준: 소스 `cd7fc1f3360b6e42d49ab75398b94732ed057649`, 문서 `92c9cda995d10ef565b0af631cf5038206a63a3e`.
- 원고 보존 1단계와 AI 맥락 일관성은 구현·독립 검토가 끝났다. 다시 미완료 작업으로 열지 않는다. [보존 결과](../audits/preservation-final-validation.md), [AI 맥락 결과](../audits/ai-context-final-validation.md).
- 최근 검증은 backend269 / UI·SPA15 / 보존17 / 가짜 제공자 실제 통합3 및 build PASS다. 각 검증 층의 수치는 합산하지 않는다. 새 기능이나 실모델 품질 전체의 통과를 뜻하지 않는다.
- **이번 승인은 남은 작업 문서화·main 커밋·push까지다.** 아래 기능 구현, 실제 모델 호출/비용, 운영 DB 접근·마이그레이션·배포는 별도 승인 대상이다. Git push를 운영 배포로 간주하지 않는다.

## 2. 다음 한 작업

**관리 데이터 무결성 후보를 현재 버전의 격리 API에서 재현하고, 첫 수정 범위를 확정한다.**

AI 요청에서 잘못된 소속을 거부하는 기능이 완성됐어도, CRUD가 잘못된 참조를 저장하거나 삭제/검색에서 실패하는 문제까지 해결됐다는 뜻은 아니다. 아래 후보는 과거 감사와 현재 정적 검토에 근거한다. **이번 인계 작업에서 새 실행 재현을 하지 않았으므로 현재 재현 확정 결함으로 단정하지 않는다.**

첫 산출물은 후보별 재현 결과/실패 테스트, 영향 데이터, 최소 수정안이다. 실제 운영 데이터 대신 새 합성 TEMP DB를 사용한다. 재현된 항목만 구현 계획으로 올린다.

## 3. 우선순위와 완료 조건

| 순서 | 작업 | 최소 완료 조건 | 현재 상태 |
| --- | --- | --- | --- |
| 1 | 관리 CRUD·조회 무결성 | 타 작품 장면 reorder 및 복선 회차 참조 거부; 관계가 있는 인물 삭제 및 복선에 연결된 회차 삭제 정책; 회차 없는 작품 reminder; 작품별 FTS 제한 순서; `volume:null` 이동을 각각 재현하고 회귀 테스트로 검증 | 과거 재현/현재 정적 후보, 새 재현 필요 |
| 2 | 모순 응답·기획 생성의 실패 계약 | 기존 JSON 파싱 실패 처리는 유지하고, 파싱 가능한 잘못된 `issues` 스키마가 실제 모순 0건으로 처리되지 않게 구분. 부트스트랩 결과의 권별 회차 수·순서·중복·폴백을 검증 | 후속 후보, 현재 버전 재현부터 |
| 3 | 문학 품질의 독립 평가 설계 | 작가가 미리 고정한 설정·사건 정답, 블라인드 비교, 모델/분량/예산 통제, 채택률·수정량·모순율·시간/비용 기록. 합격 기준을 실행 전에 승인 | 실제 모델·문학 품질 미검증 |
| 4 | 회차 시점별 작품 기억 | 근거 원고/revision/적용 시점/승인 여부를 가진 사실·변경 후보. 작가/독자/인물 인지를 구분하고 과거 수정 영향 표시. 1/20/50/100화 고정 사례로 과거·미래 혼입 검사 | 설계·구현 별도 승인 필요 |
| 5 | 영속 회차 목표·기획·퇴고·완결 연결 | 브리프 재진입 복원; 목표·사건·선택·대가를 원고 근거와 연결; 해결/의도적 미해결/외전 이관을 구분; 최종본 보존 | 후속 범위. 현재 세션 설정은 영속 목표 관리가 아님 |
| 6 | 완전 백업·복원과 운영 적용 준비 | 일관된 DB 백업을 별도 환경에 복원하고 원고 외 설정/관계/복선/장면/이력, 필요한 키 복원까지 검사. 구버전 복제 DB upgrade, rollback 및 프론트/백엔드 동시 적용 계획 확보 | 운영 DB·실제 키 복원·배포 미실행. 별도 승인 필요 |
| 7 | 실제 Windows 기기 QA | 접근성/NVDA/키보드/시니어 모드, 대용량 편집·검색 성능, 암호화·복원 동작을 합의된 환경에서 측정하고 결과표 작성 | 기존 수동 QA 항목 재검토 필요 |

3번의 평가 기준·샘플 설계는 초기에 준비하되 실모델 호출은 별도 승인 후 한다. 4→5는 의존 순서다. 6번은 출시 전 필수 조건이지 지금 운영 환경을 만져도 된다는 뜻이 아니다.

### 관리·실패 계약 후보의 코드 진입점

- 장면 reorder: `backend/app/routers/scenes.py`
- 복선 참조/reminder: `backend/app/routers/foreshadows.py`
- 관계 있는 인물 삭제: `backend/app/routers/characters.py`, `backend/app/models.py`
- 작품별 FTS 검색: `backend/app/routers/lorebook.py`의 검색 구현
- 명시적 권 미지정 이동: `backend/app/routers/projects.py`, `backend/app/schemas.py`
- canon 응답 검증: `backend/app/services/canon.py`
- 생성 계획 보충/검증: `backend/app/services/bootstrap.py`

정적 의심이 실제로 재현되지 않으면 해당 후보를 닫거나 검증 범위를 좁힌다. 오래된 감사의 행 번호나 당시 테스트 수치를 현재 결과로 재사용하지 않는다.

## 4. 완료된 부분을 다시 깨뜨리지 않을 기준

- [AI 맥락 검증 규칙](../audits/ai-context-lessons.md), [원고 보존 규칙](../audits/preservation-lessons.md)을 먼저 읽는다.
- 본문 opt-out과 회차 식별은 별개다. 생성/모순 검사/품질의 관계 대상 정책도 다르다.
- 실제 제공자 메시지와 저장 본문에서 독립 계산한 hash를 확인한다. 동일 모델의 자기 감수를 정답으로 쓰지 않는다.
- 페이지 새로고침이나 테스트의 ID 주입으로 stale-state를 지우지 않는다. 동일 SPA runtime과 남은 이전 editor/draft 상태에서 전환을 검사한다.
- 첫 await 전 snapshot, 이후 토큰·출처 확인, 회차별 저장 큐·revision·복구 잠금·명시적 반영을 유지한다.
- 검증 환경은 [AI 재실행 안내](../runbooks/ai-context-consistency.md)를 따른다. Windows native, 새 TEMP DB, import 전 환경 설정, 실제 통합은 Alembic head/우회 제거가 기준이다.

## 5. 작업 공간·공유 주의사항

- `.eval_tmp/`, 과거 감사 원시 로그·프로브·미추적 문서는 이번 인계 커밋에 일괄 추가하지 않는다. DB/WAL/SHM·키·실제 원고를 push하지 않는다.
- 일부 과거 감사와 원시 증거는 로컬에만 있다. 이 문서는 해당 미추적 문서가 없어도 남은 범위를 파악하도록 요약했다. 원격 checkout에서는 커밋된 테스트와 runbook으로 새 격리 증거를 만든다.
- [기존 수동 QA 가이드](../../QA_수동검증_가이드.md)는 항목 목록 참고용이다. 과거 기본 포트/DB 직접 접근/구형 API 명령을 그대로 실행하지 않는다. 현재 `expected_revision` 계약과 별도 테스트 환경에 맞게 개정하고 승인받은 뒤 사용한다.
- 기존 서비스나 점유 포트를 종료하지 않는다. 운영 DB/키 복원은 문서화 승인과 구분한다.
- 저장소의 main과 원격 main이 다른 경우 force push하지 않는다. 원격 변경을 확인하고 중단·재조정한다.

## 6. 낮은 우선순위·지금 늘리지 않을 것

- 비차단 Vite 중복 `build` 키 경고, anyio deprecation, 호환 helper 중복은 별도 작은 정리 작업으로 다룬다. 과거 검토 snapshot을 공백 정리 때문에 일괄 바꾸지 않는다.
- 프리셋·모델 선택지·병렬 작업자 수·외부 연동·외형 화면을 먼저 늘리지 않는다. 임베딩 도입은 시간축·근거·승인 흐름의 대체재가 아니다.

## 7. 다음 담당자의 시작 체크리스트

1. `git status --short`, 현재 `main`/원격 ref와 기능 기준 커밋을 확인한다. 기존 미추적 자료를 삭제하거나 일괄 stage하지 않는다.
2. 완료 보고서와 lessons를 읽고 완료 범위를 재개하지 않는다.
3. 2절의 관리 무결성 후보를 새 임시 환경에서 재현하는 범위부터 제안한다.
4. 재현/수정 계획 승인 → 회귀 테스트 → 최소 구현 → 독립 검토 → 실제 경계 재검증 순서를 따른다.
5. 실제 모델/운영 배포가 필요해지면 데이터·비용·백업/복원·중단 조건을 따로 승인받는다.
