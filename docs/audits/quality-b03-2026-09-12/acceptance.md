# B03 품질 지표 최소 보정 — 최종 수용

**판정: 수용 완료.** 승인 2026-09-12, 최종 수용 2026-09-13(KST). 재현 → 최소 수정 → 격리 회귀·변경범위 계측 → fresh 독립 검토 → 잔여 증거 이슈 재검토를 마쳤다. 다음 승인 묶음은 **D01/D03/D04의 상세 계약·기획**이며 구현 승인을 선취하지 않는다.

- [승인 계약](../../superpowers/plans/2026-09-12-quality-metric-corrections.md)
- [선별 증거 107개·원본 경로·SHA manifest](accepted-evidence/manifest.json)
- [검증 보고서 원문](accepted-evidence/reviews/validation.md.txt), [최종 보조 파일 재검증](accepted-evidence/parent/retry-1/manifest.json.txt)
- main HEAD `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`. stage/commit/push 및 운영 변경 없음.

## 수용한 동작

1. 설명용 `~`가 없는 약한 어미를 탐지한다. 긴 표현 우선·비중첩으로 세어 포함된 일반 어미를 중복 계수하지 않는다.
2. 200자를 넘는 닫힌 인용문의 내부 전체를 센다. 선형 스캐너로 긴 미완성 입력의 반복 재탐색을 피한다. 기존 따옴표 혼합·빈 구간·ASCII 단일 인용 제외·분모·반올림은 유지한다.
3. **문체 신호 참고 점수**, 빈 원고 경고, Unicode L/N 글자 수, 별도 essay 참고치, 목적/규칙에 의존하는 과거 이력 안내를 표시한다. 문학적 품질 점수로 주장하지 않는다.
4. full axe에서 드러난 대화상자 이름 누락은 승인 계약의 접근성 이름을 완성하는 최소 예외로 고쳤다. 공용 `Dialog`에 선택적 `aria-label` 전달만 추가하고 QualityDialog만 이름을 지정한다. 기본값·타 호출부·포커스·Portal/Escape/backdrop 정책은 바꾸지 않는다.
5. 점수 가중치·범위·빈 원고 수치·purpose·API/schema·기존 저장 이력·외부 essay/fallback 계약은 유지한다. 회귀는 같은 본문의 새 분석 50점과 기존 저장 65점이 공존하며 `recorded=false`임을 확인한다.

제품 변경은 `backend/app/services/quality.py`, `frontend/src/components/editor/QualityDialog.tsx`, `frontend/src/components/ui/dialog.tsx`다. 나머지 8개는 테스트/fixture/고정 계측 목록이다. 원래 dirty 변경과 B03 변경은 [baseline-relative diff](accepted-evidence/validation/b03-baseline-relative.diff.txt)로 구분한다. 자동 서식 변경도 숨기지 않았다.

## 실행 결과

| 검증 | 결과 | 경계 |
| --- | --- | --- |
| 공식 native preflight·전체 backend | **482 passed / 1 skipped / 70 subtests / 19 warnings**, exit 0 | `violations=[]`, `subprocess_attempts=0`; fake keyring 호출 7회는 합성 회귀 |
| 현재 보조 파일 기준 품질 화면 | **5 passed**, exit 0 | 전용 15229, fixture-only/no escapes. 이름 생략 호환 2건 포함 |
| full axe | **3회 모두 violations=[] / incomplete=[]** | 이름 있는 품질 대화상자 전체 검사. 다른 미명명 호출부의 접근성 수용으로 확대하지 않음 |
| 공용 소비자 회귀 | **Memory 31 / preservation 26 / AI 15 passed** | 같은 cwd의 Vite 서버는 순차 실행, 모두 no escapes |
| TypeScript/build | app·contextual helper TS·Vite build **PASS** | helper는 기존 owned Node22 types/strict ES2020; 전역·프로젝트 의존성 설치 없음 |

품질 5 + 관련 화면 72 = **77개 서로 다른 화면 테스트**다. 반복 실행을 합산하지 않는다. backend 기존 외부 metrics 비교 1건은 계속 V04 미검증이다. 브라우저는 지정 Windows 실기기 수용이 아니다.

## 변경범위 coverage

| 제품 소스 | 변경 실행행 | 변경 branch arms | 전체 모듈 참고치(line / branch) |
| --- | --- | --- | --- |
| `quality.py` | **19/20 (95%)** | **10/10 (100%)** | 128/135 (94.81%) / 41/48 (85.42%) |
| `QualityDialog.tsx` | **278/284 (97.89%)** | **42/48 (87.5%)** | 442/450 (98.22%) / 42/48 (87.5%) |
| `dialog.tsx` | **41/41 (100%)** | **14/14 (100%)** | 101/101 / 17/17 |

