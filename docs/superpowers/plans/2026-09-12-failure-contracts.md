# B01/B02 실패 계약 보정 계획

- 작성일: 2026-09-12
- 상태: **B01/B02/B04 최종 수용 완료 — 419P/기존 외부 skip1, 독립 재검토 2건 PASS**. 최종 근거는 §10이며 아래 승인·중단 계획은 당시 이력으로 보존한다.
- 승인: 2026-09-12 사용자가 제시된 B01/B02 기준의 수정→회귀→독립 검토에 “작업진행해”로 승인했다. 운영·실제 provider·배포·Git 변경은 제외한다.
- 크기: standard — 실패 응답 계약과 생성 내용 선택 정책에 영향을 준다.
- 현재 작업 원장: [B01/B02](../../handoffs/2026-09-08-remaining-work.md)
- 재현 근거: [보고서](../../audits/failure-contracts-2026-09-12/reproduction.md), [합성 입력·출력](../../audits/failure-contracts-2026-09-12/results.json), [stdout](../../audits/failure-contracts-2026-09-12/stdout.txt)
- 재현 실행: native Pi worker, Windows Python 3.14.4, 실제 helper import/direct call 및 메모리 fake 응답. 실제 API/DB 저장/pytest/full suite 검증은 아직 아니다.
- 이전 구현 시도는 B01 테스트 2파일만 작성한 뒤 실행 전 차단됐다. [역사적 체크포인트](../../audits/failure-contracts-2026-09-12/implementation-blocked.md)를 보존한다.
- 재개 전 부모 확인: `.cc-safety-net/policy.json`은 승인된 한 TEMP 파일의 두 경로 표기만 포함, `status`는 destructive/secrets 모두 ok, `policy check`는 No changes. 제품/테스트 hash와 HEAD 불변도 확인했다. 재개 후 전체 401개 assertion은 통과했지만 환경 전달과 기존 coverage 보존 실패를 확인했다. [격리 실패 보고](../../audits/failure-contracts-2026-09-12/validation-isolation-incident.md)에 따라 추가 실행·독립 검토는 중단했다.

## 1. 요구사항과 확인한 문제

### B01: 검사 실패를 모순 0건으로 표시하지 않는다

- `issues` 누락·잘못된 컨테이너·항목이 빈 목록/부분 성공이 되거나 TypeError로 1회 repair를 우회한다.
- parser와 fake coroutine 각각 14사례: 기준선 4 PASS, 잘못된 형식 10 RED. 같은 입력을 두 층에서 관찰한 결과이며 독립 결함 20개로 합산하지 않는다.
- 정상 빈 배열·정상 항목·unknown severity 보정·깨진 JSON repair는 유지한다.

### B02: 요청한 권별 회차 구성을 보장한다

- 요청은 2권×2화인데 2권만 네 번 나오거나, 같은 회차 번호/정렬값이 중복된다.
- helper 13사례: 기준선 4 PASS, 권/회차/정렬 불변식 9 RED. 총 개수와 입력 불변은 모두 통과했다.
- 이미 정상인 이름·제목·시놉시스·핵심 사건을 불필요하게 바꾸지 않는다.

이 RED는 예상 계약 위반을 기록한 것이며 probe 자체는 exit 0이다. DB/key 생성, 앱 startup, 실제 네트워크 접근은 없었다.

## 2. 승인된 수정 정책

### B01

1. `_extract_json` 공유 계약은 유지한다.
2. `issues`는 필수 list, 각 항목은 dict, `quote`/`reason`은 공백 제거 후 비지 않는 문자열로 검증한다.
3. 하나라도 잘못되면 전체를 ValueError로 거부한다. 잘못된 항목만 버리거나 숫자/list를 문자열로 바꿔 성공시키지 않는다.
4. 기존 repair를 정확히 한 번 사용한다. 두 번째 응답도 잘못되면 기존 API 오류 계약으로 실패해야 하며 성공 이력을 만들지 않는다.
5. 정상 `issues=[]`, trim, 500자 제한, severity 기본 `warn`, 추가 필드 무시는 유지한다. 오류 문구에 원문/credential을 넣지 않는다.
6. 원문·checked revision/hash·정상 canon 이력 저장과 provider 선택은 바꾸지 않는다.

