# B01/B02 격리 재현 및 최소 수정 제안 — 구현 전

## 결론·범위

- **B01 재현:** JSON 문법은 맞아도 `issues` 누락·잘못된 컨테이너·항목은 모순 0건 또는 일부 결과로 성공한다. `null`/숫자는 `TypeError`로 기존 repair를 우회한다.
- **B02 재현:** 총 회차 수는 4개로 맞추지만 요청한 2권×2화 분포, 중복 없는 권/순서, 정렬 값과 회차 번호 일치를 보장하지 못한다.
- 제품 코드·기존 테스트·문서·설정·의존성 변경 **없음**. 이 보고서와 신규 TEMP 파일만 작성. 아래 정책은 **제안이며 미승인·미구현**이다. 완료된 원고/context/memory P1은 다시 열지 않았다.
- 실행 대상: 현재 dirty worktree의 `canon.parse_issues`, `canon.run_canon_check`(메모리 fake 응답), `bootstrap._coerce_outline`를 **실제 모듈 import 후 직접 호출**. AST 복제/대체 구현 아님. `persist_structure`/API/DB 저장은 **정적 확인만** 했다.

## 격리·재현 명령·원본 아티팩트

먼저 현재 `AGENTS.md` 규칙과 `.eval_tmp/run_backend_pytest.py`, `backend/tests/conftest.py`를 읽었다. 기존 runner/pytest/conftest는 실행하지 않았다. conftest가 앱 lifespan과 DB fixture를 로드하므로 직접 helper probe를 선택했다. prime-agent·다른 에이전트 CLI·설치·서비스 시작·migration·실제 provider·credential 접근 없음.

실행 명령(저장소 루트, WSL bash):

```bash
backend/.venv/Scripts/python.exe -B \
  'C:\Users\wj941\AppData\Local\Temp\jippeel-b01-b02-k6krxni5\probe.py' \
  'C:\Users\wj941\Documents\jippeel'
```

동일 스크립트 재실행 시 그 TEMP 루트 아래에 새 `execution-*` 디렉터리를 생성한다. 애플리케이션 import **전에** 새 `DATABASE_URL`, 새 dummy `JIPPEEL_KEY_FILE` 설정, `JIPPEEL_ALLOW_TEMP_CREATE_ALL` 제거, bytecode 쓰기 차단을 수행한다. DB 연결·DB/key 파일 열기·keyring import·OAuth credential 파일·socket connect/bind/DNS·자식 프로세스를 audit hook으로 차단하고 모든 파일 쓰기를 해당 execution TEMP로 제한했다. 가상 응답은 `llm.complete_chat`에 프로세스 내에서만 patch; client/DB/chapter는 `None`, 합성 `messages_context`를 전달했다. fake await가 즉시 반환하므로 coroutine을 한 번 진행시키며 이벤트 루프/실제 I/O는 만들지 않았다.

- 실제 런타임: **Windows Python 3.14.4**, `backend/.venv/Scripts/python.exe`; 종료 코드 **0**. RED는 정책 불변식 위반이지 런타임/도구 실패가 아니다.
- 결과: `guard_events=[]`, `db_exists=false`, `key_exists=false`, `app_main_imported=false`.
- TEMP 루트(Windows): `C:\Users\wj941\AppData\Local\Temp\jippeel-b01-b02-k6krxni5`
- 스크립트(WSL): `/mnt/c/Users/wj941/AppData/Local/Temp/jippeel-b01-b02-k6krxni5/probe.py`
- **전 사례 정확한 입력·출력·예외·불변식·판정·fake 호출 프롬프트 원본:** `/mnt/c/Users/wj941/AppData/Local/Temp/jippeel-b01-b02-k6krxni5/execution-gjpb_2f9/results.json`
- 명령 stdout/stderr: `/tmp/jippeel-b01-b02-nPOyVVfL/probe.stdout.txt`, `probe.stderr.txt` (stderr 빈 파일).
- 환경 준비 기록: 같은 Linux TEMP의 `windows-temp.txt`, `temp-setup.stderr.txt`.
- SHA-256: probe `36c78d3f1e40664a5449c17f41d54a695cc04b38fa3c626d03f5cdc6b163b39a`; results `3c4f3b089fc11dcee39ca95dbf23b5ed4e81b9e261fbe46b0e583c34f1d9ac6d`.

