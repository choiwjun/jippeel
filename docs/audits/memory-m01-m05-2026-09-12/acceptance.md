# M01~M05 기억 화면 보정 — 최종 수용

- 날짜: 2026-09-12
- 판정: **M01~M05 구현·회귀·독립 검토·부모 수용 완료**. 운영/배포/전체 프론트 coverage 수용이 아니다.
- 저장소: `main @ c1a92c45fe8c16b4ee140a31fe97683ab588ed07`. stage/commit/push 없음.
- 승인: [순차 실행 계약](../../superpowers/plans/2026-09-12-remaining-sequence.md), [국소 coverage 결정](../../superpowers/plans/2026-09-12-memory-scoped-coverage.md).

## 수용 범위

| 항목 | 확인한 동작 |
| --- | --- |
| M01 | 작품·화면 인스턴스별 폼/필터/확인/pending 분리. A→B→A의 늦은 POST/PATCH 성공·실패도 현재 입력·toast·focus를 건드리지 않으며 원래 작품만 invalidate |
| M02 | 원고 저장/복원 revision 성공 후 원래 작품 기억 갱신. editor unmount 후 save acknowledgement도 유지하며 cache 통지 예외가 실제 저장 성공을 실패로 바꾸지 않음 |
| M03 | 작품/회차/기억 조회 오류를 loading/빈 목록과 구분, 입력 보존 및 키보드 재시도 |
| M04 | 승인·폐기 취소/완료 뒤 호출 버튼 또는 목록 fallback으로 초점 복귀, 다른 화면 초점 탈취 없음 |
| M05 | retired 기억도 근거 이력 때문에 회차 삭제를 막는 정확한 409 안내. 잠금·조회·삭제 의미와 데이터 보존 불변 |

제품 변경은 `MemoryPage.tsx`, `App.tsx`, `queryClient.ts`, `manuscriptDrafts.ts`, `projects.py`의 승인된 변경이다. fixture-only no-proxy/tripwire 및 shared synthetic HTTP handler, 계측 helper는 승인된 검증 보강이다. API/schema/migration/provider/crypto와 원고 큐/CAS는 재설계하지 않았다. 중단 후 이번 재개에서는 제품·테스트 소스를 추가 수정하지 않았다.

## 새 실행 결과

| 검증 | 실제 결과 |
| --- | --- |
| 공식 native backend preflight / 전체 suite | 앱 import 전 격리 확인; **421 passed / 기존 skip 1 / 70 subtests / 19 warnings**; `violations=[]`, `subprocess_attempts=0` |
| Memory / 원고 보존 / AI fixture 전체 | **31 + 26 + 15 = 72 passed**, 모두 positive no escapes |
| 국소 Memory / 원고 보존 | 25 / 9 passed; 전체 72와 합산하지 않음 |
| TypeScript / fixture helper TypeScript / Vite build | 각 exit 0; 프로젝트 의존성·lock 변경 없음 |
| 접근성 | 초기 memory flow와 키보드 8사례의 axe serious/critical 0 assertion 통과. 전체 접근성 인증은 아님 |
| 격리 negative | 별도 disposable 상태의 unknown API가 latch를 남기고 예상 suite exit 1. positive/coverage 증거에 혼합하지 않음 |

실행 명령·cwd·exit는 [command index](accepted-evidence/command-exit-summary.json), 실제 로그·보존·보고서는 [최종 사본 manifest](accepted-evidence/post-write-manifest.json)를 따른다.

## 변경범위 계측

| production 소스 | 변경 실행행 | 변경 branch |
| --- | --- | --- |
| MemoryPage | 60/60 | 33/33 |
| manuscriptDrafts | 2/2 | N/A |
| queryClient | 11/11 | 5/5 |
| App | N/A | N/A |
| projects | 변경 literal 1개 → 실행 문장 1개 | N/A |