### B02 — 승인된 내용 선택 기준

승인 기준은 **유효한 명시 번호 보존 → 중복은 첫 유효 항목 유지 → 미지정만 빈 번호 배정 → 남은 칸 템플릿 보충**이다.

| 입력 | 제안 처리 |
| --- | --- |
| 유효한 권/회차 번호 | 먼저 해당 위치를 확보하고 내용 보존. 입력 배열 순서가 달라도 실제 번호로 sort_order 계산 |
| 같은 권 또는 회차 번호 중복 | 해당 단계에서 첫 유효 항목만 사용. 뒤의 충돌 내용을 다른 번호로 옮기거나 덮어쓰지 않음 |
| 요청 범위 밖·0·음수·bool·문자열·비정수 번호 | 명시적 잘못된 번호로 거부/제외. 미지정 번호처럼 구제하지 않음 |
| 번호 누락/null | 유효한 명시 번호를 먼저 확보한 후, 입력 순서대로 해당 단계의 첫 빈 번호에 배정 |
| 남은 빈 회차 | 기존 템플릿 제목과 빈 synopsis/key_event로 보충 |

- 최종 `(volume, order)`는 정확히 `1..volume_count × 1..chapters_per_volume`이며 중복이 없어야 한다.
- `sort_order = (volume - 1) * chapters_per_volume + order - 1`을 사용하고 기존 `_safe_sort_order` 경계를 유지한다.
- 새 provider 재시도나 전면 fallback을 추가하지 않는다. 기존 정상/repair/fallback·use_ai=false·주인공 이름/목차 anchor 흐름은 유지한다.
- 적용은 **새 bootstrap 결과 정규화**에 한정한다. 기존 작품/원고/회차 데이터의 번호나 내용을 바꾸는 migration은 하지 않는다.
- raw 권 title index/VolumeNote 불일치는 이후 합성 TestClient/TEMP DB에서 재현했다. `test_bootstrap_duplicate_volume_metadata_matches_first_winner`에서 Note는 FIRST인데 응답과 Project.memo 목차는 LATER였다(`b02-red-corrected.txt`, `/tmp/jippeel-b01-b02-resumed-lib0k2a8`).
- 부모는 재현 로그와 `generate_structure`/`persist_structure`를 확인해 승인된 첫 유효 항목 선택을 목차·생성 anchor의 title index·VolumeNote에도 동일하게 적용하는 최소 정합성 보정을 승인했다. 미지정/null 배정과 잘못된 번호 제외를 같은 선택기로 공유한다.
- 순수 템플릿으로만 보충한 권에는 새 VolumeNote를 만들지 않는다. 선택된 원래 권의 title/overview/emotion_curve/climax_note는 기존 coercion·길이 제한을 유지한다. 기존 저장 작품 업데이트·새 재시도·스키마 변경은 금지하며 이 경계의 API/DB/anchor 회귀를 추가한다.

이 정책은 생성 내용 일부를 선택/제외하므로 별도 확인을 거쳤으며 위 사용자 승인으로 확정했다.
대안은 중복 번호가 나오면 전체 기획을 실패 처리하는 것이지만, 기존 부분 보충 동작을 더 크게 바꾸므로 기본안으로 택하지 않았다.

## 3. 구현·검증 task_list