## B01 실행 증거

아래 입력은 실제 raw JSON 문자열이다. `P` = `parse_issues`, `R` = `run_canon_check`. R의 응답 큐는 각 입력 다음에 `{"issues": []}`; malformed이면 ValueError를 통해 정확히 1회 repair(총 2회 fake 호출), 정상은 1회 호출이 기대 불변식이다. R 성공 시 주입한 revision/hash 문맥 및 `fake-model`이 반환된다. 이는 **이미 만들어진 문맥 전달** 검사이며, 실제 source revision/hash 생성·DB 이력 보존을 새로 검증한 것은 아니다.

| ID | 정확한 입력 | P 현재 출력/예외 | R 현재 결과·호출수 | 기대 / 판정 |
| --- | --- | --- | --- | --- |
| C01-empty | `{"issues": []}` | `[]` | `[] / 1회` | 정상 수용 / **PASS** |
| C02-valid | `{"issues": [{"quote": " original ", "reason": " conflict ", "severity": "error"}]}` | `[{"quote": "original", "reason": "conflict", "severity": "error"}]` | `[{"quote": "original", "reason": "conflict", "severity": "error"}] / 1회` | 정상 수용 / **PASS** |
| C03-missing | `{}` | `[]` | `[] / 1회` | ValueError→repair / **RED** |
| C04-null | `{"issues": null}` | `TypeError: 'NoneType' object is not iterable` | `TypeError / 1회` | ValueError→repair / **RED** |
| C05-number | `{"issues": 7}` | `TypeError: 'int' object is not iterable` | `TypeError / 1회` | ValueError→repair / **RED** |
| C06-string | `{"issues": "oops"}` | `[]` | `[] / 1회` | ValueError→repair / **RED** |
| C07-object | `{"issues": {"quote": "q", "reason": "r"}}` | `[]` | `[] / 1회` | ValueError→repair / **RED** |
| C08-invalid-items | `{"issues": [null, 7, "bad"]}` | `[]` | `[] / 1회` | ValueError→repair / **RED** |
| C09-missing-fields | `{"issues": [{}]}` | `[]` | `[] / 1회` | ValueError→repair / **RED** |
| C10-blank-field | `{"issues": [{"quote": " ", "reason": "r"}]}` | `[]` | `[] / 1회` | ValueError→repair / **RED** |
| C11-wrong-field-types | `{"issues": [{"quote": 123, "reason": ["bad"]}]}` | `[{"quote": "123", "reason": "['bad']", "severity": "warn"}]` | `[{"quote": "123", "reason": "['bad']", "severity": "warn"}] / 1회` | ValueError→repair / **RED** |
| C12-mixed | `{"issues": [{"quote": " original ", "reason": " conflict ", "severity": "error"}, {}]}` | `[{"quote": "original", "reason": "conflict", "severity": "error"}]` | `[{"quote": "original", "reason": "conflict", "severity": "error"}] / 1회` | ValueError→repair / **RED** |
| C13-severity-compat | `{"issues": [{"quote": "q", "reason": "r", "severity": "unknown"}]}` | `[{"quote": "q", "reason": "r", "severity": "warn"}]` | `[{"quote": "q", "reason": "r", "severity": "warn"}] / 1회` | 정상 수용 / **PASS** |
| C14-broken-json | `{"issues":` | `ValueError: JSON 객체를 찾지 못했습니다` | `[] / 2회` | ValueError→repair / **PASS** |

