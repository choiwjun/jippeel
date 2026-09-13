# 병렬 집필 평가·검증 Runbook

## 오프라인 20케이스 검증

모델 호출 없이 케이스 파일 구조와 evaluator 프로토콜을 확인한다.

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_parallel.py --case-file evals\parallel_cases.json --offline
```

이 결과는 문장 품질을 증명하지 않는다. `protocol_pass`는 corpus schema가 유효한지만 뜻한다.

## 실모델 제한 실행

실행 전 endpoint·토큰·비용을 확인한다. 기본은 1~2개 케이스로 시작한다.

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_parallel.py `
  --case-file evals\parallel_cases.json `
  --endpoint-id 1 --limit 2 --live `
  --output ..\.eval_tmp\parallel-live.json
```

확인 항목:

- `parallel_start → planner_done → worker_start/worker_done → message → review_start → review → done`
- worker 시작·완료 수 일치
- `draft_chars`와 `review_chars`가 0보다 큰지
- required cue 누락과 forbidden cue 발생
- Reviewer가 지적한 구조·동기·캐논 문제

SSE heartbeat comment는 실제 이벤트가 아니므로 평가 집계에서 제외한다. 모델 자기 감수는 독립적인 품질 판정이 아니므로, 최종 품질 판단은 고정 rubric과 사람 검토를 함께 사용한다.

## 브라우저 검증

```powershell
cd frontend
npx playwright test e2e\parallel-writing.spec.ts
```

이 테스트는 실제 LLM을 호출하지 않고 SSE를 route-intercept한다. 병렬 모드 설정, 요청 payload, 진행 이벤트, 감수 탭, 자동 본문 반영 금지를 검증한다.

## 검증 기록

2026-09-07 실행 결과:

- offline corpus: 20/20 schema cases pass
- live smoke: 2/2 protocol pass, draft/review nonempty 2/2, required cue hits 4, forbidden cue hits 0
- Playwright 전체 E2E: 10 passed (a11y 1, 기존 app-flow 8, 병렬 집필 1)
- backend pytest: 201 passed, 1 deprecation warning
- frontend Windows build: success; existing Vite duplicate `build` warning remains
