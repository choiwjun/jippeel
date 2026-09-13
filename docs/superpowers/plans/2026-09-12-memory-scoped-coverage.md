# M01~M05 변경범위 coverage 보강 — 부모 결정

- 근거: worker 요청 `259ad9da-11cf-4108-a66d-01121f40fa5a`.
- 기존 `--isolation-coverage`는 canon/bootstrap/guard만 계측한다. 이 값을 변경한 MemoryPage·저장 통지·projects.py의 coverage로 주장하지 않는다.
- 부모가 frontend에서 `v8-to-istanbul`, `@vitest/coverage-v8`, `istanbul-lib-coverage` 부재와 `@jridgewell/trace-mapping`, Playwright 존재를 확인했다. 정량 게이트를 검증되지 않은 %로 대체하거나 면제하지 않는다.
- 이번 보강은 **M01~M05 국소 검증**이며 전체 프론트 V01 완료가 아니다. 실제 provider/운영 DB/credential/지정 실기기/Git 실행은 포함하지 않는다.

## 고정된 최소 예외

1. backend의 기존 `backend/tests/isolation_guard.py`에서 `--isolation-coverage`용 **고정 source 목록에 `app.routers.projects` 한 항목만 추가**하는 것을 허용한다. 임의 `--cov` 인자 허용·새 CLI 옵션·환경 우회는 금지한다. import 전 guard·fake-keyring·소유 TEMP·latch·CLI/config override 거부는 불변이다. 이 한정 예외 외에 runner/guard는 동결한다. 해당 선택의 회귀와 stdlib preflight 후 같은 native runner로 검증한다.
2. frontend는 Playwright의 Chromium V8 coverage를 수집하고 source map으로 원본 TS/TSX에 매핑한다. 검증용 `v8-to-istanbul@9.3.0` 및 필요한 전이 의존성을 **owned TEMP 도구 디렉터리**에만 설치할 수 있다. 프로젝트 package/lock/node_modules·전역 설치는 변경하지 않는다. 공개 npm registry, 빈 owned npm 설정, install scripts/audit/fund 비활성화를 사용하며 credential을 조회하거나 출력하지 않는다. 정책 거부가 있으면 우회하지 않는다.
3. 기존 테스트 의미를 바꾸지 않는 작은 수집 fixture/helper 및 TEMP 변환 스크립트를 허용한다. 앱에 테스트 전용 전역·endpoint를 추가하지 않는다. 원시 V8 데이터·실제 변환 JS/source map·원본 source hash·변환 결과를 보존한다. 대상은 미리 정한 실제 변경 production 파일만이며 source map 외부 경로나 자격 증명은 읽지 않는다.

## raw V8 merge·helper 정적 검사 추가 승인

worker의 exact-location union 방식 초안은 테스트마다 달라지는 V8 nested-range 모양을 정확히 합성하지 못했다는 보고가 있다. 초안은 미수용으로 보존하고 표준 merge를 검증한다. 기존 요청 `c936245f-dc89-4623-8434-20c45f683cce`의 대기 만료 후, 새 요청 `cbb85203-9b99-4fad-b8ab-720cd66ac313`에 동일 run 계속 승인을 전달했다.

- `@bcoe/v8-coverage@1.0.2`, 필요한 경우 `istanbul-lib-coverage@3.2.2`, helper 정적 검사에 필요한 `@types/node@22.0.0`을 위와 같은 **owned TEMP/clean npm/공개 registry/scripts 비활성화** 조건으로만 허용한다. 부모는 각 pinned registry metadata의 존재를 확인했다.
- 원본 source·실제 변환 JS·source-map hash가 같은 그룹끼리 raw V8를 먼저 merge한다. URL만 같다고 다른 코드의 offset을 합치지 않는다. 다른 변환 그룹은 각각 원본으로 매핑한 뒤 표준 Istanbul merge를 적용할 수 있다.
- nested-range 모양 차이, 실제 미실행 branch, 다른 source 혼입 방지의 작은 합성 사례로 merge를 검증한다. 실제 미실행 경로를 covered로 바꾸지 않는다.
- 원시 자료와 초안을 보존하고 수정 보고서를 별도로 만든다. 선정 규칙은 그대로 유지하며 알고리즘 보정에 따른 분모/값 변화는 이전·이후·이유를 기록한다.
- 54 samples와 memory30/preservation25/AI15 tests의 차이를 설명한다. 각 표본은 safe run/log/test id와 source/JS/map hash에 연결하며 미계측·page-close 누락 등을 숨기지 않는다. 과거 격리 실패 run을 최종 근거에 섞지 않는다.
- 적합한 기존 Node types는 path/version 기록 후 사용할 수 있으며, 아니면 위 TEMP types와 독립 TEMP tsconfig를 사용한다. 프로젝트 설정 변경이나 오류 은폐용 any/ignore는 금지하고 앱 TS/build는 별도 유지한다.

## catch 분기 누락 정정·직접 회귀 승인

worker self-review에서 AST 실행행 목록으로 branch까지 필터링하면 실제 변경된 `catch` 분기가 빠지는 문제가 확인됐다. helper의 기존 `3/3` branch 초안은 최종 수용 수치가 아니며, catch를 포함한 `3/4 (75%)`를 기준으로 미실행 경로를 보강한다. line 선정 규칙과 branch 선정을 혼동하지 않고, **변경된 모든 source 행에 매핑된 계측 branch**를 최종 분모에 포함한다. 초안과 보수적 보고서의 차이를 보존한다.

