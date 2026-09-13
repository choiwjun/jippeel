# AI 맥락 일관성 사용·검증 안내

## 적용 범위

회차 AI 생성·병렬 생성·모순 검사에 전달되는 작품, 회차, 저장 버전과 지시문을 일관되게 묶는다. 인물·세계관 화면의 독립 AI 요청은 이전에 열었던 원고와 분리한다.

현재 상태와 검증 수치는 [최종 검증 보고서](../audits/ai-context-final-validation.md)가 기준이다. 로컬 브랜치 변경이며 운영 배포 절차는 이 문서에 포함하지 않는다.

## 사용 방법

1. 회차 편집기에서 AI 패널을 연다. 회차 목적은 **연재화 / 권말 / 최종화** 중 선택한다. 기본값은 연재화다.
2. **현재 회차 본문 포함**을 끄면 본문은 제외하지만, 활성 편집기의 작품·회차 식별과 저장 버전은 유지한다. 미리보기 탭도 편집기 맥락에 속한다.
3. 생성의 **선택 인물 관계 포함**은 인물 2명 이상을 선택했을 때 사용할 수 있다. 선택된 양쪽 인물 사이의 관계만 포함한다.
4. 모순 검사의 **작품 인물 관계 포함**은 생성의 인물 선택 수와 무관하다. 켜면 해당 작품의 관계를 검사 맥락에 포함한다. 품질 진단에는 이 옵션을 표시하지 않는다.
5. **복선 회수 승인 선택**은 이번 요청에서 선택한 복선의 회수·공개를 허용한다. 회수를 강제하거나, 실제로 회수됐다고 확정하거나, DB 상태를 자동 변경하지 않는다.
6. 생성과 모순 검사는 활성 원고의 저장을 먼저 확인한다. 충돌·복구·저장 실패로 확정할 수 없으면 요청을 시작하지 않는다. 기존 [원고 보존 절차](manuscript-preservation.md)를 따른다.
7. 모순 검사 결과의 **검사 기준 — 작품 / 회차 / rev / hash**에서 실제 검사한 원고를 확인한다. 다른 회차로 이동하거나 요청을 취소한 뒤 늦게 도착한 결과가 새 요청을 덮어쓰면 안 된다.
8. 인물의 AI 초안·세계관의 AI 다듬기는 현재 페이지의 작품과 선택 항목을 사용한다. 이전 원고의 회차·본문·저장 요청을 물려받지 않는다. 결과는 자동 삽입되지 않으며, 복사 또는 사용자의 명시적 반영이 필요하다.

회차별 공통 목적·관계·복선 설정은 현재 클라이언트 세션의 상태다. 서버 저장 설정이나 브라우저 재시작 후 복원을 보장하지 않는다.

## 목적과 시간축

- 연재화는 다음 회차 연결을 고려한다. 권말과 최종화에 연재용 훅을 강제하지 않는다.
- 최종화 병렬 기획은 `ending_intent`로 마무리 의도를 전달한다.
- 미래에 설치할 복선은 현재 사실이 아니다. 현재 설치됐지만 미래 회수 예정인 복선은 현재 단서와 미래 계획을 구분한다. 이미 공개된 사실은 별도로 유지한다.
- 품질 진단의 훅 항목은 연재화에서만 적용한다. 이것을 최종화의 문학적 완성도 점수로 해석하지 않는다.

## 안전한 재검증

전제: Windows에 기존 `backend/.venv`, 프론트엔드 의존성과 Playwright 브라우저가 준비돼 있어야 한다. 저장소 루트에서 시작하며 새 의존성을 설치하지 않는다.

먼저 읽기 전용 사전 확인을 한다. 두 `Test-Path`는 모두 `True`여야 한다. 도구를 찾을 수 없거나 검사 오류가 나면 환경 준비 단계에서 중단한다. 포트 목록에 행이 나오면 점유 중이므로 중단하며 해당 프로세스를 종료하지 않는다. 브라우저 실행 시 실행 파일 누락 오류가 나도 테스트 환경 미준비로 기록하고, 여기서 설치나 우회를 하지 않는다.

