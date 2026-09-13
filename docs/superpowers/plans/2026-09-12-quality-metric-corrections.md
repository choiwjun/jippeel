# B03 품질 지표 최소 보정안 — 수용 완료

- 상태: **2026-09-13(KST) 최종 수용 완료**. [수용 기록·검증·독립 검토](../../audits/quality-b03-2026-09-12/acceptance.md). 이후 설명의 RED/구현 순서는 보존된 승인·조사 이력이다.
- 승인: 2026-09-12, 사용자가 두 계수 오류 수정과 가중치·API·기존 이력 유지, 문체 참고점수·빈 원고 경고의 추천안에 **“진행해”**로 응답했다. 아래 호환성 계약으로 진행한다.
- 선행 M01~M05는 수용 완료이며 재개하지 않는다. 사용자 순차 승인 범위 중 두 번째 단계다.
- 근거: [전체 재현 보고서 원문](../../audits/quality-b03-2026-09-12/reproduction-plan.md.txt), [증거 manifest](../../audits/quality-b03-2026-09-12/manifest.json).
- main HEAD `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`. 조사 단계는 test-only 재현 파일만 추가했다. 승인된 제품·frontend 최소 변경과 검증을 마쳤으며 provider·DB/schema·Git 변경은 없다.

## 확인한 사실

| 구분 | 현재 관찰 | 해석 |
| --- | --- | --- |
| 결함 1 | `하게 된다`는 ending 0, `~하게 된다`는 탐지 | 설정의 설명용 `~`를 실제 문자로 검색하여 일반 문장을 놓침 |
| 결함 2 | 닫힌 200자 인용은 계산하지만 201자/400자는 비율 0 | 200자까지만 자르는 것이 아니라 긴 인용 전체가 빠짐 |
| 제품 판단 | 빈 원고 serial 65 / finale 85, 짧은 `"!"!`도 100 | 정해진 규칙의 감점 결과이지 문학 품질 검증이 아님. 임의 점수 가중치 조정 근거는 없음 |
| 외부 참고치 | synthetic adapter가 `genre="essay"`를 받고 v2는 내장 점수에 합산되지 않음 | 실제 외부 엔진 정확도·지원 소설 장르는 미검증(V04) |

공식 native 격리 runner의 기존 quality 11개 PASS, 새 진단 41개 PASS와 **의도한 결함 재현 2개 FAIL**을 확인했다. 선택 진단+기존 52개 PASS는 실패 2개를 해결했다는 뜻이 아니다. 모든 실행 `violations=[]` / `subprocess_attempts=0`; 운영 DB·실제 외부 module/provider를 사용하지 않았다. 당시 두 RED는 원시 보고서와 before snapshot으로 보존하고, 현재 `backend/tests/test_quality_b03_reproduction.py`는 승인 계약에 맞게 GREEN으로 전환했다.

## 추천 계약 — 호환성 유지 최소안

1. **어미 계수:** 설정된 약한 표현에서 설명용 tilde를 요구하지 않는다. 약한 표현 속 일반 어미를 중복 계수하지 않고 긴 표현 우선의 비중첩 발생 횟수를 센다. 형태소/문장 경계 분석으로 확대하지 않는다. 분모·반올림·점수 가중치는 유지한다.
2. **인용 비율:** 닫힌 긴 인용의 내부 전체를 센다. 기존 지원 따옴표·단일 인용/불일치 family 정책과 분모는 유지한다. 닫히지 않은 인용·다중 인용·긴 비정상 입력의 bounded 성능 회귀를 포함하고 단순 무제한 regex 변경으로 끝내지 않는다.
3. **수치/API/기록:** 기존 정수 0–100 필드, 빈 metric vector, record=false, raw 본문 hash·purpose별 중복 방지와 기존 이력을 유지한다. 계산 수정으로 새 결과가 바뀔 수 있으나 과거 기록 재계산·migration·버전별 이력 재설계는 하지 않는다. 같은 본문 재분석 값과 옛 저장 점수가 다를 수 있음을 안내한다.
4. **화면:** 제목·접근성 이름을 **문체 신호 참고 점수**로 바꾸고 종합 문학 품질 점수가 아님을 명시한다. `para_count===0`이면 **빈 원고 — 점수를 품질 판단에 사용할 수 없습니다**를 표시하되 숫자 API와 기록은 유지한다. 임의 최소 분량·null/422·기록 억제 정책은 추가하지 않는다.
5. **의미 안내:** 글자 수는 단순 공백 제외가 아니라 Unicode 문자/숫자(L/N) 기준임을 설명한다. v2는 **외부 essay 참고치(내장 점수와 별개)**로 표시한다. 이력은 목적·규칙에 의존하는 참고 기록으로 안내하며 목적 전환에 따른 점수차를 문장 개선 증거로 주장하지 않는다.
6. **외부 연동:** 현행 essay/fallback을 공개한 채 유지하고 실제 엔진의 지원 장르·버전 확인은 V04에서 별도로 한다. 확인 없이 novel/fiction으로 교체하지 않는다.

빈 원고 점수를 숨기거나 null로 바꾸기, 최소 글자 수 도입, 이력 버전/schema 변경, 외부 장르 변경을 원하면 위 최소안과 다른 계약 승인이 필요하다.

## 구현·검증 순서

