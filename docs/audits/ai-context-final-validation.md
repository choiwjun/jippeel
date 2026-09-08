# AI 맥락 일관성 최종 검증

> 아래 브랜치·미push 상태는 `92c9cda`까지의 검증 당시 기록이다. 이후 main 통합·공유와 남은 작업은 [최신 인계](../handoffs/2026-09-08-remaining-work.md)를 따른다. 소스 검증 결과와 운영 미배포 범위는 유지한다.

## 현재 상태

- **승인 범위 구현·독립 검토·최종 검증 완료. 운영 미배포.**
- 브랜치: `feat/ai-context-consistency`
- 최종 소스 커밋: `cd7fc1f3360b6e42d49ab75398b94732ed057649`
- 기준: 원고 보존 완료 커밋 `70ec67eb3be02a89baefe01b3e798d033431983b`. 기존 보존 기능을 유지한다.
- 이 문서는 현재 완료 상태의 기준이다. 개별 Task 보고서의 READY/재검토 대기 문구는 당시 이력이다.
- merge, push, 운영 DB 마이그레이션, 운영 서버 재시작은 하지 않았다. 기존 서비스와 관련 없는 dirty/untracked 파일은 보존했다.

## 구현한 범위

| 영역 | 현재 계약 |
|---|---|
| 소속·저장 버전 | 명시적/소비되는 참조의 작품 소속을 제공자 호출 전에 검증한다. 활성 편집기 요청은 저장을 확정하고 revision을 전달한다. 본문 제외와 회차 식별은 별개다. |
| 생성 지시문 | 단일·감수·병렬 기획·각 장면·병렬 감수에 문체, 선택 인물 관계, 목적, 회수 허용을 일관되게 전달한다. 최종화는 `ending_intent`를 사용한다. |
| 모순 검사 | 선택 인물 수와 무관하게 작품 전체 관계를 opt-in할 수 있다. 검사 당시 저장 본문에서 revision/hash를 고정하고 화면·API·DB 이력에 보존한다. |
| 시간·권한 | 미래 설치와 미래 회수를 현재 사실에서 구분한다. 회수 허용은 회수 강제/완료 증명/상태 자동 변경이 아니다. |
| 품질 | 연재화에만 훅 항목을 적용한다. 실제 본문 hash와 목적을 이력 구분에 사용한다. 최종화 문학 품질 점수를 새로 검증한 것은 아니다. |
| 화면 수명 | 첫 await 전에 요청을 복사한다. 늦은 응답은 토큰·화면 수명·출처로 제한하며, 다른 회차/새 요청을 덮어쓰지 않도록 한다. |
| 독립 AI | 인물·세계관 요청은 명시적 현재 작품을 사용하고 이전 회차/body/revision/scene/저장 flush를 물려받지 않는다. 활성 편집기 미리보기는 여전히 회차에 바인딩된다. |

사용법과 재실행 절차: [runbook](../runbooks/ai-context-consistency.md).

## 최종 검증 결과

서로 다른 검증 층이므로 아래 수치를 하나의 총점으로 합산하지 않는다.

| 검증 | 결과 | 근거 |
|---|---|---|
| 부모 전체 native backend | **269 passed**, exit 0 | [출력](ai-context-final-parent-backend.txt) |
| 부모 native frontend build | **PASS**, exit 0 | [출력](ai-context-final-parent-build.txt) |
| 부모 실제 browser/API/Alembic/임시 SQLite/가짜 제공자 통합 | **3 passed**, exit 0 | [출력](ai-context-final-parent-integration.txt) |
| 부모 보정된 UI/SPA fixture | **15 passed**, exit 0 | [출력](ai-context-final-parent-fixture.txt) |
| 독립 Spec: 보정된 UI/SPA fixture | **15 passed** | [Spec 보고서](ai-context-final-spec-review.md) |
| 독립 Spec: 같은 앱 hash의 실제 통합 / 원고 보존 fixture | **3 passed / 17 passed** | [Spec 보고서](ai-context-final-spec-review.md) |
| 최종 Spec / Standards | **PASS / PASS**, 남은 차단 지적 없음 | [Spec](ai-context-final-spec-review.md), [Standards](ai-context-final-standards-review.md) |

실제 부모 실행 명령(각 지정 폴더에서 native Windows 실행):