```powershell
Get-Command node.exe,npm.cmd,npx.cmd -ErrorAction Stop
Test-Path backend/.venv/Scripts/python.exe
Test-Path frontend/node_modules/.bin/playwright.cmd
Get-NetTCPConnection -State Listen -ErrorAction Stop |
  Where-Object { $_.LocalPort -in @(15212,18112,18113,15225,15227) } |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

아래 세 브라우저 명령은 **한 번에 하나씩** 실행한다.

```powershell
# 저장소 루트에서
cd frontend
npm.cmd run build
npx.cmd playwright test --config playwright.ai-context.fixture.config.ts
npx.cmd playwright test --config playwright.preservation.config.ts
npx.cmd playwright test --config playwright.ai-context.config.ts
```

- 첫 fixture는 UI 요청·저장·취소·SPA 상태 경계를 모의 API로 검사한다(포트 15227).
- 보존 fixture는 기존 원고 복구·저장 동작을 검사한다(포트 15225).
- 실제 통합은 15212 → 18112 → 18113에서 브라우저·전용 프록시·임시 FastAPI·로컬 가짜 AI를 연결한다. 새 Windows TEMP SQLite에 Alembic head를 적용한 뒤 앱을 시작한다. `JIPPEEL_ALLOW_TEMP_CREATE_ALL`은 통합 fixture가 제거한다.
- 점유된 포트가 있으면 중단한다. 기존 서버를 종료하거나 8000/5173을 대신 사용하지 않는다.
- 통합 제공자 로그의 실제 `payload.messages`, 저장 원고 해시, API/DB 이력, 창작 데이터 전후값을 확인한다. 테스트 프로세스 종료만으로 정리를 단정하지 말고 소유 PID와 전용 포트 종료도 확인한다.
- `holding`은 fixture 보고서의 상태 값으로, 서버를 유지하며 테스트를 기다린다는 뜻이다. Windows Playwright가 소유 webServer 프로세스 트리를 종료하면 이 값이 종료 상태로 갱신되지 않고 남을 수 있다. 이때 별도 PID·포트 확인 결과를 근거로 남긴다.
- 기본 `.eval_tmp/ai-context-task-4/`는 새 실행이 갱신하는 fixture 포인터·증거 경로이고, `frontend/test-results/`는 브라우저 산출물 경로다. 둘 다 다음 실행에서 교체될 수 있다. 보존할 결과는 먼저 별도 폴더로 복사한다. 이번 최종 부모 검증의 보존 사본은 `.eval_tmp/ai-context-final-parent/`이며, 새 실행의 기본 출력 위치가 아니다.

전체 backend pytest는 [격리 실행기](isolated-backend-tests.md)를 사용한다. 앱/pytest import 전에 Windows 내부에서 DB·키·coverage 경로와 fake keyring을 설정한다. 충돌하는 기존 테스트 환경변수는 거부하며 직접 pytest 호출은 지원하지 않는다. 단위 테스트용 create-all 우회는 위 실제 브라우저 통합에 사용하지 않는다.

```powershell
# 저장소 루트에서 별도로 실행
cd backend
& .\.venv\Scripts\python.exe -I -S -B scripts\run_backend_pytest.py --isolation-preflight
if ($LASTEXITCODE -ne 0) { throw "backend isolation preflight failed" }
& .\.venv\Scripts\python.exe -I -B scripts\run_backend_pytest.py -q
if ($LASTEXITCODE -ne 0) { throw "backend tests failed" }
```

## 검증하지 않은 것

실제 외부 AI 모델의 응답 품질, 장편 기억력, 소설의 문학적 품질, 운영 환경 배포는 검증하지 않았다. 결정론적 가짜 AI는 요청 계약·흐름 검증용이다. 기존 Vite 중복 `build` 키 경고는 별도 정리 대상으로 남아 있다.