P 14건/R 14건 중 각각 정상·호환·문법 repair 기준선 4 PASS, 계약 위반 10 RED. C12는 0건이 아니라 **잘못된 항목만 조용히 버리는 부분 성공**이다. C13은 기존의 unknown severity→`warn` 호환 정책을 유지 대상으로 표시한 것으로 결함에 포함하지 않았다.

## B02 실행 증거

모든 호출은 `_coerce_outline(data, volume_count=2, cpv=2)`이다. 입력 표기의 `V(v,[o...])`는 정확히 다음 생성식이며, JSON 실물과 모든 출력 필드(`title/synopsis/key_event` 포함)는 results.json에 있다:

```python
def V(v, orders):
    return {"volume": v, "title": f"V{v}", "chapters": [
        {"order": order, "title": f"V{v}C{i}",
         "synopsis": f"S{i}", "key_event": f"K{i}"}
        for i, order in enumerate(orders, 1)
    ]}
# 아래 목록은 {"volumes": [V(...), ...]}의 값. {} 표기는 data 자체.
```

불변식: 총 4개, 1·2권 각각 2개, `(volume,order)`가 `(1,1),(1,2),(2,1),(2,2)`로 중복 없이 완비, sort_order 0..3 고유, `sort_order=(volume-1)*2+order-1`, bool 아닌 int 번호, 입력 불변. **총 개수와 입력 불변은 전 사례 PASS**. 표의 출력은 실제 반환 순서대로 `(권, 회차번호, sort_order)`를 투영했다. 반환 배열 자체의 정렬은 필수 조건으로 가정하지 않았다(O11 PASS).

| ID | 정확한 입력 구성 | 현재 출력 투영 | 위반 불변식 / 판정 |
| --- | --- | --- | --- |
| O01-normal | `[V(1,[1, 2]), V(2,[1, 2])]` | `[(1, 1, 0.0), (1, 2, 1.0), (2, 1, 2.0), (2, 2, 3.0)]` | 없음 / **PASS** |
| O02-missing-earlier-volume | `[V(2,[1, 2])]` | `[(2, 1, 2.0), (2, 2, 3.0), (2, 1, 2.0), (2, 2, 3.0)]` | 권별 분포, 권/번호 격자, 정렬 고유·범위 / **RED** |
| O03-uneven-volumes | `[V(1,[1]), V(2,[1, 2])]` | `[(1, 1, 0.0), (2, 1, 2.0), (2, 2, 3.0), (2, 2, 3.0)]` | 권별 분포, 권/번호 격자, 정렬 고유·범위 / **RED** |
| O04-duplicate-volume | `[V(1,[1, 2]), V(1,[1, 2])]` | `[(1, 1, 0.0), (1, 2, 1.0), (1, 1, 0.0), (1, 2, 1.0)]` | 권별 분포, 권/번호 격자, 정렬 고유·범위 / **RED** |
| O05-out-of-range-volume | `[V(3,[1, 2]), V(2,[1, 2])]` | `[(3, 1, 4.0), (3, 2, 5.0), (2, 1, 2.0), (2, 2, 3.0)]` | 권별 분포, 권/번호 격자, 정렬 고유·범위 / **RED** |
| O06-duplicate-order | `[V(1,[1, 1]), V(2,[1, 2])]` | `[(1, 1, 0.0), (1, 1, 1.0), (2, 1, 2.0), (2, 2, 3.0)]` | 권/번호 격자, 번호↔정렬 일치 / **RED** |
| O07-out-of-range-order | `[V(1,[99, 2]), V(2,[1, 2])]` | `[(1, 99, 0.0), (1, 2, 1.0), (2, 1, 2.0), (2, 2, 3.0)]` | 권/번호 격자, 번호↔정렬 일치 / **RED** |
| O08-all-missing | `{}` | `[(1, 1, 0.0), (1, 2, 1.0), (2, 1, 2.0), (2, 2, 3.0)]` | 없음 / **PASS** |
| O09-short-last-volume | `[V(1,[1, 2]), V(2,[1])]` | `[(1, 1, 0.0), (1, 2, 1.0), (2, 1, 2.0), (2, 2, 3.0)]` | 없음 / **PASS** |
| O10-reversed-order | `[V(1,[2, 1]), V(2,[1, 2])]` | `[(1, 2, 0.0), (1, 1, 1.0), (2, 1, 2.0), (2, 2, 3.0)]` | 번호↔정렬 일치 / **RED** |
| O11-reversed-volumes | `[V(2,[1, 2]), V(1,[1, 2])]` | `[(2, 1, 2.0), (2, 2, 3.0), (1, 1, 0.0), (1, 2, 1.0)]` | 없음 / **PASS** |
| O12-invalid-volume-after-short | `[V(1,[1]), V(0,[1, 2])]` | `[(1, 1, 0.0), (1, 1, 0.0), (1, 2, 1.0), (2, 2, 3.0)]` | 권별 분포, 권/번호 격자, 정렬 고유·범위 / **RED** |
| O13-boolean-identifiers | `[V(True,[True, 2]), V(2,[1, 2])]` | `[(True, True, 0.0), (True, 2, 1.0), (2, 1, 2.0), (2, 2, 3.0)]` | bool 제외 정수 / **RED** |

