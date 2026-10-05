# 버그 8건 수정 — 최종 수용 2026-10-05

승인: 사용자 요청 “모두 수정해. 그리고 커밋 푸시해”. [수정 전 조사](report.md)의 BUG-01~08 구현·격리 회귀·독립 검토와 이번 관련 파일의 `origin/main` 선별 게시가 승인됐다.

## 수정 결과

| ID | 수정 | 직접 검증 |
| --- | --- | --- |
| BUG-01 | 메모 mutation에 작품·회차·입력 문자열을 고정하고 전환/unmount 시 원래 회차로 flush | 800ms 안에 회차 전환해도 1화에만 메모 저장 |
| BUG-02 | 장면 저장 직전 초기화를 제거하고 대상 id·편집 제목/본문을 변수로 고정 | 장면A의 수정 본문이 PATCH와 서버 값에 반영 |
| BUG-03 | 승인·폐기 상태를 포함한 출처 graph를 배치 적재하고 원문/revision·해시·하위 출처의 stale을 재귀 전파 | 원문 변경·승인 취소·누락·잘못된 출처가 아크와 권 기억까지 전파. 건강한 하위 기억으로 fallback |
| BUG-04 | 권(null last)→sort_order→id 공통 순서로 이웃·미래 참조·rollup 출처/planner·프론트 정렬 일치 | 권별 sort 중복·동일 sort·권 없음, 다단계 rollup의 미래 누출/과거 누락 차단 |
| BUG-05 | 회차/전체 내보내기는 draft를 flush하고 상세 메타데이터에 저장된 본문/revision만 병합 | 미저장 회차/전체 본문·파일명·제목·권·순서 보존, 500/409 다운로드 차단, 동시 저장 미덮어쓰기, 오래된 GET 미반영 |
| BUG-06 | mutation의 원래 상세 캐시에 변경 필드만 병합하고 원고/revision 보존 | 저장 후 상태 즉시 반영, 늦은 메타 응답이 더 최신 원고를 덮지 않음 |
| BUG-07 | lifecycle 근거 회차 참조가 있으면 삭제를 원고 보존 409로 반환 | departed/deceased의 데이터 보존, 참조 해제 후 204 삭제 |
| BUG-08 | NOT NULL PATCH 필드의 명시적 null은 모델 검증에서 422로 거부 | 9개 필드 422와 기존 값 보존, nullable volume/memo/lifecycle 참조는 null 허용 |

요약 planner는 stale 원천을 제외한다. worker는 호출 전후 새 graph의 존재·종류·승인·freshness·출처 해시를 확인한다. 실제 GPT 어댑터의 Session helper 계약을 유지했으며 fake transport로 arc/volume 경로를 통과시켰다. 승인된 기억 자체를 변경하거나 삭제하는 자동 처리는 없다.

## 실행 근거

| 검증 | 결과 | 증거 |
| --- | --- | --- |
| 수정 전 전체 backend | 950 passed / 1 skipped / 70 subtests | [baseline-results.txt](baseline-results.txt) |
| 새 backend 회귀의 RED | 20 failed / 1 passed, 격리 위반 0 | [backend-regressions-red.txt](backend-regressions-red.txt) |
| 관련 backend 회귀 | 133 passed, 격리 위반 0 | [backend-focused.txt](backend-focused.txt) |
| 최종 backend 전체 | **979 passed / 1 skipped / 70 subtests passed** | [backend-full.txt](backend-full.txt) |
| 새 browser 회귀 | **10개 통과**, unmocked API 0, 실제 provider 0 | [frontend-regressions.json](frontend-regressions.json) |
| 기존 원고 보존 browser suite | **26 passed**, HTTP/keepalive fixture escape 0 | [frontend-preservation.txt](frontend-preservation.txt) |
| frontend type/build | **PASS**, 최종 `tsc -b && vite build` | [frontend-build.txt](frontend-build.txt) |
| 독립 검토 | 지적 6건 수정 후 **수용 가능** | [independent-review.md](independent-review.md) |

최종 backend runner는 앱 import 전 native TEMP DB·fake keyring·네트워크/subprocess 차단을 설치했다. `violations=[]`, `subprocess_attempts=0`이다. Browser는 proxy 없는 fixture 서버와 합성 API를 사용했고, 전용 API tripwire 두 파일 모두 0 bytes였다. `summary_provider` 회귀는 실제 메시지 조립/worker를 사용하되 `complete_chat`과 client factory를 fake로 대체했다.

Backend에 신규 회귀 27개 및 adapter 회귀 2개를 추가했다. 기존 volume worker fixture의 가짜 dangling source id는 실제 승인 하위 요약 id로 바꿔 출처 graph 계약을 검증하도록 했다. 기존 assertion의 의미를 약화하지 않았다.

RED 로그는 Git 공백 검사를 위해 행끝 공백만 제거했다. assertion·traceback·실행 결과·격리 기록과 행 수는 유지했다.

## 재실행

Backend 작업 디렉터리에서 공식 격리 runner만 사용한다.

```bash
.venv/Scripts/python.exe -I -B scripts/run_backend_pytest.py -q
```

Frontend 작업 디렉터리에서 기존 fixture 보존 suite와 build를 실행한다.

```bash
./node_modules/.bin/playwright test --config=playwright.preservation.config.ts
npm run build
```

추가 browser 회귀는 frontend에서 `JIPPEEL_FIXTURE_API_VIOLATIONS`에 새 TEMP 파일을 지정하고 `vite.fixture.config.ts` 서버를 전용 포트 15483으로 띄운 뒤 프로젝트 루트에서 실행한다. 서버는 다른 fixture suite와 순차로 실행한다. 최초 cold Vite 적재 시간 때문에 harness의 편집기 초기 대기는 60초다.

```bash
node docs/audits/2026-10-05-bug-hunt/frontend_probe.cjs --verify-fixes
```

`backend_probe.py`와 `frontend_probe.cjs`의 기본 모드는 수정 전 결함 assertion의 역사 기록이다. 현재 정상 판정에는 새 backend 회귀와 `--verify-fixes`를 사용한다.

## 경계·게시

- 운영 DB·실제 provider/credential·실기기·migration·배포는 수행하지 않았다. 이번 수정은 migration이 필요 없다. 실행 중인 운영 앱에는 재기동/배포가 별도로 필요하다.
- Git은 이번 소스·회귀·조사/수용 자료만 선별한다. 기존 `.cc-safety-net`, `.eval_tmp`, `.omo`, `.pi-conductor`, `.team`, `.vite` 자료와 DB 백업은 게시 대상에서 제외하고 보존한다.
- 게시 대상은 `origin/main`이다. 정확한 커밋 hash와 원격 게시 여부는 Git 로그 및 최종 응답으로 확인한다. 강제 push는 사용하지 않는다.