요청 `1e1d8172-eb7f-4784-a77e-6fd31f2262a8`에 승인한 test-only 보강:

- 실제 편집·저장 UI를 실행하되 원래 작품 memory query의 실제 save-ack invalidation 이벤트에서만 QueryCache subscriber가 한 번 예외를 던지도록 fault injection한다. 본문·expected_revision·서버 revision·저장 완료와 generic console error를 직접 확인하고 다른 오류를 숨기지 않는다. subscriber 해제 후 정상 화면 흐름의 memory 회복을 검증한다.
- 현재 화면 PATCH 실패를 실제 fixture 실패 응답으로 재현해 toast·입력·확인 대상·pending 해제와 재시도 가능성을 확인한다.
- 제품 source·저장 큐·app 전역/API는 불변, manual invalidation으로 결과를 만들지 않는다. 영향받는 전체 fixture를 재실행하고 새 source-mapped coverage를 수집한다.

## 사전 판정 기준

- 기준은 M01~M05 시작 baseline 대비 **추가/변경된 실행 가능 소스 행**, 그리고 해당 변경에서 발생한 계측 가능한 branch다. 전체 모듈 수치도 참고로 별도 표시한다. 결과를 보고 유리하게 분모를 축소하지 않는다.
- 변경 executable line/branch 각각 **80% 이상**을 확인한다. 분모가 0인 항목은 N/A이지 100%가 아니다. 누락된 변경 소스·미로드 파일을 집계에서 숨기지 않는다.
- coverage ignore 지시·실패 skip·핵심 assertion 삭제·테스트에서 cache 수동 무효화로 통과시키지 않는다. 부족한 변경 경로는 정상적인 국소 회귀를 추가한다.
- 실제 매핑이 불가능하거나 도구/권한/의존성 문제가 있으면 부족한 증거를 보고한다. 일반 JSX 변환 JS의 %를 TSX 원본 수치처럼 표시하지 않는다.
- M01~M05 행동 회귀·전체 backend·TS/build·axe·소스 보존을 계속 검증한다. 기존 실패 로그 및 정상 발견용 exit4/no tests는 성공 실행과 분리한다.
- 독립 reviewer는 이 승인된 instrumentation-only 예외와 측정 정합성을 함께 검토한다. B01/B02/P1 제품 계약을 다시 여는 것이 아니다.

## 재개 시 Python 다중행 문장 매핑 결정

- 요청 `1264f399-64ca-4176-868b-9def84d1984c`에 대한 부모 결정. 새 공식 runner의 421 passed / 기존 skip 1 / 70 subtests와 `violations=[]`, `subprocess_attempts=0`을 직접 확인했다. `assert 299 in executed_lines` 실패는 그 이후 측정 reader의 잘못된 가정이며 backend 테스트 실패가 아니다.
- 현재 `projects.py` SHA-256 `3953fd5e4e60e292c9d936e269f12066de74975ffd1ddcfd2402394abc330c95`에서 변경된 L299는 L297–300 `raise HTTPException(...)`의 직접 `detail=Constant`다. 부모가 앱 import 없이 AST를 확인했다. coverage.py 7.16.0은 L297 실행을 기록하고 L299는 executed/missing/excluded 어느 목록에도 넣지 않았다.
- **동결 변경 단위 분모 1을 유지**하고, 이 직접 literal만 containing Raise의 계측 문장 L297에 연결하는 source→statement 매핑을 허용한다. 원시 coverage JSON은 변경하지 않는다. raw L299 자체가 계측·실행됐다고 주장하지 않고, 결과는 “변경 literal 1개 → 실행 문장 1개”로 명시한다. 새로운 branch가 없는 이 literal은 branch N/A이며 100%가 아니다.
- 매핑은 source hash·AST 범위·직접 keyword Constant·coverage executable 문장·draft/approved/retired 삭제의 정확한 응답 문구 회귀를 함께 증명해야 한다. 조건식/short-circuit/lambda/comprehension 등 임의 미실행 자식이나 함수 전체로 일반화하지 않으며 모호하면 unmapped로 차단한다. 누락/미실행 문장·잘못된 hash·허용하지 않은 AST 모양은 작은 합성 검증에서 실패해야 한다.
- 실패 assertion 뒤 복합 shell이 memory focused 25개를 계속 실행한 사실은 보존한다. 이후 명령은 exit를 즉시 검사하는 단일 실행 또는 fail-fast 연결로 제한하고, 해당 focused run은 새 정상 실행과 분리한다. 앱·runner 변경 없이 reader/측정 근거만 보정하고 동일 native workflow로 진행한다.

## 공개 근거

- npm pinned metadata: <https://registry.npmjs.org/v8-to-istanbul/9.3.0>
- 공식 사용법: <https://raw.githubusercontent.com/istanbuljs/v8-to-istanbul/v9.3.0/README.md>
- `.load()` → `.applyCoverage(V8 ranges)` → `.toIstanbul()`이며, source map/원본 소스 연결의 실제 정합성은 이번 산출물로 검증해야 한다.