13건: 4 PASS / 9 RED. O02는 기존 2권 2화를 둔 채 2권 1·2화를 다시 채워 **1권이 전혀 없다**. O03은 1권 부족분 대신 2권 2화를 추가한다. O08/O09는 기존 전체 개수 기반 padding이 우연히 맞는 기준선이다. O10은 번호만 뒤집혀 있는데 sort_order는 입력 위치를 따라간다. O13은 Python의 `isinstance(True, int)` 때문에 그대로 통과한 추가 타입 경계 증거다.

## 원인과 정적 영향(미실행 구분)

- **B01 — `canon.py:70–85`:** `data.get("issues", [])`가 누락을 정상 빈 배열과 동일 취급. 컨테이너 list 검증이 없어 str/dict는 순회 후 전부 skip, null/int는 TypeError. 항목 dict 여부/빈 quote·reason에서 `continue`; 숫자·목록도 `str()`로 강제 수용.
- **B01 — `canon.py:113–125`:** repair catch가 ValueError/JSONDecodeError뿐이라 잘못된 스키마의 무예외 성공과 TypeError를 다루지 못한다. **fake 실행으로 확인**했다.
- **B01 API 영향은 정적 추론:** `routers/quality.py:53–63`은 ValueError만 502로 번역하고 성공 결과를 CanonRun에 저장한다. 빈 결과 성공 이력/TypeError 미처리 경로가 가능하지만 HTTP 상태·실제 이력 생성은 이번에 실행하지 않았다.
- **B02 — `bootstrap.py:270–300`:** 권/회차 ID는 하한만 확인하며 중복·상한·bool을 검사하지 않는다. sort_order는 `order`가 아니라 권 번호+입력 위치 `pos`. 보충은 각 권의 빈 슬롯이 아니라 전체 `len(chapters)`를 기준으로 권을 재계산한다.
- **B02 저장 영향은 정적 추론:** `persist_structure`의 outline은 위 helper 결과를 그대로 Chapter.volume/sort_order에 쓴다(`530–584`). `order`는 별도 Chapter 필드로 저장하지 않으므로 주로 목차 요약 번호와 정렬이 어긋난다. 전체 raw volumes로 만든 title index는 중복 시 마지막 값, VolumeNote는 처음 값 우선이고 요청 상한 밖도 허용한다(`543–549`, `610–629`). **VolumeNote/title 상충·DB 저장 결과는 미재현**이며 자동으로 수정 범위를 넓히지 않는다.

## 가장 작은 수정 정책 — 승인 요청용 제안, 코드 변경 없음

### B01

