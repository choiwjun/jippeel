# AnyIO·Starlette·HTTPX 호환성 조사

- 조사일: 2026-09-10
- 범위: `HANDOFF.md` 최신 인계의 AnyIO/Starlette 경고 원인과 의존성 대안 확인
- 변경 범위: `backend/requirements.txt`에 호환성 제약을 추가하고 전체 회귀 검증

## 결론

경고에는 두 원인이 있었다.

1. Starlette 1.6.0은 `httpx2`가 없으면 `httpx` TestClient fallback을 deprecate한다.
2. AnyIO 4.15.1에서는 Starlette 1.6.0이 사용하는 `anyio.abc.BlockingPortal` alias가 deprecate된다.

승인된 대응으로 `backend/requirements.txt`에 다음을 추가했다.

```text
anyio>=4.14,<4.15
httpx2>=2.0.0
```

이 조합은 Starlette의 `httpx2` 경로를 사용하고 AnyIO 4.15 alias 경고를 피한다.

## 현재 환경 증거

`backend/.venv` 설치 버전:

| 패키지 | 버전 |
|---|---:|
| fastapi | 0.141.1 |
| starlette | 1.6.0 |
| anyio | 4.14.2 |
| httpx | 0.28.1 |
| httpx2 | 2.12.0 |

Starlette의 현재 소스는 `backend/.venv/lib/python3.14/site-packages/starlette/testclient.py:40-50`에서 `httpx2`를 먼저 import하고, 없을 때 `httpx` fallback과 `StarletteDeprecationWarning`을 발생시킨다. 현재 파일의 53행은 타입 별칭이며 경고 발생문이 아니다. 핸드오프의 행 번호는 설치 패키지 버전 변화로 stale 상태다.

## 격리 재현 결과

동일한 최소 FastAPI 앱을 `TestClient`로 호출했다.

| 조합 | 응답 | 경고 |
|---|---:|---|
| FastAPI 0.141.1 + Starlette 1.6.0 + AnyIO 4.14.2 + HTTPX 0.28.1, `httpx2` 없음 | 200 | `StarletteDeprecationWarning: Using \`httpx\` with \`starlette.testclient\` is deprecated; install \`httpx2\` instead.` |
| 위 조합 + `httpx2` 2.12.0 | 200 | 없음 |
| FastAPI 0.141.1 + Starlette 1.6.0 + AnyIO 4.15.1 + `httpx2` 2.12.0 | 200 | `DeprecationWarning`: `anyio.abc.BlockingPortal` alias |
| FastAPI 0.141.1 + Starlette 1.6.0 + AnyIO 4.14.2 + `httpx2` 2.12.0 | 200 | 없음 |
| FastAPI 0.141.1 + Starlette 0.48.0 + AnyIO 4.15.1 + HTTPX 0.28.1 | 200 | `DeprecationWarning`: `anyio.abc.BlockingPortal` alias |

초기 후보 비교는 임시 격리 환경에서 수행했다. 최종 requirements 조합은 별도 격리 설치로 검증했다.

재현 스크립트의 핵심 명령 예:

```bash
uv run --isolated \
  --with 'fastapi==0.141.1' \
  --with 'starlette==1.6.0' \
  --with 'anyio==4.14.2' \
  --with 'httpx==0.28.1' \
  python /tmp/check_testclient_warning.py
```

## 호환성 판단

- Starlette 1.6.0의 기본 의존성은 `anyio>=3.6.2,<5`지만, AnyIO 4.15.1의 alias deprecation과는 별도 호환성 문제가 있다.
- Starlette 1.6.0의 `full` extra는 `httpx2>=2.0.0`과 `httpx>=0.27,<0.29`를 별도 선택지로 선언한다.
- FastAPI 0.141.1은 `starlette>=0.46.0`을 요구하며, `httpx`는 standard extra에만 포함한다.
- 현재 검증된 안전 범위는 `anyio>=4.14,<4.15`와 `httpx2>=2.0.0`이다.

## 저장소 회귀 검증

최종 `requirements.txt`를 임시 격리 환경에 설치하고 전체 백엔드 테스트를 실행했다. `DeprecationWarning`을 오류로 승격했다.

```text
277 passed in 22.17s
```

호환성 경고 없이 통과했다. 기존 `backend/.venv` 전체 실행에서 관찰된 16개 `ResourceWarning`은 테스트 종료 시 SQLite 연결 정리 문제이며, 이번 의존성 변경의 deprecation 경고와는 별개다.

## 승인된 결정과 다음 게이트

- `httpx2>=2.0.0`을 명시해 Starlette의 의도된 TestClient 경로를 사용한다.
- `anyio>=4.14,<4.15`로 AnyIO 4.15 alias deprecation을 피한다.
- 최종 requirements 조합의 격리 설치와 백엔드 277개 전체 테스트를 통과했다.
- 다음 게이트는 프론트 빌드와 변경 diff 최종 검토다. 이후 핸드오프의 실제 모델 품질 평가 설계로 이동한다.

## 출처

- Starlette TestClient 공식 문서: <https://www.starlette.io/testclient/> (2026-09-10 확인)
- Starlette 1.6.0 PyPI metadata: <https://pypi.org/pypi/starlette/1.6.0/json> (2026-09-10 확인)
- HTTPX2 2.12.0 PyPI metadata: <https://pypi.org/pypi/httpx2/2.12.0/json> (2026-09-10 확인)
- AnyIO 4.15.1 PyPI metadata: <https://pypi.org/pypi/anyio/4.15.1/json> (2026-09-10 확인)
- FastAPI 0.141.1 PyPI metadata: <https://pypi.org/pypi/fastapi/0.141.1/json> (2026-09-10 확인)
- 로컬 Starlette source: `backend/.venv/lib/python3.14/site-packages/starlette/testclient.py:40-50`
- 프로젝트 선언 의존성: `backend/requirements.txt`
