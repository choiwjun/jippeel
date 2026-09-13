# 병렬 집필 품질 강화 명세

## 목표

병렬 집필 결과가 장면 계약·인물 동기·캐논 정합성을 더 안정적으로 지키도록 하고, 고정 평가 세트와 실제 브라우저·실모델 검증으로 회귀를 감지한다.

## 보존할 제약

- 기존 `/api/v1/ai/generate`와 SSE 계약을 변경하지 않는다.
- 병렬 엔드포인트는 기존 `/api/v1/ai/generate-parallel`을 확장한다.
- SQLite를 작품 데이터 원본으로 유지한다.
- Planner·Worker·Reviewer 결과를 본문에 자동 반영하지 않는다.
- 외부 패키지·Redis·Celery·새 큐를 추가하지 않는다.
- 최종 원고에는 내부 장면 메타데이터를 출력하지 않는다.
- Reviewer는 감수 리포트만 반환한다.

## 품질 계약

### Planner/Worker

각 장면 계약은 다음을 포함한다.

- `objective`: 장면에서 주인공 또는 중심 인물이 이루려는 즉시 목표
- `choice`: 장면에서 발생하는 핵심 선택
- `cost`: 선택으로 발생하는 대가 또는 위험
- 기존 `purpose`, `required_beats`, `opening_state`, `closing_hook`

Worker는 objective·choice·cost를 본문 행동과 판단으로 보여주고, opening_state에서 시작해 closing_hook에 도달한다. 계약·프롬프트·메타 설명을 원고에 출력하지 않는다.

### 조립/검증

- 결과는 `order` 오름차순으로 조립한다.
- 빈 결과, 중복·누락 order, 과도한 결과 길이, 내부 계약 누출은 성공으로 표시하지 않는다.
- 사용자에게 보내는 draft는 자연스러운 본문만 포함한다.
- Reviewer 전용 원고에는 `[장면 N — 제목]` 경계를 넣어 장면별 검수를 가능하게 한다.

### Reviewer

Reviewer는 다음을 반드시 검사한다.

- 장면별 목적·필수 비트·hook 달성
- 장면 전환 인과성과 전체 구조
- 주인공 목표·선택·대가의 설득력
- 캐릭터·세계관·시간축·위치·복선 캐논 충돌
- 문장·리듬·플랫폼 적합성

## 평가

`backend/evals/parallel_cases.json`에 서로 다른 장르·갈등·캐논 조건을 가진 20개 고정 케이스를 둔다. runner는 기본적으로 fake/offline 계약 검증을 수행하며, `--live`를 명시한 경우에만 지정 endpoint로 실모델 호출한다. 결과는 `.eval_tmp/`에 저장하고 커밋하지 않는다.

## 브라우저 검증

Playwright E2E는 실제 AI 호출 대신 SSE fixture를 route-intercept하여 병렬 모드 선택, worker 수, reviewer 설정, 진행 문구, draft/review 탭을 검증한다. 실모델 smoke는 별도 명령으로 수행한다.