1. `_extract_json`은 그대로 공유한다. `parse_issues`에만 구조 검증: `issues` 필수 list, 각 item은 dict, quote/reason은 trim 후 비지 않는 **문자열**. 잘못된 항목 하나라도 있으면 전체를 **ValueError**로 거절해 부분/0건 성공을 금지한다.
2. 정상 `issues=[]`는 정상 0건. 기존 trim·500자 제한, severity 누락/미지원값의 `warn` 기본 보정은 유지한다. 알 수 없는 추가 필드는 기존처럼 무시한다. quote/reason을 `str()`로 구제하는 동작만 제거한다.
3. 기존 `run_canon_check`의 1회 repair 경로와 최종 ValueError 전파를 재사용한다. repair 안내만 “JSON 문법 **또는 issues 형식** 불일치”로 명확히 한다. 광범위한 `except Exception`/TypeError 삼키기는 불필요하다.
4. build_messages·원고·checked_input_revision/hash·CanonRun 성공 저장 계약은 건드리지 않는다. malformed가 다시 나오면 실패이지 0건 성공이 아니어야 한다.

### B02

1. `_coerce_outline` 안에서 **요청한 권별 슬롯**을 먼저 정규화한 뒤 각 권의 빈 회차를 템플릿으로 채운다. 총 개수만 맞추는 현재 while 보충을 대체한다. 반환 격자는 정확히 `1..volume_count × 1..cpv`이며 sort_order는 확정된 권/회차 슬롯에서 산출한다. `_safe_sort_order`는 유지한다.
2. 충돌 정책 **제안**: 유효한 명시 ID는 보존, 같은 슬롯이 여러 번 나오면 첫 유효 항목 우선(덮어쓰기 금지); 중복·범위 밖 명시 ID는 수용하지 않는다. 누락된 ID만 해당 권/회차의 첫 빈 슬롯에 입력 순서대로 할당한다. 남은 슬롯은 기존 템플릿 제목/빈 synopsis/key_event로 보충한다. bool은 유효 번호로 간주하지 않는다. 이 정책의 데이터 선별 효과는 구현 전 승인이 필요하다.
3. 기존 정상 outline의 제목·고유명사·시놉시스·핵심 사건을 그대로 보존한다. `_call_json`/AI 호출 횟수·normal/repair/fallback 상태코드·주인공 이름 전달은 변경하지 않는다. 잘못된 outline에 새 provider 재시도를 추가하거나 전체 bootstrap을 재구현하지 않는다.
4. persist_structure에는 필요한 경우 **정규화 결과의 사용 일관성만** 검토한다. title/VolumeNote까지 ID 정책을 통일할지는 현재 정적 발견에 대한 후속 합성 재현 뒤 정한다. raw metadata의 승자 규칙을 이번 helper 증거만으로 몰래 변경하지 않는다.

## 회귀 수용 조건·검증 한계

- B01: C03–C12가 모두 ValueError로 reject되어 fake 2회째 정상 응답으로 회복; 재시도도 malformed이면 2회로 끝나고 실패. C01/C02/C13은 한 번에 성공, C14 기존 문법 repair 유지. 500자 clipping, severity 기본값, 추가 필드 무시도 보강한다.
- B02: O01–O13의 합의된 정규화 결과를 golden 입력/출력으로 고정. 모든 격자/개수/정렬 불변식 만족, 정상 제목·synopsis/key_event 및 후속 name/outline anchor는 그대로 보존. 충돌 항목의 버림/선택 정책도 명시적으로 assert한다.
- 이후 승인된 TEMP DB/fake API 회귀에서 기존 `test_foreshadows_canon.py`의 정상 검사·checked_context revision/hash·원문 변경 중 이력 보존과 `test_bootstrap_api.py`의 정상 2권×3화·기본 1권×10화·JSON repair·502 fallback·use_ai=false·주인공 이름/목차 anchor 전달을 실행해야 한다. malformed canon이 성공 이력으로 저장되지 않는 것과 실제 Chapter/VolumeNote 수·정렬은 그 단계에서 검증한다.
- **이번에는 pytest/API/E2E/full-suite/실제 모델/DB 저장/coverage 측정 미실시.** 80% coverage나 실서비스 수용을 주장하지 않는다. 기존 정상/repair/fallback/name 테스트는 읽었을 뿐 통과했다고 재선언하지 않는다. 순수 helper와 fake coroutine 결과만 재현 증거다.

