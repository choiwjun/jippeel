# 2026-09-13 최종 인계·Git 게시 경계

## 사용자 요청과 재개 위치

사용자가 **“핸드오프에 모두 남기고 커밋 푸시해”**라고 명시적으로 승인했다. 대상은 현재 `main`의 누적 프로젝트 변경·테스트·정식 문서·선별 증거다. 새 기능 개발·실제 DB/provider/credential·migration 실행·배포 승인으로 확대하지 않는다. 초기 로컬/원격 `main`은 모두 `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`이었다. 강제 push·자동 merge/rebase·이력 재작성은 하지 않는다.

**다음 작업은 D01 요구 결정 → 상세 사양·검토·승인이다.** 이 인계는 D01 구현 승인이 아니다. [단일 원장](2026-09-08-remaining-work.md)과 [D01 질문·근거](../superpowers/plans/2026-09-13-d01-contract-questions.md)를 먼저 읽는다.

## 완료한 범위 — 재개하지 않음

- 기존 기본 기능·원고 보존·공통 AI 맥락·관리 CRUD/검색·수동 기억 기반·P1 네 건·고정 GPT OAuth fake 계약·provider-free summary planner: 원장 C01~C12의 완료/운영 미검증 구분 유지.
- **C13/B01/B02/B04:** canon 실패 구조·bootstrap 슬롯/metadata·pre-import 격리/공식 runner 수용. 당시 backend419P/기존 외부 skip1/70subtests, 독립 재검토2PASS. [수용·사고 한계](../audits/failure-contracts-2026-09-12/b04-review-fixes.md).
- **M01~M05:** 프로젝트/화면 생애별 격리, 저장·복원 후 memory 갱신, 조회 오류/재시도, 확인 후 focus, 삭제409 안내 수용. 당시 backend421P/기존 skip1·UI72P, 국소 coverage·독립2PASS. [수용·원본 복구 한계](../audits/memory-m01-m05-2026-09-12/acceptance.md).
- **B03:** 약한 어미 중복/누락 및 긴 닫힌 인용 계수, 참고점수/빈 원고/essay/이력 안내, 선택적 dialog 이름 수용. 가중치/API/기존 이력/purpose/외부 adapter 유지. [최종 수용](../audits/quality-b03-2026-09-12/acceptance.md).

## 최신 검증과 한계

| 항목 | 확인된 결과 |
| --- | --- |
| B03 최종 공식 native backend | **482 passed / 1 skipped / 70 subtests / 19 warnings**, isolation violations0·실제 subprocess 시도0 |
| 서로 다른 fixture 테스트 | **quality5 + memory31 + preservation26 + AI15 = 77 passed**; 현재 품질 fullaxe3회 violations/incomplete0 |
| TypeScript/build | app/helper contextual TS·Vite build PASS |
| 변경범위 line/branch | quality19/20·10/10; QualityDialog278/284·42/48; Dialog41/41·14/14 |
| 독립 검토 | B03 제품 지적0. 현재 helper 실행 증거 E1을 exact-current5P/helperTS0로 보강한 뒤 retained2PASS·새 지적0 |

이 수치는 최근 수용된 실행 기록이지 이번 Git 게시 때 전체 suite를 새로 실행했다는 뜻이 아니다. 전체 프로젝트 coverage/V01·문학 품질·외부 metrics/V04·실제 OAuth·지정 실기기 수용을 주장하지 않는다. B03 원래218+retry25artifact, 선별107byte사본과 16source/protected hash를 검증했으며 D01 읽기 전용 조사 이후에도 16hash 불변을 확인했다.

과거 RED/격리 사고·Vite504·axe 실패·formatter/map mismatch·serializer 오류·ENOMEM은 보존한다. 최초 BLOCKED 검토를 PASS로 고쳐 쓰지 않는다. 기존 frozen v2 LSP 진단과 contextual helper 진단을 구분하며 LSP 전체 clean을 주장하지 않는다. 원래 `.coverage` 미복구/당시 credential 영향 미확정도 별도 역사적 한계다.

## Git 게시 전 검토·진단 종결

- 검토 대상은 정확히 **305개 파일**, staged tree `747b420f6b5bcc1286ffb8570a886295fd149a2f`였다. [검토 원문·hash manifest](../audits/publication-2026-09-13/manifest.json)를 보존한다.
- 코드/구성 검토 `921b3b85-54e4-4acf-81eb-33875dac5f66`: **PASS, 지적 없음**. 공식 runner·새 helper·fixture 의존성의 게시 포함, D01 미승인/미구현 구분 확인.
- 보안 검토 `d001fc65-a4bf-4269-80df-7be59d5415f7`: **PASS, 차단 없음**. 305개 파일/4,408,478byte hash·크기를 두 번 대조하고 전체 선택 byte 및 decoded JSON44,010문자열을 정적 검사했다. 실제 credential/DB/export로 남은 지적 없음. 저장소 전체 이력이나 모든 문장의 저작/개인정보 판정까지 증명한 것은 아니다.
- **A1 LOW 후속 참고:** `backend/app/routers/ai_panel.py:280`의 기존 일반 provider 오류 메시지 전달은 민감한 upstream 내용을 로컬 화면에 반영할 여지가 있다. 새로운 회귀/실제 유출은 관측하지 않았다. 고정 일반 메시지·정제 진단·fake sentinel 회귀를 별도 후속 범위로 검토하며, 이번 게시에서는 제품을 수정하지 않는다.
- 부모의 whitespace 출력 해석은 Windows 원시 로그 인코딩에서 `UnicodeDecodeError` exit1로 중단했다. 당시 305개 staged blob은 이미 hash 일치였다. 원본432,965byte 진단을 그대로 저장한 뒤 표시용 escape 파생본만 만들었다. 일반 diff-check는 CRLF/raw archive 때문에 exit2이며, 기본 공백 규칙을 유지하고 명령에만 `cr-at-eol`을 적용한 **비감사 전체 파일 검사 exit0**을 별도로 보존했다. 소스·전역 설정·원본 증거를 정규화하지 않았다.
- 보안 scanner의 최초 `python` 명령은 exit127이었다. 즉시 중단·supervisor 확인 후, 부모가 305hash와 staged tree/diff 불변을 확인하고 기존 `python3`의 읽기 전용 stdlib 검사만 명시 허용했다. 후속 검사는 성공했다. 앱/test import·runner 우회·설치·alias/전역 변경은 없다.
- 검토 이후 추가되는 것은 **이 인계/원장의 결과·A1 기록과 검토/진단 원문 사본·manifest뿐**이다. 이를 305개 원래 검토 대상과 구분하고 최종 stage에서 나머지 소스·테스트·archive hash 불변을 다시 확인한다. 두 검토의 PASS는 게시 범위이며 실제 서비스 배포 승인이 아니다.

