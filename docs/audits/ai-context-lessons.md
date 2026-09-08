# AI 맥락 작업의 재사용 가능한 검증 규칙

이 문서는 구현 목록이 아니라 다음 수정에서 반복 실패를 막는 기준이다. 현재 완료 상태는 [최종 검증 보고서](ai-context-final-validation.md)를 따른다.

## 1. 식별자와 포함 옵션을 분리한다

본문 제외는 회차 식별 제거가 아니다. 반대로 편집기를 떠난 뒤 남은 store ID는 현재 요청의 권한 있는 출처가 아니다.

**Gate:** 활성 편집기·미리보기·독립 요청을 구분하고, 실제 요청의 작품/회차/revision/body를 확인한다. 독립 요청은 오래된 원고를 flush하지 않아야 한다. 맥락 전환 중 불일치는 원고를 지우거나 무검증 fallback으로 숨기지 않는다.

근거: [최종 Spec S3](ai-context-final-spec-review.md), [fix-2](ai-context-final-frontend-fix-2.md).

## 2. 공통 UI가 서로 다른 대상 정책을 지우면 안 된다

공통 관계 옵션이어도 생성은 선택된 양쪽 인물, canon은 작품 전체 관계, 품질은 미사용이다. 같은 boolean을 공유한다고 활성화 조건까지 같지는 않다.

**Gate:** 공유 컴포넌트마다 소비자별 대상 정책을 명시하고 기본 상태(인물 0/1명)를 검사한다. 기본 상태를 건너뛰는 편의 setup을 금지한다.

근거: [최종 Standards S2](ai-context-final-standards-review.md), [fix-1](ai-context-final-frontend-fix-1.md).

## 3. 메타데이터보다 실제 소비된 입력을 검사한다

미래 복선을 메타데이터에 표시했어도 제공자 본문에서 현재 비밀로 쓰면 실패다. 원시 enum과 자연어 지시문은 다른 경계이므로 같은 문자열을 요구해서도 안 된다.

**Gate:** HTTP 요청은 enum/ID를, 실제 제공자 `payload.messages`는 적용된 의미·본문 제외·문체·관계·권한·시간축을 검사한다. 기획자, 각 장면 생성, 감수, canon을 따로 확인한다. 제공자 로그 분류기의 라벨만을 정답으로 쓰지 않는다.

근거: [Task2 review](ai-context-task-2-review.md), [Task4 review](ai-context-task-4-review.md).

## 4. 평가 장치가 버그를 지우지 않게 한다

테스트가 `setCurrentIdentity`로 정답을 주입하거나, `page.goto`로 앱을 새로 불러와 이전 store 상태를 지우면 정상처럼 보일 수 있다. 새 창에서 정상인 것과 SPA 전환이 안전한 것은 다르다.

**Gate:** 실제 앱 내 이동에서 동일 runtime이 유지되고, 이전 editor ID와 미해결 draft가 실제로 남아 있음을 먼저 확인한다. 그 상태에서 새 요청의 출처·무추가 flush를 검증한다. 초기 페이지 진입용 `goto`와 상태 유지 이동을 구분한다.

근거: [fix-2의 helper 보정](ai-context-final-frontend-fix-2.md), [최종 Spec 재검토](ai-context-final-spec-review.md). 이전 reload 기반 통과 결과는 stale-state 증거로 쓰지 않는다.

## 5. 비동기 소유권은 await 뒤에도 확인한다

요청 시작 시 ID 검사만으로는 늦게 끝난 응답이 다른 회차나 새 요청을 덮어쓰는 것을 막지 못한다.

**Gate:** 전체 입력을 첫 await 전에 복사한다. 응답 시 요청 토큰·화면 수명·출처를 다시 확인한다. 닫기/다시 열기, 다른 회차로 이동/복귀, 이전 오류가 새 요청보다 늦는 경로를 검사한다. 결과 표시와 삽입 권한, 이력 invalidation도 같은 출처를 따른다.

근거: [Task3 review](ai-context-task-3-review.md). [원고 보존 규칙](preservation-lessons.md)은 계속 적용한다.

## 6. 표시·이력 해시는 원본에서 독립 계산한다

`검사 기준` 라벨이 보이거나 해시가 64자리인 것만으로는 검사 원고가 맞는지 알 수 없다.

**Gate:** 검사 직전 실제 저장 본문에서 SHA256을 계산해 화면의 작품/회차/revision/hash, API 이력, DB 이력을 모두 대조한다. 반환된 해시 자체를 예상 정답으로 재사용하지 않는다.

근거: [Task4 재검토](ai-context-task-4-review.md).

## 7. 테스트 실행 환경도 계약이다

잘못된 cwd, 경로 escaping, 스키마에 없는 seed enum, 모달을 열어둔 이동, 동시 제공자 로그 분류·기록 오류는 앱 버그와 구분해야 한다.

**Gate:** 기존에 검증된 native 실행 구성을 먼저 재사용한다. 새 임시 DB 환경은 import 전에 설정한다. 실제 통합은 Alembic을 적용한다. 모든 seed payload를 실제 스키마와 대조한다. 병렬 로그를 안전하게 기록하고 장면별 입력·응답을 확인한다. 실패 출력을 보존하며 검증 조건을 낮춰 통과시키지 않는다.

근거: [Task4 검증](ai-context-consistency-validation.md), [Task4 rulings](ai-context-task-4-rulings.md).

## 8. 비동기 시작은 완료나 자동 재개가 아니다

작업 handle을 남기고 턴을 끝낸 뒤 실제로는 idle 상태였던 구간이 있었다. 실행 중이라는 오래된 상태 보고를 반복하면 사용자가 먼저 중단 여부를 물어야 한다.

**Gate:** 살아 있는 작업 상태와 이미 나온 결과를 확인하고, 같은 작업자에게 명시적으로 이어서 처리하게 한다. 종료한 작업·진행 중인 작업·대기 중인 검토를 구분한다. 중복 실행과 sleep polling으로 이를 대체하지 않는다.

근거: 이 작업 중 사용자의 “멈춘거야?” 질문 이후 live 상태를 확인하고 재개한 기록. 앞으로도 결과·장애물·다음 행동을 짧게 알린다.