1. **B01 RED:** 구조 오류, 정상 0건, 정상/혼합 항목, 1회 repair 성공/실패와 호출 상한을 pytest 회귀로 고정한다.
2. **B01 GREEN:** parser의 최소 구조 검증과 repair 안내를 보정한다. 합성 TEMP DB/fake API로 오류 응답 및 성공 이력 미생성, 정상 revision/hash 보존을 검사한다.
3. **B02 RED:** 13개 재현 사례 및 누락 ID/명시 ID 충돌의 golden 입력·출력으로 승인 정책을 고정한다. 원본 입력·정상 내용 보존을 검사한다.
4. **B02 GREEN:** 권별 슬롯 배정·정렬·보충만 최소 보정한다. 기존 bootstrap API 정상/repair/fallback/name/anchor 회귀와 새 DB 저장 정합성을 확인한다.
5. **검증:** 기존 안전 runner로 관련·전체 backend 회귀, 변경 범위 coverage 80% 이상을 확인한다. 기존 `.coverage` 대신 새 TEMP 출력 사용. 실제 provider·기존 DB·credential에는 접근하지 않는다.
6. **독립 검토:** Python 코드 품질 및 외부 응답/데이터 무결성 검토. 차단 지적을 해결하고 원장·HANDOFF에 실제 완료/잔여와 근거를 갱신한다.

예상 소스 범위는 `backend/app/services/canon.py`, `bootstrap.py`이며 필요한 작은 helper 분리는 검토한다.
회귀는 기존 `test_foreshadows_canon.py`, `test_bootstrap_api.py` 및 필요한 집중 테스트로 제한한다.
UI 변경·새 의존성·새 schema/migration 파일·운영 배포·commit/stage/push는 포함하지 않는다.

## 4. 승인과 중단 조건

- 승인 범위: 위 B01 오류 계약과 B02 내용 선택 기준의 최소 보정/회귀/독립 검토. 같은 정책을 다시 승인 요청하지 않는다.
- 기존 테스트의 의도된 계약 변경은 이유와 대체 회귀를 명시하며, 실패를 숨기려고 기대값을 완화하지 않는다.
- 실행 인프라 실패: 정확한 명령·오류·ref·부분 변경을 기록하고 중단한다. 다른 agent CLI로 우회하지 않는다.
- 범위 외 발견: 별도 후보로 기록한다. 완료된 원고/context/memory P1이나 다른 M/D/G 작업을 자동 재개하지 않는다.

## 5. 증거 보존

재현 workflow `eccff8f1-dfc5-400f-b1c1-12a5475bf565`, child `f31ff0ec-57bb-4c7e-aca0-2bf528bde53a`는 완료됐다.
부모는 probe/stdout와 격리 설정을 직접 읽고 원본을 프로젝트 감사 폴더로 복사했다.
`manifest.json`은 저장된 파일 hash를 기록한다. Markdown 자동 서식이 적용된 보고서와 별도로,
`reproduction.original.md.txt`에 child 출력의 원본 바이트를 보존했다.
`probe.py.txt`는 실행 당시 코드 보존용이며 앱/테스트 파일이 아니다.
수정 승인/제품 완료 여부는 이 계획 및 작업 원장에 별도로 기록한다.

## 6. 최초 구현 시도 중단 기록 — 재개 전 역사

- 정책 승인과 별개의 도구 권한 blocker다. 사용자 “진행해 허용할게”로 공식 한정 허용 진행도 승인됐다.
- 설치 버전 2.3.4의 [한 파일 허용](../../audits/failure-contracts-2026-09-12/temp-key-policy.md)을 사용자가 직접 적용했고 부모가 실제 정책·status·No changes로 확인했다. 이 권한 blocker는 해소됐으며 에이전트가 정책을 쓰거나 apply하지 않았다.
- worker `2938109b-01cb-4979-bff9-bb53c8483bae`는 `IMPLEMENTATION_GATE: BLOCKED` 보고 후 종료했다.
- 부모 workflow `0eb4ece4-f165-4adb-95ff-da4fec6abe42`도 `emit.outputPathMapping`의 undefined 직렬화로 failed다. 저장된 보고서·receipt·부분 diff는 회수했다. 다음 스크립트에서는 선택 필드를 생략/null 정규화한다.
- 당시 신규 테스트 정적 타입 오류 2건도 미수정 상태로 종료했다. 이후 재개 결과는 아래 7절이다. 과거 helper 재현과 실제 pytest RED는 별도 증거다.