```text
backend: .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests -q
frontend: npm run build
frontend: npx playwright test --config playwright.ai-context.config.ts --output ../.eval_tmp/ai-context-final-parent/playwright-results
frontend: npx playwright test --config playwright.ai-context.fixture.config.ts --output ../.eval_tmp/ai-context-final-parent/fixture-results
```

이 작업에서 보존한 임시 unit runner는 pytest import 전에 새 TEMP DB와 단위 테스트 전용 우회를 설정했다. `.eval_tmp`는 배포 파일이 아니다. 임시 runner가 없는 checkout에서도 실행할 수 있는 환경 설정 예는 runbook에 있다. 실제 통합 fixture는 우회를 제거하고 Alembic head를 적용한다.

## 실제 경계에서 확인한 근거

부모 최종 통합 run `20260908-192523-425543`:

- 제공자 HTTP 요청 8건: draft 2, single review 1, planner 1, worker 2, parallel review 1, canon 1. 원시 JSONL의 `payload.messages`를 보존했다.
- 단일 생성·감수에서 본문은 제외되고 목적·문체·관계·회수 허용은 전달됐다. 두 병렬 장면 응답은 서로 구분되며 감수 입력에서 순서가 유지됐다.
- 잘못된 소속/참조/저장 버전 요청 8건에서 제공자 호출 수가 각각 7 → 7로 유지됐다. 이후 정상 legacy 요청은 별도 8번째 호출이다.
- 관찰한 창작 데이터의 전후 snapshot이 같았다. 허용된 usage/canon/quality 이력은 생성됐다.
- 저장 본문 SHA256 `b7d5fa523f776666ef9759325be9eba3821e3c2fb90c46424156a545b57a2d07`가 정확한 화면 표시·API 이력·DB 이력과 일치했다.
- 소유 provider PID 20016 / backend PID 19828이 종료됐다. 부모 최종 확인에서 전용 포트 15212/18112/18113/15225/15227의 listener는 0이었다. 기존 8000/5173 서비스를 종료한 근거로 해석하면 안 된다.

[경계 요약/소스 hash](ai-context-final-parent-boundary-summary.json), [포트 확인](ai-context-final-parent-ports.txt).

원시 재현 자료: `.eval_tmp/ai-context-final-parent/`의 `provider-prompts.jsonl`, `backend-fixture.json`, `playwright-evidence.json`, `integration.db*`, `cleanup.txt`. 다른 실행의 기본 포인터 덮어쓰기를 피하도록 따로 복사했다. TEMP와 `.eval_tmp` 자료는 현재 작업 공간의 보존 근거이며 Git checkout만으로 모두 제공되는 것은 아니다. 커밋된 테스트·설정·실행 절차로 재현할 수 있다.

## 해결된 지적과 남은 검증 한계

- S2: 생성의 인물 선택 수 조건이 canon에 새어 들어갔다. 내부 대상 정책을 분리하고 인물 0/1명 상태를 검증했다.
- S3: 남은 editorStore ID가 독립 요청에 섞일 수 있었다. 명시적 요청 출처와 활성 편집기 식별을 도입했다.
- 초기 standalone 테스트의 `page.goto`는 runtime을 초기화해 stale-state 증거로 부적절했다. 보정된 테스트는 동일 runtime, 실제로 남은 이전 editor ID, 보존된 미해결 draft를 먼저 확인한다. 이전 reload 기반 15PASS와 중단된 fixture 실행은 이 증거로 사용하지 않는다.
- 마지막 소스 커밋은 독립 검토의 [고정 snapshot](ai-context-final-rereview-2-snapshot.json)과 동일한 8개 파일을 포함한다. 검토 당시 `d2a5b34` 위의 미커밋 후보였으며, 부모가 일치 여부를 확인한 뒤 커밋했다.
- 결정론적 가짜 AI 계약 검증이다. 실제 모델 품질·문학적 완성도·장편 기억·운영 배포는 검증하지 않았다.
- 기존 Vite 중복 `build` 키 경고, anyio deprecation 경고, 과거 Markdown hard-break 공백과 비차단 호환 helper 정리는 범위 밖으로 남겼다.

다음 수정의 필수 검증 규칙: [lessons](ai-context-lessons.md).