## Git·소스 불변 증거

저장소 `/mnt/c/Users/wj941/Documents/jippeel`, 전후 ref `refs/heads/main`, HEAD `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`(기대값 일치).

실행 전/후 스냅샷은 `/tmp/jippeel-b01-b02-nPOyVVfL/`의 다음 쌍이며 **모두 cmp 동일**:

- `head.before.txt` ↔ `head.after.txt`, `ref.before.txt` ↔ `ref.after.txt`
- `status.before.txt` ↔ `status.after.txt` (`git --no-optional-locks status --porcelain=v1 -uall`, 각 1,812행; 기존 dirty/미추적 목록 보존)
- `worktree-diff.before.sha256` ↔ `worktree-diff.after.sha256`: `a2acfc61d03bfddd0e8eb31f0120d4d5f5dbf0a4e1347c3f08ea908ef7ded744`
- `index-diff.before.sha256` ↔ `index-diff.after.sha256`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (staged diff 없음)
- `index.before.sha256` ↔ `index.after.sha256`: `bf9b6260efa6613d5136561a7b53fa1f42c55f3b7af2d49748eb4ae341044e00`
- `sources.before.sha256` ↔ `sources.after.sha256`: 선정한 15개 파일 전부 동일. 목록/전체 해시는 해당 파일에 보존.

주요 파일 SHA-256(전후 동일):

| 파일 | SHA-256 |
| --- | --- |
| `AGENTS.md` | `c4578e35df11c7081e1cfd89d7d7eb8343a1795919ecf39fd4da25549a2de045` |
| `.eval_tmp/run_backend_pytest.py` | `34a56c6337311e0792b24b567242cc9d58ee78c846438a0e4e09f0c583349470` |
| `backend/tests/conftest.py` | `94baa88b91934f040a31cf313842362af745b5c746e0bc4df33838532ca3bc3f` |
| `backend/app/services/canon.py` | `52d46194c071d0efa6b319eb34d8140c76e6d18bbc7ca5cf7277cce5afb5e8c5` |
| `backend/app/services/bootstrap.py` | `4cdbd4bda13112279aadc459a3d15d0d2f70fe7e0c0d00ae94faab58882f61cf` |
| `backend/tests/test_foreshadows_canon.py` | `274c2ccc24051ac2d277872a36d9a2822bbc911c2b0d84f8c4fb427813b87351` |
| `backend/tests/test_bootstrap_api.py` | `37d18fa362166b611fd9249dfa4c8c641300b724fa77b30487901d5e79e38fba` |
| `docs/handoffs/2026-09-08-remaining-work.md` | `b47cfbcac31e8d0e775bb5cfad9270c54ca64e3f0dcba65ad086df23fc8b10bd` |

## 잔여 위험·다음 단계

1. B02의 명시 ID 충돌에서 어떤 생성 내용을 남길지는 데이터 의미가 있는 정책이다. 위 “첫 유효 슬롯 우선”은 제안이며 구현 승인으로 간주하지 않는다. 정상/유효 ID의 이름·내용을 바꾸지 않는다는 경계가 우선이다.
2. TEMP 아티팩트는 정리될 수 있다. 부모 세션이 검토 후 승인 보고서와 필요 증거를 프로젝트에 별도로 보관해야 한다. 기존 `.eval_tmp`/`.coverage`는 재사용·정리하지 않았다.
3. 권장 다음 단계: **본 재현과 B01/B02 좁은 정책 승인 → 기존 dirty 보존하에 최소 수정+RED/GREEN 회귀 → 독립 검토**. 지금 수행한 것은 재현/제안까지다.