- 각각 line/branch 80% 기준을 충족했다. 전체 저장소나 V01 완료 수치가 아니다. frontend 전체 모듈 수치는 V8→Istanbul 매핑 방식의 line counters다.
- Python L34 generator는 native 계측이 직접 기록하지 않아 **분모에 포함하고 미충족으로 남겼다**. 상위 함수/문장 실행으로 점수를 주지 않는다.
- Dialog의 14는 변경범위, 17은 전체 모듈 branch arms다. 누락된 frontend 6개 branch 및 catch, raw diff의 빈 줄 6개 분류를 [전체 branch 원장](accepted-evidence/validation/all-branch-arms.json.txt)에 보존했다.
- 원본 기준·계측 JSON·변환 코드·source map·generated JS·raw V8를 함께 보존했다. 독립 검토자가 **5 raw samples / 10 runtime entries / 2 exact-identity groups**를 다시 merge/변환해 저장된 전체 매핑과 일치함을 확인했다.

## 독립 검토와 마지막 증거 경계

| 검토 | 최초 fresh 검토 | retained E1 종결 |
| --- | --- | --- |
| 동작·계약 | 제품 지적 0, 보조 파일 증거 경계 BLOCKED | [PASS·새 지적 0](accepted-evidence/reviews/behavior-e1-closure.md.txt), `d877212a-6442-45b2-b407-76dd165100ad` |
| 보안·계측·보존 | 제품 보안 지적 0, 원본 coverage 재구성 완료, E1 BLOCKED | [PASS·새 지적 0](accepted-evidence/reviews/integrity-e1-closure.md.txt), `498706f7-4a43-42a4-aa43-029022f03b4b` |

최초 검토의 BLOCKED 원문은 유지한다. 검증 종료 뒤 자동 서식이 바뀐 **spec/collector 2개**는 기존 validation manifest와 다른 hash다. 최종 수용은 과거 hash를 고쳐 쓰지 않고, 부모의 **현재 파일 재실행 5P·helper TS 0 및 16개 전후 hash 동일** 증거로 E1을 닫았다. 제품 3개의 hash는 원래 검증·계측과 같다. 부모의 새 raw 5/10/2 묶음은 기존 coverage에 합치지 않았다.

공용 31/26/15 회귀 이후 QualityDialog의 4행 속성 줄바꿈은 parse-error 0·literal/JSX/operator 변경 거부 대조군이 있는 syntax-equivalence 증거로 구분한다. 현재 품질 테스트·TS/build·원본 map은 최종 제품 소스 hash에 직접 결속되어 있다. 모든 회귀가 byte-identical 소스로 실행됐다고 주장하지 않는다.

## 보존한 실패·복구

- 조사 RED2와 추가 RED → 승인된 계수 수정으로 GREEN. 원래 실패·관찰을 성공으로 다시 쓰지 않았다.
- Vite 동시 실행 중 AI `504 Outdated Optimize Dep`: 1 fail/14 not run 보존 → 같은 설정 순차 재실행 15P. 공유 cache 경합은 유력 설명이지 확정된 제품 결함이 아니다.
- full axe의 `aria-dialog-name` 3 FAIL → 선택적 이름 전달·전체 재검증으로 해결.
- 서식 후 raw-map/source mismatch → 변환기가 exit 1로 차단, 새 exact-current 수집·변환. SourceFile 전체 text를 비교한 보조 serializer 오류도 별도 보존·대조군 포함 수정.
- 부모 마지막 실행의 **ENOMEM**은 test discovery 전 실패했다. 당시 available 560MiB/swap 거의 소진 → 독립 검토 종료 후 1931MiB로 자연 회복 확인 → 승인된 순차 1회 재실행 성공. cache 청소·다른 프로세스 종료·설정/의존성 변경은 없었다.
- frozen v2의 기존 optional ModuleSpec/loader 진단과 Node helper의 잘못된 fallback-lib 진단은 분리했다. 후자는 올바른 contextual TS 통과이며 **active LSP all-clean이라는 뜻이 아니다**. 일반 자동 `python` ENOENT advisory를 공식 backend 실행 결과로 대체하지 않았다.

## 최종 보존·이관

부모와 무결성 검토자는 원래 **218개**, 최종 retry **25개** artifact의 hash/크기를 확인했다. 11개 작업 소스와 `.coverage`/crypto/canon/bootstrap/index를 합친 **16개** hash가 최종 소스와 일치한다. 기존 dirty/미추적 자료와 staging 공백을 보존했다.

선별 사본 107개는 자동 formatter로 원본이 바뀌지 않도록 `.txt`를 덧붙인 byte archive다. 전체 실행 디렉터리나 독립 실행 가능한 도구 묶음을 복사한 것은 아니며, manifest에 명시한 persistent 원본 경로를 함께 보존한다. [게시 후 확인](accepted-evidence/post-write-manifest.json)은 최종 문서와 사본의 실제 hash를 기록한다.

B03은 기술적 최소 계약으로 종결한다. 실제 문학 품질·외부 엔진 정확도·운영 DB/credential/provider·지정 실기기·migration/배포·Git 반영은 수용 범위 밖이다. **D01/D03/D04는 상세 저장/상태/job 계약을 먼저 확정**하고, V/G는 승인된 순서를 유지한다.