- 승인 후 `backend/app/services/quality.py`의 계수·인용 처리와 해당 테스트, `QualityDialog.tsx`의 승인 문구/경고 및 필요한 국소 UI 테스트를 최소 변경한다. router/schema/model/완결 목적 의미는 유지한다.
- 두 RED를 GREEN으로 만든다. 현재 관찰용 테스트에서 결함 결과를 고정한 assertion은 새 계약 기준으로 갱신하되 원래 RED/보고서는 보존한다.
- 어미 중복/negative, 199/200/201/400 이상 인용과 비정상 장문, 분모/rounding, 목적·record=false·기존 이력 호환 회귀를 확인한다.
- 공식 격리 backend 전체 회귀, 필요한 source 범위 계측, frontend fixture-only UI·TS/build·접근성, fresh 독립 검토 후 부모 수용한다. 새 계측 예외가 필요하면 실행 전에 근거와 범위를 확인한다.
- 실제 provider·외부 metrics 원본 실행·운영 DB/credential·migration·배포·stage/commit/push는 계속 제외한다.

## 실행 전 검증 경계 확정

- backend의 공식 runner와 import 전 격리는 유지한다. `backend/tests/isolation_guard.py`의 고정 coverage source 목록에 **`app.services.quality` 한 항목 추가**와 그 목록을 확인하는 회귀만 한정 허용한다. 기존 canon/bootstrap/projects/guard 계측은 유지하며 임의 `--cov`·CLI/config 우회·초기화 순서 변경은 금지한다. 새 stdlib preflight 후 실행한다.
- frontend는 `QualityDialog.tsx`의 변경행·branch를 실제 원본 TSX에 매핑한다. 검증된 fixture-only no-proxy/tripwire helper와 기존 Playwright/V8 수집·동일 hash raw merge·source-map/Istanbul 변환 방식을 재사용한다. 필요하면 독립 quality fixture config/test/작은 수집 helper를 추가할 수 있으며 전용 포트 **15229**, server reuse 금지다. 기존 8000/proxy·운영 설정·저장 큐는 건드리지 않는다.
- 이미 소유 검증 디렉터리에 있는 pinned `v8-to-istanbul@9.3.0`, `@bcoe/v8-coverage@1.0.2`, `istanbul-lib-coverage@3.2.2`와 Node types를 provenance/version 확인 후 재사용한다. 프로젝트 의존성·package/lock·전역 설치는 변경하지 않는다(기존 Vite 실행의 파생 cache와 구분). 새 패키지나 실행 환경 변경이 필요하면 먼저 보고한다.
- 구현 전 quality service/dialog의 원본 snapshot·SHA를 보존하고 실제 변경 실행행 및 모든 변경행의 계측 branch(예외 포함)를 분모로 고정한다. 각각 80% 이상, 0분모는 N/A로 표시하며 전체 모듈 값도 별도 보고한다. Python 다중행 literal의 별도 문장 매핑이 필요하면 AST·계측 원문 근거를 보고하고 임의 상위 함수 실행으로 덮지 않는다.
- 이전 계측 도구와 JSON 크기/직렬화 교훈을 재사용한다. raw 원본은 불변, 읽기용 pretty/projection과 본문 추출은 별도 저장한다. 같은 소스의 복수 runtime script entry를 숨기지 않고 source/JS/map hash와 scriptId/index를 연결한다. 명령별 fail-fast와 persistent evidence를 유지한다.

## 검증 중 한정 결정과 최종 상태

- full axe에서 공용 `role=dialog` 이름 누락을 재현해, `ui/dialog.tsx`의 선택적 `aria-label` 전달과 QualityDialog의 승인 이름만 한정 허용했다. 다른 호출부·focus·portal·키보드 정책은 유지하고 primitive도 변경범위 coverage에 포함했다.
- 동일 cwd의 Vite fixture는 전용 포트만으로 optimizer cache가 분리되지 않으므로 **순차 실행**한다. 504 초기 실패·서식 후 source mismatch·serializer 실패·ENOMEM은 원문과 supervisor 결정을 보존한 후 같은 프로토콜에서 검증했다. gate 면제나 의존성/전역 설정 변경은 없다.
- native 전체 **482P/기존 skip1/70subtests**, 서로 다른 frontend **77P**, full axe3회 violations/incomplete 모두 0, app/helper TS·build 통과. 변경 실행행/branch는 quality **19/20·10/10**, QualityDialog **278/284·42/48**, Dialog **41/41·14/14**다.
- 처음 fresh 독립 검토의 유일한 E1은 formatter가 바꾼 test/helper의 현재 실행 증거였다. exact-current 5P/helperTS0와 16개 hash 불변을 확인한 후 retained 검토 2건 **PASS, 새 지적 0**으로 종결했다. 원래 helper hash manifest와 초기 BLOCKED는 고쳐 쓰지 않는다.
- `.coverage`/crypto/canon/bootstrap/index와 범위 밖 dirty 자료 보존, staging 공백. 전체 worktree whitespace 지적은 임의 정리하지 않았다. 문학적 타당성·실제 외부 엔진·운영/지정 실기기는 여전히 범위 밖이며 active LSP all-clean도 주장하지 않는다. 다음은 **D01/D03/D04 상세 계약·기획**이다.