## 7. 401개 실행 당시 수용 차단 기록

- B01 RED 37F/25P→62P, B02 metadata 포함 RED 24F/8P, 결합 targeted 105P, 최종 전체 401P를 기록했다.
- bootstrap line 278/289·branch 75/92, canon line 54/62·branch 15/18이다. 단, coverage 데이터 파일 목적지는 격리되지 않았다.
- 순수 Windows stdlib sentinel로 WSL 셸 변수 미전달을 확인했다. DB는 runner 내부 TEMP 설정으로 격리됐지만 기존 `.coverage`가 변경됐고 dummy-key 변수는 미전달됐다.
- `get_cipher`의 keyring 우선 경로와 지역 fixture만 있는 테스트 구조 때문에 실제 키 저장소 접근 가능성을 배제할 수 없다. 실제 키 내용·상태는 조사하지 않는다.
- 당시 worker와 workflow는 BLOCKED 결과를 보존하고 종료했다. 독립 검토는 미착수였다. 후속 승인과 재개 범위는 아래 8절이며 제품 암호화 동작·실제 키 저장소·운영 DB는 변경하지 않는다.

## 8. B04 테스트 격리 보강 — 2026-09-12 승인

사용자 “진행해”는 현재 재생성된 `.coverage`를 유지하는 예외와 테스트 격리 보강 후 재검증을 승인한다. 부모가 재확인한 새 보존 기준은 SHA-256 `a8dbb468171bf47a125460523e569bf205e9dc0784a018301adb9598a3f58624`다. 옛 d6ad… 원본은 복원하지 못했으며 이를 당시 보존 PASS로 바꾸지 않는다.

- **수정 범위:** `.eval_tmp/run_backend_pytest.py`, `backend/tests/conftest.py`, 필요한 작은 테스트 전용 격리 helper와 회귀. 기존 crypto 테스트의 실제 Fernet/fallback 의미·실패 assertions를 유지한다. 새 의존성은 추가하지 않는다.
- **동결 범위:** `backend/app/`의 B01/B02 구현 및 제품 crypto, frontend, schema/migration, 실제 keyring/기본 키 파일, 보안 정책, index/HEAD와 기존 dirty 자료. 제품 결함이 새로 발견되면 부모에게 보고한다.
- **시작 순서:** 소스에 근거한 읽기 전용 보안 사전검토 → 단일 writer의 테스트 전용 보강 → 안전한 native 검증 → fresh 코드·격리/무결성 독립 검토. 부모가 최종 수용한다.
- **초기 경계:** Windows 프로세스 내부의 fresh TEMP 경로와 환경을 앱/pytest/coverage import 전에 stdlib로 확인한다. WSL 셸 할당만 믿지 않는다. per-process WSLENV 또는 명시적 Windows 내부 설정을 사용하며 누락·잘못된 경로는 먼저 실패시킨다.
- **credential 경계:** 앱 import 전 테스트 프로세스 전체에 fake keyring/차단을 설치하고 fallback도 테스트 소유 TEMP로 제한한다. 지역 fixture나 키 파일 설정 하나만으로 격리했다고 간주하지 않는다. 실제 키 저장소 조회로 안전성을 검사하지 않는다.
- **회귀 경계:** 격리 실패를 합성 입력·가짜 저장소의 negative test로 먼저 재현한다. 격리 없는 옛 전체 suite를 다시 실행하여 RED를 만들지 않는다. 환경·credential guard를 먼저 증명한 후 targeted/전체 backend와 module별 line/branch coverage≥80%를 새 TEMP에 기록한다. 새 helper도 가능한 범위에서 직접 회귀·coverage를 확인한다.
- **보존 증거:** 현재 coverage와 protected source의 전/후 hash, 범위 한정 baseline-relative diff, 실제 명령·exit·sentinel·guard·로그를 남긴다. 보호 정책 경로를 복사/쓰기 명령과 묶지 않는다. guard 차단이나 실행 인프라 실패는 우회하지 않고 보고한다.
- **잔여 구분:** 과거 credential 부수 효과는 여전히 미확정이다. 새 격리 검증은 이후 실행에 대해서만 증거이며 운영 credential 복구·실제 provider·운영 DB·배포/Git 권한을 주지 않는다.

