# B04 독립 검토 지적 보정·재검증

- 날짜: 2026-09-12
- 상태: **B01/B02/B04 부모 최종 수용 완료 — 명시된 한계 포함**. 독립 재검토 2건 PASS와 새 실행·보존 증거를 확인했다. 운영 수용·배포 승인은 아니다.
- main / HEAD `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`; stage/commit 없음.

## 최초 검토와 부모 결정

workflow `510018b7-5387-4f90-b733-859a51971986`의 두 독립 reviewer는 B01/B02 제품 계약과 기존 회귀를 확인했지만 다음을 지적했다.

1. **P1:** Windows의 대소문자 차이로 알려진 민감 파일 읽기가 audit 검사에서 빠질 수 있음.
2. **P1:** 기존 direct-pytest runbook과 새 fail-closed 실행 계약 불일치.
3. **P2:** worker의 “모든 파일 쓰기 차단” 설명이 실제 writable-open 보호보다 넓음.

부모가 테스트 전용 범위에서 최소 보정했다. 실제 키 저장소 접근이 있었다는 증거로 지적을 확대하지 않았으며 제품 crypto/canon/bootstrap은 변경하지 않았다.

## 수정

- `backend/tests/isolation_guard.py`: 알려진 민감 파일명의 대소문자·trailing dot/space·stream 별칭을 비교할 때 정규화한다. 실제 경로 소유 검사는 유지한다.
- `backend/tests/test_isolation_guard.py`: str/bytes 합성 alias 18사례를 추가했다. 실제 파일을 열지 않으며 거부 전후 소비자 호출 0·latch 증가 및 소유 경로 허용을 확인한다.
- `backend/scripts/run_backend_pytest.py`: 기존 검증된 설치/실행/최종 latch 검사 흐름을 제공하는 공식 소스 진입점.
- `.eval_tmp/run_backend_pytest.py`: 공식 진입점으로 위임하는 기존 호출 호환 shim. `.eval_tmp`가 ignored라는 주장은 하지 않는다.
- [지원 실행 가이드](../../runbooks/isolated-backend-tests.md)에 전달할 필수 소스를 명시하고 `ai-context-consistency.md`, `manuscript-preservation.md`의 실제 명령을 바꿨다. 과거 보존 감사는 당시 결과를 유지하면서 명령이 대체됐음을 안내한다.

**보장 범위 정정:** 이 helper는 쓰기 모드 Python `open`, 알려진 민감 파일명 읽기, SQLite 연결, 해당 crypto 사용 경로 및 network/subprocess 호출을 검사한다. 일반 OS sandbox가 아니며 `os.rename`/`os.remove` 등 모든 파일시스템 변경을 차단한다고 주장하지 않는다. 실제 보존은 소스 검토·범위 한정 전후 hash·실행 기록을 함께 근거로 한다. 이전 worker 보고서의 넓은 문구는 이 설명으로 정정한다.

## 실행 증거

증거 루트: `/tmp/jippeel-b04-review-fixes-t4hs3psy`

| 실행 | 실제 결과 | 로그 |
| --- | --- | --- |
| 합성 alias RED | 19개 중 새 alias subtest 18 failures | `aliases-red.txt` |
| 합성 guard GREEN | 19 tests OK | `aliases-green.txt` |
| 공식 entrypoint preflight | app/pytest 미import, 내부 IPC 1, 위반 0 | `canonical-preflight.txt` |
| 기존 호환 entrypoint preflight | 동일한 격리 확인 | `compat-preflight.txt` |
| 최종 소스 전체 suite | **419 passed, 1 skipped, 19 warnings, 70 subtests passed; exit 0** | `full-final-clean.txt` |

최종 run root는 Windows TEMP의 `jippeel-isolated-b53rk_44`다. 실제 coverage data와 JSON 모두 해당 root 안에 있다. 최종 attestation: IPC 233, subprocess 시도 0, fake-keyring 호출 7, `violations=[]`. 의도적인 합성 negative는 별도 state를 사용하며 이 latch와 섞지 않는다.

