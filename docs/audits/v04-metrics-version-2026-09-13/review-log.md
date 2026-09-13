# V04 독립 검토 기록 — 외부 metrics 버전 동기화 검증기

- 슬라이스: V04 (backend service layer only)
- 검토일: 2026-09-13
- 검토자: 독립 subagent 1건. 프론트 산출물 없음.
- 판정: **PASS_WITH_NOTES**

## 검토자 확인 요약

- AST 전용 — 대상 모듈 `exec`/`import`/`compile` 없음, side-effect 페이로드 음성 대조 테스트로 입증.
- 계약 정확성 — `quality.py:219` 호출 형태(`text` 위치 + `genre="essay"` 키워드)와 `_PARAMS` 일치, `_CONSTANTS`는 `humanize.WARN_RATIO/BLOCK_RATIO` 라이브 참조로 드리프트 안전.
- 비-리터럴 상수는 "평가 불가"로 fail-closed 보고. 격리 확인 — 읽기만, 쓰기·subprocess·network·env 없음.

## 지적 처리표

| # | 심각도 | 지적 | 처리 |
|---|--------|------|------|
| 1 | MED | `ast.parse`가 null-byte에 `ValueError`를 던진다는 주장 — 미포착 시 크래시 | **부분 반증 + 강화** — 이 인터프리터(3.14)에서 `compile("a=1\x00")`는 `SyntaxError`(기존 포착됨)를 실측 확인. 다만 `ValueError`·`RecursionError`를 except에 추가해 방어 확장 + null-byte 회귀 테스트 추가 |
| 2 | MED | 시그니처 검사 false-pass 3형태 — 3번째 필수 인자·`genre` positional-only·`async def`가 모두 `ok=True`로 통과(실제 호출은 TypeError/coroutine) | **수정** — `AsyncFunctionDef` 거부·`genre` posonly 거부·2번째 이후 필수 인자 존재 시 거부(vararg 있으면 허용). 회귀 테스트 4건 추가(거부 3 + defaulted 허용 1) |
| 3 | LOW | `test_inverted_warn_abort`가 상수 불일치 메시지의 "warn"에 오탐 — 순서 검사 미실행도 통과 | **수정** — `">"`와 "관계" 동시 포함 단정 |
| 4 | LOW | 상수 추출 edge(AnnAssign·가드·다중 타깃) 미테스트 | **수용** — 모두 fail-closed("missing"/"평가 불가") 방향, 다중 타깃은 `len(targets)==1`로 안전 스킵. if-가드 덮어쓰기 오탐은 이론적 — 실제 metrics 파일에 비현실적 |
| 5 | LOW | `_literal_number` bool 허용·음수 리터럴 `UnaryOp` 미평가 | **수용** — 둘 다 fail-closed 방향(false-pass 불가) |
| 6 | NOTE | 시그니처 검사가 런타임 계약보다 엄격(`f(text, *, genre)` 등 호출 가능 형태도 거부) | **수용** — 사양 §2가 명시한 의도적 엄격성, 드리프트 탐지기로서 사람 검토 유도 방향이 올바름 |
| 7 | NOTE | `_FUNCTION`/`_PARAMS`는 계약 정의 자체(quality.py 파싱 불가) — 호출부 변경 시 미감지 | **수용** — "단일 출처" 설계 의도와 일치, 호출부 변경은 호출부 테스트 영역 |
| 8 | NOTE | `to_dict()` 편의 부재·디렉터리 경로 오류 메시지·wordcount 선존 경고 | **부분 수정** — `to_dict()` 추가(실물 검증 시 붙여넣기용). 디렉터리 메시지·선존 경고는 수용 |

## 재검증

- focused: `tests/test_metrics_version.py` **20 passed** (15 → 신규 5 + 단정 강화)
- 전체 회귀: **671 passed / 1 skipped / violations 0**
- 증거: `backend-focused.txt`·`backend-full.txt`·`source-hashes.txt` 갱신

## 판정 근거

차단 결함 없음. MED 2건 전부 수정(1건은 부분 반증 후 방어 확장), 재검증 녹색. LOW/NOTE는 fail-closed 방향·사양 의도와 일치로 명시 수용.