## D01 대화의 정확한 결론

- 소스상 회차 목표는 임시 store 값이며 영속 저장·재시작 복원이 없다. 새 실행 오류를 발견한 것이 아니라 아직 없는 D01 기능이다.
- **핵심 해결책:** 작품/회차별 목표를 DB에 저장하고 다시 열 때 불러오기.
- **추가 보호 기능:** 변경 이력을 남겨 예전 목표를 조회·복원하기.
- 부모 추천은 **영구 저장 + 변경 이력 보존**이다. 사용자의 “어떤게 문제야?”, “해결방안이야?”는 설명 확인이며 A/B 선택 또는 상세 구현 승인으로 기록하지 않는다. 이후 요청은 인계·Git 게시다.
- D01 조사는 완료, 제품 코드/schema/migration은 미변경이다. 목표 버전/기준 원고 버전·원고 복원과의 관계·부분 입력 저장·purpose 복원·생성의 현재값/저장값 사용을 상세 사양에서 정해야 한다.
- 목표 저장은 목표 달성 판정이 아니다. 원고/빠른 메모와 혼용하거나 기존 생성 요청 동결·flush·출처/경합 방어를 바꾸지 않는다.

## 후속 순서와 승인 경계

1. D01 요구 결정·저장 계약·사양 승인 후 구현/회귀/독립 검토.
2. D03 기획→집필→퇴고→완결/재개를 얇게 승인. D04는 이미 끝난 planner가 아닌 실제 job/worker/draft/idempotency를 fake 기반으로 검증. D02 자동 추가 없음.
3. V01/V02/V04 검증 보강.
4. G02→G01→G03→G04는 환경·예산·접근 허가를 각각 확보한 뒤에만 실행. 운영 DB·credential·실제 provider/비용·지정 장치·migration/배포는 이번 Git 요청으로 허용되지 않는다.

## 커밋 범위·자료 보존

- 누적된 tracked 프로젝트 변경과 필요한 새 앱/테스트/공식 runner/fixture/정식 계획·runbook 및 C13/M/B03/D01 선별 증거를 명시 목록으로 검토한다. 단순 `git add .`/`git add -A`는 사용하지 않는다.
- `.eval_tmp/`, `.cc-safety-net/`, `.omo/`, `.pi-conductor/`, `backend/.coverage`, 그 밖의 이전 미추적 감사 로그/프로브는 삭제하거나 일괄 게시하지 않는다. DB/WAL/SHM·키·실제 원고는 포함하지 않는다.
- 이전 감사 Markdown 9개도 원장/사양 근거의 연결성을 위해 포함한다. 다만 `management-review.md`, `writing-review.md`, `소설집필_관리_감사.md`의 옛 로그·probe 대상 링크 18회는 **로컬 전용 미게시 자료**다. 이들 보고서를 원격에서 독립 재실행 가능한 도구 묶음으로 해석하지 않는다. 현재 C13/M/B03/D01 수용·질문 문서의 링크는 별도 선별 사본으로 제공한다.
- 수용 원본의 `.md.txt` 등은 byte archive다. 공백 정리·hash 교체를 하지 않는다. 세션의 절대 원본 경로는 당시 증거의 출처이며 원격 checkout에 그 디렉터리가 생긴다는 의미가 아니다.
- 기존 수용 manifest의 `.git/index`·문서 hash·HEAD는 **그 수용 시점**의 증거다. 이번 명시적 stage/commit 승인은 index/HEAD를 바꾸는 별도 경계다. D01/Git 인계로 갱신한 살아 있는 문서도 과거 게시 당시 hash와 구분한다. 과거 manifest를 다시 계산해 덮어쓰지 않는다.
- 공식 재검증은 [격리 runner](../runbooks/isolated-backend-tests.md)를 따른다. fixture 서버는 공유 Vite cache 때문에 순차 실행한다. 설치·cleanup·현재 서비스 종료로 환경을 바꾸지 않는다.
- 게시 커밋은 이 파일의 Git 이력으로 식별한다. 다음 세션은 로컬 `HEAD`와 `git ls-remote origin refs/heads/main`을 대조해 실제 원격 반영을 확인한다. push를 배포 성공으로 해석하지 않는다.
