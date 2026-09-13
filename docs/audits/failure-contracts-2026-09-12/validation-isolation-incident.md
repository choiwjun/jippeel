# B01/B02 검증 격리 실패 — 사고 당시 기록

> **후속 종결:** 사용자 승인된 B04 보강 후 새 격리 실행 419P/기존 외부 skip1, 독립 재검토 2건 PASS로 B01/B02/B04를 수용했다. [최종 수용·증거](b04-review-fixes.md)를 따른다. 아래 401개 실행의 보존 실패·원본 미복구·credential 부수 효과 미확정은 역사적 한계로 유지한다. 추가 실행 중단/미착수 표시는 사고 당시 상태다.

- 날짜: 2026-09-12
- 사고 당시 상태: **제품 구현·401개 assertion 통과 / 격리·보존 gate 실패 / 추가 실행 중단**
- 저장소: `/mnt/c/Users/wj941/Documents/jippeel`, `refs/heads/main`, HEAD `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`
- workflow `c3560081-9458-4464-b041-1e41518a0244`: 실행 흐름은 종료, 반환은 `blocked-before-review`.
- child `ea631bc5-5328-4afe-a253-d199a4710ee8`: `IMPLEMENTATION_GATE: BLOCKED`로 종료. 실행 중인 worker와 독립 reviewer는 없다.

## 확인된 구현과 테스트

B01은 구조 전체 검증·기존 1회 repair·실패 이력 미생성을, B02는 번호 슬롯 선택과 목차/생성 anchor/VolumeNote의 동일한 첫 유효 항목 선택을 구현했다.
변경 제품 파일은 `backend/app/services/canon.py`, `backend/app/services/bootstrap.py`다.
새 회귀는 `test_canon_failure_contract.py` 52건과 `test_bootstrap_outline_contract.py` 32건이며 기존 canon fixture의 승인된 계약 보정도 유지한다.

| 검증 | 실행 결과 |
| --- | --- |
| B01 RED → GREEN | 37 failed / 25 passed → 62 passed |
| B02 metadata 포함 RED | 24 failed / 8 passed |
| 결합 targeted GREEN | 105 passed |
| 최종 전체 backend | **401 passed, pytest summary 4 warnings**; 종료 시에도 unclosed SQLite ResourceWarning 메시지가 있음 |
| bootstrap coverage | line 278/289 (96.19%), branch 75/92 (81.52%) |
| canon coverage | line 54/62 (87.10%), branch 15/18 (83.33%) |

부모가 `full-final.txt`와 `coverage-summary.json`을 직접 읽었다. 이는 실제 assertion/coverage 측정 결과이지만 **안전한 격리·기존 파일 보존·최종 수용을 증명하지 않는다**. 독립 검토는 시작되지 않았다.

## 확인된 격리 실패와 미확정 영향

1. WSL 셸에서 지정한 환경변수가 Windows Python에 전달되지 않았다. 앱을 import하지 않는 stdlib sentinel에서 `sentinel_arrived`, `coverage_arrived`, `coverage_is_set`, `key_path_is_set`, `database_url_is_set`이 모두 false였다.
2. DB는 별도 경로로 격리됐다. `.eval_tmp/run_backend_pytest.py`가 **Windows 내부에서 pytest import 전** 새 TEMP `DATABASE_URL`을 설정하고 conftest도 per-test TEMP DB를 사용한다. 셸 변수와 독립된 근거다.
3. `COVERAGE_FILE`이 전달되지 않아 기존 `backend/.coverage`가 갱신됐다. JSON 보고서 목적지는 CLI 인자여서 TEMP에 기록됐지만 내부 coverage 데이터 파일은 보호되지 않았다.
4. `JIPPEEL_KEY_FILE`도 전달되지 않았다. `test_bootstrap_api.default_endpoint`의 합성 API key 저장이 `crypto.get_cipher()`를 호출하는 경로가 있다. 이 함수는 **파일 경로 설정 여부와 무관하게 keyring을 먼저 호출**한다. `test_crypto`의 지역 fixture는 fallback 파일만 바꾸며 전역 keyring 접근을 차단하지 않는다.
5. 따라서 기본 키 저장소/기본 키 파일에 접근했을 가능성이 있다. **실제 키 내용과 저장소 상태는 조회하지 않았으며, 접근·생성 여부는 미확정**이다. 키 유출을 주장하지 않으며 삭제·초기화·교체·회전도 하지 않는다.

