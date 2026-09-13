# 병렬 장면 집필 엔진 명세

## 1. 목표

한 회차의 장면들을 Medium 모델 worker 2~4개로 동시에 집필하고, 결과를 장면 순서대로 조립한 뒤 xhigh 모델이 조립된 전체 원고를 감수한다. 감수 결과는 리포트로만 반환하며 원고와 SQLite 본문을 자동 변경하지 않는다.

기존 단일 `/api/v1/ai/generate` 흐름과 SSE 계약은 유지한다. 병렬 집필은 별도 모드·엔드포인트로 추가해 기존 생성 사용자를 깨뜨리지 않는다.

## 2. 범위

### 포함

- Medium planner의 구조화된 장면 계약 생성
- 장면 계약별 Medium worker fan-out
- 최대 4개 동시 worker 실행과 실패 취소
- worker 완료 순서와 무관한 장면 번호 기준 조립
- 조립 원고에 대한 xhigh 감수
- 진행 상황과 감수 결과의 SSE 이벤트
- 기존 컨텍스트(회차, 캐릭터, 로어, 목차, 복선, 문체 프로파일, 회차 브리프) 재사용
- 수동 반영 원칙 유지

### 제외

- 단일 LLM 응답의 토큰 단위 병렬화
- 장면 결과의 자동 본문 저장·자동 교체
- 여러 회차 사이의 무제한 동시 집필
- 별도 외부 큐·Redis·Celery 도입
- xhigh가 자동 수정본을 작성하는 동작
- 기존 `/api/v1/ai/generate`의 의미 변경

## 3. 용어와 모델

- **Planner**: 회차 전체를 2~4개 장면 계약으로 분해하는 Medium 호출
- **Worker**: 한 장면 계약을 받아 장면 원고를 작성하는 Medium 호출
- **Assembler**: worker 결과를 순서대로 합치는 결정적 구현. LLM 호출이 아니다.
- **Reviewer**: 조립된 원고 전체를 읽고 xhigh 감수 리포트를 반환하는 호출
- **정본 컨텍스트**: 생성 요청에서 선택된 컨텍스트와 planner가 받은 원문. 모든 worker와 reviewer가 공유한다.

단일 회차 내부의 모든 worker는 같은 generation endpoint와 `reasoning_effort=medium`을 사용한다. reviewer는 별도 endpoint를 선택할 수 있고 `reasoning_effort=xhigh`를 사용한다.

## 4. 처리 흐름

1. 요청을 검증하고 기존 `_build_messages`로 정본 컨텍스트를 만든다.
2. Planner가 다음 JSON 계약을 반환한다.
   - `scenes`: 2~4개
   - 각 항목: `order`, `title`, `purpose`, `required_beats`, `characters`, `opening_state`, `closing_hook`
3. planner 결과를 Pydantic으로 검증한다. 순서는 1부터 연속이어야 하며 중복 order를 허용하지 않는다.
4. `asyncio` 기반 bounded fan-out으로 worker를 실행한다. 동시 worker 수는 4를 넘지 않는다.
5. 각 worker는 정본 컨텍스트와 자기 장면 계약, 앞·뒤 장면의 상태 경계를 받는다. 다른 장면의 원고를 추측해 생성하지 않는다.
6. 모든 worker가 성공하면 order 오름차순으로 조립한다. worker 완료 순서는 사용하지 않는다.
7. 조립된 원고가 완성된 뒤 reviewer를 호출한다. reviewer는 `[감수]` 형식의 의견만 반환한다.
8. SSE로 planner/worker 진행 상태, 조립 원고, reviewer 감수, 완료를 전송한다.
9. 사용자가 수동 반영을 선택하기 전까지 본문 DB를 변경하지 않는다.

worker 하나라도 실패하면 나머지 worker를 취소하고 `parallel_error`를 전송한다. 불완전한 조립 원고나 감수 결과를 성공 결과로 표시하지 않는다.

## 5. SSE 계약

새 엔드포인트는 기존 이벤트와 충돌하지 않는 다음 이벤트를 사용한다.

- `parallel_start`: `run_id`, `scene_count`, `worker_limit`, generation/reviewer 모델 정보
- `planner_done`: 검증된 장면 수와 제목 목록
- `worker_start`: `order`, `title`
- `worker_done`: `order`, `chars`
- `message`: 조립 원고 delta. 장면 순서대로만 전송
- `review_start`: reviewer 모델·endpoint·reasoning effort
- `review`: xhigh 감수 delta
- `parallel_error`: 단계, 실패 order, 사용자용 오류
- `done`: `[DONE]`

기존 `message` 소비자는 조립 원고를 계속 받을 수 있어야 한다. 새 진행 이벤트를 모르는 기존 클라이언트도 최종 `message`와 `done`을 처리할 수 있게 한다.

## 6. 입력 인터페이스

기존 생성 요청과 분리된 병렬 요청을 추가한다.

- generation `endpoint_id`: Medium 모델 endpoint
- generation `model`: 선택적 override
- generation `reasoning_effort`: 기본 `medium`
- 기존 `prompt_override`, `context`, `params`
- `worker_limit`: 2~4, 기본 3
- reviewer `endpoint_id` 또는 generation endpoint 재사용
- reviewer `model` override
- reviewer `reasoning_effort`: 기본·권장 `xhigh`

프론트는 병렬 모드, worker 수, reviewer endpoint/추론 강도를 노출한다. 기존 단일 생성 UI의 기본 동작은 변하지 않는다.

## 7. 정합성·크기 규칙

- worker마다 동일한 정본 컨텍스트와 캐논 앵커를 전달한다.
- 장면 계약의 필수 필드는 비어 있지 않아야 한다.
- planner 출력과 worker 출력에는 개별 글자 수 상한을 둔다.
- 정본 컨텍스트와 전체 planner 계약은 요청별 최대 프롬프트 예산을 넘지 않도록 제한한다.
- worker 결과는 `order`로 정렬하고, 완료 callback 순서로 합치지 않는다.
- reviewer는 조립 결과와 정본 컨텍스트를 모두 받되, 새 사실을 만들지 않도록 지시한다.

## 8. 오류와 취소

- planner JSON 오류: 기존 JSON repair 정책을 적용하고 실패하면 `parallel_error`
- worker 오류: 다른 worker 취소, 부분 결과 폐기
- reviewer 오류: 조립 원고는 `message`로 완료할 수 있지만 `review_error`를 전송하고 감수 미완료 상태로 표시
- 클라이언트 취소: 실행 중 task를 취소하고 DB 자동 반영 없음
- endpoint rate limit/timeout: worker order와 오류 종류를 이벤트에 포함

## 9. 검증 기준

- planner가 2~4개 장면 계약을 반환하고 잘못된 order를 거부한다.
- 실제 비동기 fake worker가 서로 겹쳐 실행되는 것을 검증한다.
- 완료 순서를 역순으로 만들어도 최종 원고가 order 순서인지 검증한다.
- worker 실패 시 부분 원고·DB 저장이 없는지 검증한다.
- reviewer 호출이 모든 worker와 조립 완료 뒤에만 발생하는지 검증한다.
- xhigh 감수 이벤트는 `review`만 반환하고 자동 수정본을 반환하지 않는지 검증한다.
- 기존 단일 생성 SSE·기존 전체 백엔드 테스트·프론트 빌드가 유지되는지 검증한다.