| 모듈 | line | branch |
| --- | --- | --- |
| bootstrap | 278/289 — 96.19% | 75/92 — 81.52% |
| canon | 54/62 — 87.10% | 15/18 — 83.33% |
| isolation_guard | 171/183 — 93.44% | 55/60 — 91.67% |

- 정확한 명령·cwd·exit·로그: `validation-commands.json`.
- 원본 coverage JSON: `coverage-clean.raw.json`; JSON 의미가 같은 읽기용 `coverage-clean.pretty.json`; 요약·hash: `coverage-clean-summary.json`, `coverage-clean-manifest.json`.
- 부모 수정 전후 diff: `delta-clean.diff`; source hash: `before-hashes.json`, `final-clean-hashes.json`; 보존: `preservation-clean.json`.
- B04 전체 시작점 대비 증거는 `/tmp/jippeel-b04-15o9xrm4`; 최초 B01/B02 제품 delta는 `/tmp/jippeel-b01-b02-resumed-lib0k2a8/original-baseline.final.delta.diff`에 별도로 남는다.

## 독립 재검토 및 부모 수용

workflow `c754cea0-dbe9-4990-be98-48a1d2cf0c32`는 `ready-for-parent-acceptance`로 종료했다. 처음 fresh로 시작한 두 독립 reviewer의 retained follow-up이며, 부모의 수정 맥락을 그대로 상속한 자기 검토가 아니다.

- 코드 검토 `e2ddb15d-f06a-4976-ae1f-89791cd0a23f`: **REVIEW_GATE: PASS**.
- 격리·보존 검토 `f7811f72-003c-4794-9568-c650f6245659`: **REVIEW_GATE: PASS**.
- 부모가 두 보고서를 끝까지 읽고, 검토 후 소스·보존 대상 10개 hash 불변을 다시 확인했다. B01/B02의 승인 계약과 B04 보강을 수용한다. 완료된 기억 P1은 재개하지 않는다.
- [코드 검토 원문](accepted-evidence/code-review.md.txt), [격리 검토 원문](accepted-evidence/integrity-review.md.txt), [최종 실행](accepted-evidence/full-final-clean.txt), [보존](accepted-evidence/preservation-clean.json), [사본 manifest](accepted-evidence/manifest.json)를 프로젝트에 보존했다. 필수 증거 16파일의 원본/사본 byte equality를 확인했다. stage/commit/push는 하지 않았다.
- 최초 401개 실행의 격리·원본 보존 실패는 소급 PASS로 변경하지 않는다. 후속 격리 수용과 과거 사고 한계는 별개다.

## 보존 및 남은 한계

- 현재 승인된 `.coverage` hash `a8dbb468171bf47a125460523e569bf205e9dc0784a018301adb9598a3f58624` 불변. 처음 손실된 d6ad… 파일을 복원한 것이 아니다.
- B04 시작 전 hash와 비교한 **backend/app 37파일**이 불변이다. 제품 crypto hash `5902a04108befdb29c1652d353eda0c2e6d0bdd22cf67c2560d6d0be33f60f2e`, index hash `bf9b6260efa6613d5136561a7b53fa1f42c55f3b7af2d49748eb4ae341044e00`도 유지했다.
- 범위 한정 `git diff --check`는 exit 0. 전체 dirty worktree 검사는 기존 QA 문서/projects 등 CRLF/trailing-whitespace 지적으로 exit 2였다(`diff-check.txt`). 이번 범위 밖 변경을 정리하지 않았다. 새 Python 파일의 trailing whitespace도 별도 확인·보정했다.
- 마지막 active LSP probe는 5파일 diagnostics 0, **clean 0 / inconclusive 5**(timeout 1, silent push-only 4)다. clean 근거로 쓰지 않는다.
- 기존 `test_gate_values_match_im_not_ai_constants`의 미설치 skip 1건만 부모가 외부 검증 미실시로 명시해 허용했다. 상수 참조를 위조하지 않는다. 후속 todo #18이다.
- SQLite ResourceWarnings 19건, 실제 provider·브라우저/지정 실기기 미재검증, 과거 credential 부수 효과 미확정을 유지한다.
- 보안 정책 수정·운영 DB·실제 키 저장소 조회/복구·Git 반영을 수행하지 않았다.
