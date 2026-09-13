# 잔여 작업 순차 실행 — 사용자 승인 기록

- 승인일: 2026-09-12. 사용자가 아래 다섯 묶음을 인용하고 “이 작업들 순서대로 작업진행해”로 승인했다.
- 현재(2026-09-13): **M01~M05·B03 수용 완료, 다음은 D01/D03/D04 상세 요구·계약·기획**. [기억 수용](../../audits/memory-m01-m05-2026-09-12/acceptance.md), [B03 수용](../../audits/quality-b03-2026-09-12/acceptance.md). 완료한 P1·C13(B01/B02/B04)·M01~M05·B03은 재개하지 않는다.
- 현재 상태 원장: [전체 작업 현황](../../handoffs/2026-09-08-remaining-work.md).
- main worktree 단일 writer. 기존 dirty/미추적 자료 보존, stage/commit/push 없음.

## 승인된 순서

1. **M01~M05** 기억 화면 보정 → 회귀·독립 검토·부모 수용.
2. **B03 — 수용 완료:** [최소 보정안](2026-09-12-quality-metric-corrections.md)의 사용자 승인 후 계수2건·표시/접근성을 보정했다. backend482P/기존 skip1·frontend77P·국소coverage·독립 E1종결2PASS. 가중치/API/기존 이력 유지, 원래 RED·인프라 실패 보존.
3. **D01/D03/D04** 회차 목표 저장 → 기획/완결/재개 흐름 → 실제 summary worker 구현. D01 소스 조사를 마쳤고 [목표 이력 요구](2026-09-13-d01-contract-questions.md) 결정 후 상세 사양으로 간다. 기존 planner 재구현 없음. 실행은 fake provider로 검증하며 미결정 데이터·제품 계약은 먼저 명확히 한다.
4. **V01/V02/V04** 프론트 정량 coverage, 복원 실패 시험, 실제 외부 metrics 소스 비교. 기존 todo #18과 중복하지 않는다.
5. **G02/G01/G03/G04** 실제 AI → 운영 DB → credential 복구 → 지정 Windows 실기기 수용 준비 및 조건 충족 후 실행. 아직 비용 한도·대상 DB/백업/계정/장치/시간 창 등이 지정되지 않았으므로 지금 실제 자원에 접근하지 않는다. 해당 단계에서 필수 입력과 명시적 실행 허가를 확인한다.

각 묶음은 완료·검토 후 다음 묶음으로 진행한다. 코드 변경에 필요한 국소 검증은 즉시 하되, 전체 프론트 coverage 같은 후속 묶음의 완료로 확대하지 않는다. 오류·정책 거부·불명확한 제품 결정은 근거와 부분 diff를 남기고 부모에게 보고한다. 단순 검색 결과 없음/예상 경로 부재는 실패가 아닌 탐색 정보다.

## 1단계 확정 수용 계약 — 기존 M01~M05를 구체화

| 항목 | 수용 조건 |
| --- | --- |
| M01 | 같은 SPA A→B 전환에서 입력·필터·확인·pending 상태를 작품별로 분리. A의 늦은 성공/실패가 B 입력·확인·toast·cache를 변경하지 않는다. 요청 발생 당시 작품으로만 mutation·무효화한다. 새로 돌아온 A 폼도 이전 화면의 callback으로 초기화하지 않는다. |
| M02 | 원문 저장/복원 성공으로 revision이 바뀌면 해당 작품 기억 cache를 갱신해 stale 표시가 뒤처지지 않는다. 기존 저장 큐·revision/CAS·본문 보존/실패 처리 계약은 불변이다. |
| M03 | project/chapter/memory 조회 실패를 loading/정상 빈 목록과 구분하고 키보드 접근 가능한 재시도 경로를 제공한다. 실패 시 입력을 없애지 않는다. |
| M04 | 승인/폐기 확인을 취소하거나 성공 완료하면 호출 버튼 또는 사라진 버튼의 합리적 대체 위치에 초점을 돌린다. 다른 작품으로 초점을 탈취하지 않는다. |
| M05 | 연결 기억은 retired여도 provenance 때문에 회차 삭제를 막는다고 정확히 안내한다. 기존 409/잠금/조회/cascade 정책은 변경하지 않는다. |

### 변경 경계

- 주로 `frontend/src/pages/MemoryPage.tsx`와 기존 원고 저장/복원 성공 시 cache 갱신 지점, 회귀 테스트. 기존 UI 패턴 재사용, 디자인 재작업 없음.
- **M05의 실제 잘못된 안내는** `backend/app/routers/projects.py`의 chapter DELETE 409 detail에 있다. 이 문구만 최소 변경하고 관련 회귀를 보강할 수 있다. SQL/잠금/삭제 의미는 동결한다.
- 필요 시 작은 frontend helper를 추가한다. API/schema/migration/provider/crypto 및 기존 테스트 격리 runner는 동결한다. 의존성·검증 도구 추가가 필요하면 먼저 부모에게 근거를 제시한다.

### 기존 패턴·공식 근거

