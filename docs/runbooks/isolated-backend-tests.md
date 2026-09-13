# 격리된 backend 테스트 실행

2026-09-12부터 지원하는 pytest 진입점은 **`backend/scripts/run_backend_pytest.py`**다. 직접 `pytest`/`python -m pytest` 실행은 앱 import 전에 의도적으로 거부한다. DB 환경변수만 지정하는 과거 방식은 키 저장소와 coverage를 격리하지 못한다.

## 전달할 필수 소스

- `backend/scripts/run_backend_pytest.py` — 공식 진입점
- `backend/tests/isolation_guard.py` — 테스트 프로세스 격리
- `backend/tests/conftest.py` — 앱 import 전 초기화 확인
- `backend/tests/test_isolation_guard.py` — 합성 회귀

`.eval_tmp/run_backend_pytest.py`는 기존 호출을 위한 호환 shim일 뿐이며 공식 실행에는 필요 없다. 이 목록은 파일 전달 계약이지 stage/commit 지시가 아니다.

## Windows PowerShell / cmd

저장소 루트에서 `backend`로 이동한다. 이미 설치된 프로젝트 venv를 사용하며 설치나 실제 provider 시작을 수행하지 않는다.

```text
cd backend
.venv\Scripts\python.exe -I -S -B scripts\run_backend_pytest.py --isolation-preflight
.venv\Scripts\python.exe -I -B scripts\run_backend_pytest.py -q
```

WSL에서 같은 native Windows Python을 실행할 때:

```bash
cd backend
.venv/Scripts/python.exe -I -S -B scripts/run_backend_pytest.py --isolation-preflight
.venv/Scripts/python.exe -I -B scripts/run_backend_pytest.py -q
```

선택한 테스트 파일/노드만 실행하려면 `-q tests/test_crypto.py`처럼 지정한다. 디렉터리 `tests` 인자는 사용하지 않고 전체 실행은 대상 인자를 생략한다.

`--isolation-coverage`를 추가하면 동일한 suite를 실행하며 **canon·bootstrap·격리 helper·projects·quality 다섯 모듈**의 line/branch coverage를 측정한다. projects는 [M01~M05 국소 계측 승인](../superpowers/plans/2026-09-12-memory-scoped-coverage.md), quality는 [B03 국소 계측 승인](../superpowers/plans/2026-09-12-quality-metric-corrections.md)의 고정 목록 추가다. 임의 `--cov` 인자는 허용하지 않으며 전체 앱 모듈의 coverage라고 해석하지 않는다.

기존 `DATABASE_URL`, `JIPPEEL_KEY_FILE`, `COVERAGE_FILE`, `COVERAGE_RCFILE`, `PYTEST_ADDOPTS`, `PYTEST_PLUGINS` 값이나 사용자 pytest/config 출력 덮어쓰기는 거부한다. 충돌 시 자동으로 사용자 설정을 바꾸지 않는다. 별도의 테스트 셸에서 충돌 변수를 제거한 후 실행한다. WSL 셸 변수 전달에 의존하거나 운영 변수·실제 키 경로를 넣지 않는다.

## 확인할 결과와 한계

- 첫 JSON: Windows 내부의 fresh TEMP root/목적지, fake keyring, 앱/pytest/coverage import 이전 상태.
- preflight: stdlib 내부 socketpair IPC만 동작하고 앱/pytest 미import·위반 0.
- 최종 JSON: pytest exit, 내부 IPC 횟수, 실제 subprocess 시도 수, fake keyring 호출 수, 위반 latch. exit 0뿐 아니라 위반 0도 확인한다.
- DB·fallback·coverage 데이터/JSON·로그·pytest temp/cache는 출력된 fresh root를 사용한다. 기존 `backend/.coverage`는 쓰지 않는다. 보존할 증거는 TEMP 청소 전에 따로 보관한다.
- 실제 Fernet/fallback을 쓰되 keyring은 가짜이며, 외부 humanize 스크립트는 실행하면 실패하는 합성 파일만 둔다. 기존 외부 metrics 상수 비교 1건은 원래 미설치 조건으로 skip되어 별도 미검증으로 남는다.
- 보호는 **쓰기 모드의 Python `open`, 알려진 민감 파일명 읽기, SQLite 연결, 해당 crypto 경로와 network/subprocess 호출**에 대한 테스트용 검사다. 일반 OS sandbox나 모든 파일시스템 변경의 차단을 보장하지 않는다. 특히 `os.rename`/`os.remove` 등은 이 audit hook의 포괄적 보호 대상이 아니다. 따라서 소스 범위·전후 hash·실행 기록을 함께 확인한다.
- 실제 provider/credential·운영 DB·브라우저/지정 실기기 검증과 배포는 이 명령의 수용 범위가 아니다.
