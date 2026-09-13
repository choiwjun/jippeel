# V04 — 외부 im-not-ai metrics 버전 동기화 검증기 (얇은 단위)

- 날짜: 2026-09-13
- 원장 행: V04 "외부 im-not-ai metrics 버전 동기화 — 실제 외부 `metrics_v2.py` 상수 비교 미실시(todo #18)"
- 선행: C13/B04 수용(내부 경계 회귀 유지), 격리 가드의 `IM_NOT_AI_METRICS_DIR` → TEMP no-host-metrics 차단

## 1. 배경과 한계

코드베이스는 외부 스킬과의 **암묵적 계약** 두 곳을 주장한다:

1. `backend/app/services/quality.py` — `try_metrics_v2`가
   `{IM_NOT_AI_METRICS_DIR|~/.agents/im-not-ai/skills/humanize-korean/references}/metrics_v2.py`를 로드해
   `compute_all_v2(text, genre="essay")`를 호출하고 dict/`_asdict`/`__dict__`를 정규화한다.
2. `backend/app/services/humanize.py` — `WARN_RATIO = 0.30`·`BLOCK_RATIO = 0.50`이
   "im-not-ai `metrics_v2.py`의 `CHANGE_RATE_WARN`/`CHANGE_RATE_ABORT`와 동일"이라고 명시한다.

**환경 제약:** 검증 대상 외부 파일 `metrics_v2.py`는 이 호스트에 **설치되어 있지 않다**
(`~/.agents/skills` = computer-use·find-skills·orca-cli만 존재 — 수집된 증거 참조).
따라서 "실제 외부 파일과의 상수 비교"는 실행할 수 없고, 이번 슬라이스는
**비교 절차를 코드로 고정**해 실물 설치 시 즉시 검증 가능하게 만드는 범위다.

## 2. 목표

`backend/app/services/metrics_version.py`(신규, stdlib만):

- `verify_metrics_module(path: Path) -> MetricsVersionReport`
  - 대상 파일을 **실행하지 않고** AST 파싱만 한다(외부 코드 미실행 — 격리·보안 안전).
  - 계약 검사:
    - `compute_all_v2` 함수 존재 + 첫 두 매개변수명이 `(text, genre)` — 호출부와 시그니처 일치.
    - `CHANGE_RATE_WARN` 상수 존재·숫자 → `humanize.WARN_RATIO`와 비교.
    - `CHANGE_RATE_ABORT` 상수 존재·숫자 → `humanize.BLOCK_RATIO`와 비교.
    - `WARN <= ABORT` 순서 관계.
  - 결과: `ok`, `mismatches: list[str]`(항목별 차이 기술), `checked: list[str]`(수행 검사), `found` 파일 존재 여부.
  - 파일 부재·파싱 실패는 예외가 아니라 보고로 반환(`ok=False`, 이유 포함) — V02와 동일한 "진단 도구는 손상 입력에 크래시하지 않는다" 원칙.
- `expected_contract()` — 코드가 요구하는 계약 표면을 데이터로 노출
  (함수명·매개변수·상수명·기대값) — 문서와 코드의 단일 출처.

## 3. 비목표

- 외부 스킬 설치·다운로드·실행 — 없음.
- 외부 모듈 `exec`/`import` — AST 파싱만.
- `quality.py`·`humanize.py` 동작 변경 — 없음(읽기 전용 검증기만 추가).
- 실제 외부 파일 검증의 완료 주장 — 파일 부재를 `found=False`로 보고하며 "버전 일치 확인"으로 확대하지 않는다.
- 운영 환경에서의 자동 실행 — 수동 호출/테스트만.

## 4. 수용 기준

- [ ] `verify_metrics_module` 구현 — 위 계약 검사 4종.
- [ ] 파일 부재 → `ok=False`, `found=False`, 이유 포함.
- [ ] 파싱 불가(문법 오류·비-UTF8) → `ok=False` 보고, 미예외.
- [ ] 계약 일치 합성 파일 → `ok=True`, 모든 검사 `checked`에 기록.
- [ ] 상수 불일치·함수 누락·시그니처 불일치·WARN>ABORT → 각각 `mismatches`에 항목.
- [ ] 리터럴이 아닌 상수(계산식·외부 참조) → "평가 불가"를 mismatch로 보고(조용한 통과 없음).
- [ ] 기존 격리 가드 위반 0 — 읽기 대상은 owned TEMP만.
- [ ] 기존 `test_quality_b03_reproduction.py` 합성 모듈 테스트 무손상.

## 5. 검증

- `backend/scripts/run_backend_pytest.py tests/test_metrics_version.py` — 집중.
- `backend/scripts/run_backend_pytest.py` — 전체 회귀.
- 감사: `docs/audits/v04-metrics-version-2026-09-13/` — red-log·focused·full·hashes·manifest·review-log·acceptance.

## 6. 잔여(승인 게이트)

- 실물 `metrics_v2.py`가 설치된 환경에서 `verify_metrics_module(실물 경로)`를 1회 실행해
  실제 상수 동기화를 확인하는 것 — 외부 스킬 설치 자체가 별도 승인이며, 이번 슬라이스는
  검증 도구와 절차만 제공한다.