- 원래 M 시작점의 5파일 기준을 durable 세션으로 복구했다. 원래 전체 snapshot이 살아 있다고 주장하지 않는다. 현재/HEAD를 새 baseline으로 삼아 분모를 줄이지 않았다.
- 72 tests → 56 raw samples / 228 runtime entries / 8 source·JS·map hash groups. AI 15개는 선택 계측 fixture 미사용, lifecycle 1개는 명시적 page close로 표본이 없음을 기록했다. 동일 소스의 scriptId 50/295를 서로 다른 transform으로 오인하거나 버리지 않았다.
- 변경된 모든 source 행의 branch/catch를 포함한다. helper fault 표본을 뺀 반사실 비교는 3/4, 포함하면 catch와 추가 mapped normal-await range 때문에 5/5다. 이전 잘못된 3/3은 수용 수치가 아니다.
- Python literal L299는 coverage.py raw 계측행이 아니다. 정확한 source hash와 직접 `Raise→Call→keyword(detail)→Constant` AST 및 응답 회귀로 실행 문장 L297에만 연결했다. 분모 1 유지, raw JSON 불변, 8개 합성 검증 통과.
- 이는 **M 변경범위**의 80% gate 충족이다. drafts 전체 모듈 branch는 75%이며 전체 프론트 V01은 남아 있다.

## 독립 검토·부모 판정

workflow `f7db362c-4031-4698-ab0f-93665a93cf14`의 fresh read-only 두 검토 모두 PASS / 차단 지적 0이다.

- 상태·접근성: `f8697d88-366b-42a1-8115-83bdeb22ea16`, [원본 structured 판정](accepted-evidence/behavior-review.raw.json).
- 격리·계측·보존: `5eb1e1eb-b307-4bd3-a05c-5ab6af9a9eca`, [원본 structured 판정](accepted-evidence/integrity-review.raw.json).
- 부모가 두 판정을 끝까지 읽고 실제 로그·계측·partial diff를 대조했다. 356개 artifact, 29개 source, 5개 protected hash를 직접 검증했고 검토 종료 후 source/protected 불변을 다시 확인했다. 이후 상태 문서만 갱신한다.
- 일부 큰 raw JSON은 원본 hash와 필드 동등성이 확인된 별도 부모 projection으로 검토했다. reviewer가 테스트/전체 hash를 독립 재실행했다고 주장하지 않는다.
- runtime markdown output binding은 비어 있었으나 실제 structured 결과는 정상 반환됐다. 원본 JSON을 byte-identical하게 보존했다. 사본 Markdown 자동 서식 적용 두 건은 읽기용 파생본으로 구분하고 원문 `.md.txt`도 별도 보존했다.

## 복구 이력과 한계

- `/tmp`의 이전 검증 자료 소실 후 새 검증을 수집했다. 복구 worker의 30분 timeout은 변환 exit 0 뒤 발생했고, 보존된 세션에서 근거 정리만 이어갔다.
- 부모 workflow의 optional `outputPathMapping=undefined` 직렬화 오류는 writer 정상 종료 뒤, reviewer 시작 전에 발생했다. JSON-safe 정규화 합성 3건 후 리뷰만 재실행했다. 앱 실패로 해석하지 않는다.
- Python 계측행 가정, raw sample을 항상 4 entry로 가정한 포장 오류 및 그 뒤 보정은 별도 실패 기록으로 보존했다. 오류 뒤 복합 shell이 진행한 focused run은 최종 정상 실행과 분리했다.
- active LSP 5파일: diagnostics 0 / **clean 1, inconclusive 4**(timeout 3, silent push-only 1). 전체 clean 근거가 아니다.
- backend 기존 외부 metrics 비교 skip 1(V04), ResourceWarnings, restore-after-unmount 전용 held-restore 회귀 부재(지속 coordinator 소스 검토와 save-unmount/restore 사례로 확인)를 비차단 한계로 남긴다.
- 실제 provider·운영 DB·credential·지정 Windows 실기기·migration/배포·Git 반영은 수행하지 않았다.

전체 원시 자료는 `/home/hunter8891/.pi/agent/sessions/--mnt-c-Users-wj941-Documents-jippeel--/recovery/memory-m01-m05-restart-szd8peci/verification-0fe42cf5`에 유지한다. 프로젝트에는 최종 판정·주요 로그·계측·보존 등 27개 사본/파생본을 보존했다. 전체 raw archive가 원격 checkout에 자동 전달되는 것은 아니다. 다음 순서는 원장의 **B03**이다.
