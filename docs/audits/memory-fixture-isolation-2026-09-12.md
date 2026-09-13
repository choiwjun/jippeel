# M01~M05 frontend fixture 격리 실패 및 보정 승인

- 현재 상태: **보정·새 격리 회귀·독립 검토 후 M01~M05 수용 완료**. [최종 수용 기록](memory-m01-m05-2026-09-12/acceptance.md). 아래는 당시 실패·승인 이력이며 실패 run을 소급 PASS로 바꾸지 않는다.
- workflow `fd612dab-a366-4666-8092-39dfb37f8691`, worker `9b9b7611-e048-49cd-adbf-195df647396a`.
- main / HEAD `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`.

## 직접 확인한 근거

`/tmp/jippeel-memory-m01-m05-zr9p0h9_/manuscript-full-coverage.log`를 부모가 읽었다. Playwright는 **24 passed / exit 0**이지만 Vite가 `/api/v1/chapters/10/content`를 `127.0.0.1:8000`으로 전달하려다 **ECONNREFUSED 3건**을 출력했다. 이 실행은 assertion 통과일 뿐 fixture-only 격리 PASS나 최종 frontend coverage 근거가 아니다.

실제 확인 명령(cwd `frontend/`):

```text
env MEMORY_SCOPED_COVERAGE=1 node node_modules/@playwright/test/cli.js test --config playwright.preservation.config.ts --output /tmp/jippeel-memory-m01-m05-zr9p0h9_/manuscript-full-coverage-results
```

기존 `playwright.preservation.config.ts`는 전용15225/no reuse지만 기본 Vite 설정을 사용한다. `vite.config.ts`에는 `/api → http://localhost:8000` proxy가 있다. `page.route`가 reload/teardown의 pagehide keepalive를 놓쳤다는 것은 원인 가설이며 실제 회귀로 확인한다. 기록된 세 연결은 거부됐으며 서버의 응답/쓰기 성공은 기록되지 않았다. 운영 DB·해당 포트 서비스·credential을 조사하지 않았다.

## 부모 승인 — 요청 98e3ae64-49fe-404f-a06f-6f921e899160

- 같은 native workflow/전용 포트/no reuse를 유지한다. 원시 실패 로그·부분 diff를 보존한다.
- preservation mock을 context 수준으로 옮기고 필요한 fixture teardown 순서만 보강한다. 앱의 pagehide/keepalive/저장 큐/CAS/복구 계약은 변경하지 않는다.
- **fixture-only Vite config**에 API proxy가 실제 resolved 상태에서도 없음을 확인한다. 빈 객체 deep-merge로 원래 proxy를 남기지 않는다. production Vite 설정과 backend 통합용 설정은 불변이다.
- 이번 실행의 memory/AI-context fixture-only 설정에도 같은 no-proxy 구성을 재사용할 수 있다. 실제 backend8000을 실행하거나 접속해 검증하지 않는다.
- 누락 mock을 no-proxy의 기본HTML/임의200으로 숨기지 않는다. 예상 밖 `/api`가 fixture server에 도달하면 차단하고 method/path tripwire/latch를 남겨 reload/teardown까지 자동 실패로 검출한다. 의도적인 negative는 별도 disposable state/run으로 분리한다. positive run 위반 기록을 지우지 않는다.
- 실제 lifecycle 회귀·tripwire 검출 회귀 후, 새 로그로 full preservation과 공유 설정이 바뀐 memory/AI fixture를 재실행한다. 안전한 새 실행의 source/hash와 coverage를 맞춘다.

## context-only 한계와 다음 seam 승인

worker 보고에 따르면 `fixture-lifecycle-2.log`는 context route만으로도 Chromium pagehide keepalive를 처리하지 못함을 재현했다. 두 PUT은 no-proxy tripwire가 차단했고 suite exit1이 됐다. `/tmp/jippeel-fixture-tripwire-xlrSoG/violations.jsonl`을 보존한다. 이는 차단 장치의 유효한 negative이지 정상 fixture 격리 PASS가 아니다.

부모는 요청 `91e82e11-a9b7-4815-9d2b-560b77c44ad6`에 다음 test-only 확장을 승인했다.

- 기본 Chromium을 유지한다. keepalive 이동/수명/전달 의미를 바꾸는 browser flag는 승인하지 않는다. 강제 사전 flush·탐색·pagehide 비활성화·fetch 교체로 회귀를 우회하지 않는다.
- **동일 origin/전용 포트의 synthetic HTTP handler와 브라우저 mock이 같은 per-test 원고 상태/handler를 공유**한다. 설치된 Vite API를 이용한 Playwright-worker 소유 in-process 서버 방식을 사용할 수 있다. production 설정·앱 code·원고 큐/CAS/복구는 불변이다.
- 추가 backend/proxy8000/외부서비스/의존성·임의 forwarding 포트를 도입하지 않는다. 서버 중복 실행/reuse 금지와 resolved no-proxy를 유지한다.
- test/context 식별, 등록·해제, in-flight drain을 명시해 늦은 요청을 다음 테스트에 적용하지 않는다. 등록한 기대 API만 처리하며 unknown route/method/owner 또는 handler 오류는 persistent tripwire와 suite 실패로 남긴다.
- 먼저 실제 close/reload unload PUT의 본문·원래 작품/회차·expected_revision·공유 state 반영 및 unknown-API negative를 검증한다. 성공 후 영향받은 전체 fixture와 source-mapped coverage를 새로 수집한다.
- 일반 mock framework로 확대하지 않는다. 단일 소유 서버/공유 상태로 해결할 수 없거나 실행 기반·권한 문제가 발생하면 부분 증거와 다음 결정을 보고한다.

## 별도 근거 유지

backend421P/기존 외부skip1/70subtests/격리 위반0은 별도 native runner 실행 근거다. memory30/AI fixture15의 이전 로그에 proxy 오류가 없었다는 보고만으로 새 공유 설정의 검증을 대신하지 않는다. 전체 frontend V01·실제 운영/G gate까지 완료했다고 주장하지 않는다.
