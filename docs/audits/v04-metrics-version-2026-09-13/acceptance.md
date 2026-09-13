# V04 수용 — 외부 im-not-ai metrics 버전 동기화 검증기

- 수용일: 2026-09-13
- 사양: [V04 사양](../../superpowers/plans/2026-09-13-v04-external-metrics-version-spec.md)
- 상태: **수용 — 실물 파일 검증 완료** (2026-09-14 실물 대조 통과)

## 수용 범위

`backend/app/services/metrics_version.py` — 외부 `metrics_v2.py`를 **실행하지 않고** AST로 파싱해 코드베이스가 주장하는 계약과 비교하는 읽기 전용 검증기.

계약(단일 출처 `expected_contract()`):

| 항목 | 기대값 | 근거 호출부 |
|------|--------|-------------|
| `compute_all_v2(text, genre)` | 동기 함수, `genre` 키워드 바인딩 가능, 필수 위치 인자 ≤2 | `quality.py` `try_metrics_v2` → `compute_all_v2(text or "", genre="essay")` |
| `CHANGE_RATE_WARN` | `0.30` 리터럴 | `humanize.WARN_RATIO` 라이브 참조 |
| `CHANGE_RATE_ABORT` | `0.50` 리터럴 | `humanize.BLOCK_RATIO` 라이브 참조 |
| `WARN <= ABORT` | 순서 관계 | 게이트 판정 안전 |

거부 조건: 함수 누락·async·이름 불일치·`genre` positional-only·3번째 이상 필수 인자·상수 누락/불일치/비-리터럴(평가 불가)·순서 파손·파싱 불가·파일 부재 — 전부 예외 없이 `MetricsVersionReport`로 반환.

## 검증 근거

- focused: `tests/test_metrics_version.py` **20 passed** — 계약 일치·각 불일치 유형·외부 코드 미실행(side-effect 페이로드)·직렬화
- 전체 회귀: **671 passed / 1 skipped** — skip은 기존 외부 metrics 미설치 분기(`test_quality_merges_metrics_v2_when_available`)로 분리 유지
- 격리: violations 0 · subprocess 0
- RED 증거: `red-log.txt` (모듈 부재 확인)
- 독립 검토: PASS_WITH_NOTES — MED 2건 수정·재검증 ([review-log.md](review-log.md))

## 실물 파일 검증 — 2026-09-14 완료

WSL에서 탐색 대상이었던 `~/.agents/`는 Linux 측이었다. 실제 설치 위치는 Windows 측
`C:\Users\wj941\.agents\im-not-ai\skills\humanize-korean\references\metrics_v2.py`
(32,130 bytes)로 확인돼 `verify_metrics_module`을 실물 경로에 실행했다.
전체 결과는 [real-file-verification.txt](real-file-verification.txt):

- `ok: true`, `found: true`, `mismatches: []`
- checked: `compute_all_v2 signature` · `CHANGE_RATE_WARN` · `CHANGE_RATE_ABORT` · `warn<=abort`

→ 외부 metrics_v2 버전 동기화는 **실물 대조로 확정**됐다.

## 비수용(명시 제외)

- 외부 스킬의 런타임 실행·네트워크 접근 — 없음(검증은 AST 읽기 전용).
- `quality.py`/`humanize.py` 동작 변경 — 없음(읽기 전용 검증기만 추가).
- 기존 metrics_v2 병합 동작의 재검증 — B03/C13 수용 범위에서 유지.