- React [key를 통한 상태 초기화](https://react.dev/learn/preserving-and-resetting-state): 작품 경계에서 폼 수명 분리 가능. 단순 remount가 외부 toast/cache side effect까지 막는 것은 아니므로 별도 확인한다.
- TanStack Query v5 [mutation callbacks](https://tanstack.com/query/v5/docs/framework/react/guides/mutations): mutate 호출별 추가 callback은 unmount 시 실행되지 않으며 hook-level callback과 의미가 다르다. 요청 변수에 원래 작품 식별자를 고정해 검증한다.
- [query invalidation](https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation): 작품 query-key prefix로 invalidate하면 staleTime과 무관하게 stale 처리하고 active query를 다시 가져온다. 기존 cache 구조를 재사용한다.
- 이는 구현 선택 참고이며 새 프레임워크/의존성 도입 승인이 아니다.

### 실행·검증

- planner는 승인된 다섯 계약의 기존 경로·회귀 매핑만 구체화한다. 새로운 기능/정책은 추가하지 않는다. 이어 단일 writer가 TDD RED→GREEN을 수행한다.
- fixture-only Playwright와 기존 memory/manuscript 회귀, axe serious/critical 0, TS/build, 필요한 국소 coverage를 검증한다. source-mapped 근거 없는 프론트 %는 주장하지 않는다. 전체 V01 완료와 구분한다.
- backend 실행은 **`backend/scripts/run_backend_pytest.py`**만 사용한다. [격리 가이드](../../runbooks/isolated-backend-tests.md)의 import 전 Windows 내부 TEMP/guard/fake-keyring을 유지한다. 과거 direct pytest/셸 환경변수만으로 격리를 주장하지 않는다.
- 기존 `.coverage` a8db…와 crypto/canon/bootstrap·Git index/HEAD를 불변 기준으로 잡는다. 새 로그·baseline-relative diff·hash 증거는 fresh owned TEMP에 둔다. 전체 무차별 hash 대신 제외 목록 있는 bounded source baseline을 사용한다.
- 구현 후 fresh 독립 검토 2축: 상태/접근성/회귀, 데이터·격리·보존. 부모가 직접 근거를 확인한 뒤 원장의 각 M 항목을 완료로 전환한다.

### Frontend fixture 격리 보강 승인

원고 fixture24개 assertion 통과 실행에서 백엔드 프록시 시도3건(연결 거부)이 확인돼 격리 PASS를 철회했다. [실패 근거·보정 승인](../../audits/memory-fixture-isolation-2026-09-12.md)에 따라 context mock과 fixture-only no-proxy/tripwire를 보강하고 같은 전용 포트로 재검증한다. 앱 저장/pagehide 동작은 바꾸지 않는다. 공유 설정이 바뀌는 memory/AI fixture도 재실행해야 한다.

### 변경범위 coverage 보강 결정

[국소 coverage 승인](2026-09-12-memory-scoped-coverage.md)에 따라 이번 변경 소스의 line/branch 근거를 확보한다. 앞의 runner 동결에는 고정 계측 목록에 `app.routers.projects`를 추가하는 한정 예외만 둔다. frontend 변환 도구는 owned TEMP 설치만 허용하며 프로젝트 의존성/전역 설치는 변경하지 않는다. 전체 V01은 여전히 후속 단계다.

### 조사 중 확인·재개 기록

- M02 조사에서 `manuscriptDrafts.ts`의 화면 구독이 unmount 시 해제돼, 진행 중 PUT이 뒤늦게 성공하면 `EditorPage.updateChapterCaches`만으로는 갱신을 놓칠 수 있음을 확인했다. held-save → SPA 기억 화면 이동 → 늦은 성공을 회귀에 포함한다. 요청 당시 작품으로만 성공 통지를 전달하고 기존 UI 구독 해제·큐/CAS 동작은 유지한다.
- 계획 child `dc237107-74df-461b-88ff-5130571e3690`가 부분 읽기 출력 차이를 동시 수정으로 추정했다. 부모는 writer 진입 전 workflow `7e9ea6c8-cf0d-4d65-8408-f82387ba7938`를 중단했다. `interrupt`는 async workflow에 미지원이어서 도구 안내대로 `stop`을 사용했고 stopped 상태를 확인했다. 구현 worker는 시작되지 않았다.
- 실제 검증: MemoryPage SHA-256 `2e09129dd5fd314cf68c362ac45cbda687ed7cce6c6ff64261686c659e84c143`은 기존 P1 수용 기록과 같고, child의 최초 전체 읽기와 현재 파일도 byte-identical이다. `offset=490, limit=12` 응답은 기존 372행부터의 문맥 확장 출력이었다. 동시 writer의 증거가 아니다.
- `/tmp/jippeel-memory-plan-recheck-2iiii34d/verification.json`, snapshot·기존 partial diff·status를 보존했다. trace 파서의 혼합 string/object 가정에서 나온 부모 진단 오류 2건도 타입 검사로 수정했다. 제품/테스트 실행·소스 수정은 없었다.
- 중단 child는 `children.list`에서 not resumable로 확인됐다. 동일 native 프로토콜의 fresh same-role 재시작으로 이어간다. 반환 행 수로 소스 변경을 추정하지 말고 실제 내용/snapshot으로 확인한다. 새로운 작업 승인이나 실행 경로 변경은 필요하지 않다.