이는 실행 설정과 확인 절차의 잘못이다. 사용자에게 같은 제품 정책 승인을 반복 요구할 사안이 아니며, 별도의 생성물 처리 결정과 테스트 격리 보정이 필요하다.

## 기존 coverage 보존 실패

- 원래 SHA-256: `d6ad2c71e630fb2473c1ee0439e234d9d555c01183d0698b413d3c462b0dee77`
- 현재 SHA-256: `a8dbb468171bf47a125460523e569bf205e9dc0784a018301adb9598a3f58624`
- 현재 77,824바이트. TEMP forensic 사본과 hash가 동일하다.
- Git 미추적 파일이며 알려진 baseline/evidence/Git 범위에서 정확한 원본을 찾지 못했다. 더 넓은 사용자 백업의 존재 여부까지 판단하지 않는다.
- 원본을 추측해 재생성하거나 현재 파일을 덮어써 복원한 척하지 않는다. 현재 생성본을 유지하는 예외 처리 또는 사용자 보유 원본의 제공 여부는 소유자가 결정해야 한다.

worker 검사에서 index와 사용자가 적용한 보안 정책은 불변이다. B01/B02 원본 대비 diff에 기존 OAuth 변경을 섞어 이번 변경으로 주장하지 않는다.

## 증거 위치

TEMP 루트: `/tmp/jippeel-b01-b02-resumed-lib0k2a8`

- `full-final.txt`, `coverage-summary.json`, `full-final-coverage.json`
- `env-sentinel.txt`, `isolation-incident.md`, `coverage-forensics.json`
- `observed-coverage-forensic-copy` — 현재 변경된 생성물의 사본이며 옛 원본이 아님
- `hashes.before.json`, `hashes.after.json`, `preservation.json`
- `original-baseline.final.delta.diff`, `resumed-baseline.final.delta.diff`, `commands.json`

worker 원본 보고서:
`/home/hunter8891/.pi/agent/sessions/--mnt-c-Users-wj941-Documents-jippeel--/subagent-artifacts/outputs/c3560081-9458-4464-b041-1e41518a0244/implementation/b01-b02-resumed.md`

receipt:
`/tmp/pi-subagents-uid-1000/async-subagent-runs/c3560081-9458-4464-b041-1e41518a0244/workflow-receipt.json`

부모의 감사 복사와 정책 hash 조회를 묶은 후속 명령도 Safety Net이 정책 보호 경로를 이유로 실행 전에 차단했다. 이 복합 명령은 재시도하지 않았으며, 해당 시도의 프로젝트 내 복사본이 있다고 주장하지 않는다. 위 원본 증거는 기존 TEMP/session 경로에 남아 있다. 실제 정책 수정은 하지 않았다.

## 후속 승인과 조치 — 격리 보강 착수

2026-09-12 사용자가 “진행해”로 **현재 재생성된 `.coverage` 유지와 테스트 격리 보강·재검증을 승인**했다. 부모는 현재 hash가 `a8dbb468171bf47a125460523e569bf205e9dc0784a018301adb9598a3f58624`임을 다시 확인했다. 이는 옛 원본 복원이나 당시 보존 성공의 소급 판정이 아니다.

1. 현재 `.coverage`를 새 불변 기준으로 보존한다. 기존 원본 미확보와 당시 키 저장소 부수 효과 미확정 기록은 유지한다.
2. 테스트 코드/실행기에만 한정해 앱 import 전 전역 crypto/keyring 격리와 TEMP 경계 fail-closed 검사를 보강한다. 제품 암호화 동작과 실제 키 저장소는 변경하지 않는다.
3. 같은 native 프로토콜에서 per-process WSLENV 전달 또는 명시적인 Windows 내부 설정을 먼저 stdlib sentinel로 검증한다. **환경 전달 보정만으로 keyring 격리가 해결되지는 않는다.**
4. 전체 회귀와 coverage를 새 TEMP에 기록하고 기존 파일·정책·index의 불변을 확인한 뒤 fresh 독립 검토를 수행한다.
5. 원장 B01/B02는 그때까지 수용 차단 상태로 유지한다. 기존 P1 제품 수정 완료를 다시 열지는 않는다.