## 9. 독립 검토 후 부모 최소 보정

두 reviewer가 B01/B02 제품 계약은 유지됨을 확인했지만 Windows 민감 파일명 대소문자 검사와 기존 direct-pytest 가이드 불일치를 P1로 차단했다. 부모가 테스트 전용 범위에서 이 두 건만 보정한다.

- 합성 stdlib 회귀: 대소문자·trailing dot/space·stream 별칭의 str/bytes 이벤트가 소비자 호출 전 거부되고 latch에 남는지 확인. 제품 crypto는 변경하지 않는다.
- 지원 소스 진입점 `backend/scripts/run_backend_pytest.py`를 제공한다. 기존 `.eval_tmp/run_backend_pytest.py`는 호환 shim으로 유지하며 두 runbook의 실제 실행 명령과 과거 감사의 명령 안내를 구분한다. fail-closed는 유지한다.
- worker의 “모든 파일 쓰기 차단” 주장은 **쓰기 모드 open 보호**로 정정한다. os.rename/remove 등을 포함한 범용 OS sandbox를 새로 구현하거나 보장하지 않는다.
- 실제 수정 전/후 증거는 `/tmp/jippeel-b04-review-fixes-t4hs3psy`에 보존한다. 합성 RED→GREEN, 공식/호환 entrypoint preflight, 공식 entrypoint의 전체 suite·coverage, 보존 검사 후 같은 독립 reviewer들에게 재검토를 요청한다.
- 새 실행기는 배포/인계 소스 목록에 명시하되 stage/commit하지 않는다. 외부 metrics 비교 skip 1건과 SQLite warnings·정적 진단의 미확정 범위를 숨기지 않는다.

## 10. 최종 수용 — 2026-09-12

B01/B02 제품 계약 및 B04 보강을 **부모 수용 완료**했다. [최종 수용 보고서·프로젝트 내 증거](../../audits/failure-contracts-2026-09-12/b04-review-fixes.md), [지원 runner](../../runbooks/isolated-backend-tests.md)를 따른다.

- 새 native 격리 전체 suite: **419 passed / 기존 외부 비교 1 skipped / 70 subtests / 19 warnings; exit 0**. 위반 0, subprocess 시도 0, 실제 Fernet 의미 유지.
- bootstrap/canon/guard 각각 line·branch coverage 80% 이상. 두 독립 reviewer의 후속 검토 PASS, 검토 후 소스·coverage·index hash 불변 및 필수 증거 사본 무결성을 확인했다.
- 원장 C13 완료, 외부 metrics 비교 V04(todo #18)로 분리했다. LSP clean 0/inconclusive 5, 실제 provider·운영·지정 기기 미검증은 수용 범위 밖이다.
- 초기 401개 실행의 coverage 보존 실패·옛 d6ad… 미복구·credential 영향 미확정을 소급 해소했다고 주장하지 않는다. 사용자 승인된 a8db… 생성본을 유지했다.
- 제품 crypto·운영 DB·실제 키 저장소·보안 정책·Git은 변경하지 않았다. 완료된 기억 P1 및 다른 후속 작업은 재개하지 않는다.
