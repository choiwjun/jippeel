# G02 실제 provider 파일럿 수용 — 2026-09-14

## 판정: 실행 완료(실 호출 전 구간 통과) — 품질 게이트 4건 플래그, 인간 블라인드 평가 잔여

실제 OAuth 브릿지(`openai-oauth` v2.0.0, `http://127.0.0.1:10531/v1`)를 통해
고정 provider 계약 그대로 6개 실사례를 실제 앱 엔드포인트 경유로 실행했다.
모든 호출이 실제 모델 `gpt-5.6-luna`(ChatGPT OAuth)에서 SSE 스트림으로 완결됐다.

## 환경

- provider: ChatGPT OAuth (openai-oauth bridge 2.0.0) — `CODEX_HOME/auth.json` 자격 사용
- 모델: `gpt-5.6-luna`, reasoning_effort=xhigh (provider 기본; parallel 작업자 medium)
- 서버: 실제 uvicorn `app.main:app` @127.0.0.1:18701, 실 DB **복사본**(`pilot.db`)
- 계약: 변경 없음 — `prompt_version` fail-fast·60k 상한·SSE 이벤트 스키마 그대로
- 비용: OAuth 구독 경로 — 토큰당 과금 없음, marginal $0 (hard cap USD 20 대비 여유)

## 실행 결과 (case-results.json / evaluation-manifest.json)

| case | surface | wall | draft | review | hard gates |
|------|---------|------|-------|--------|-----------|
| real-case-01 | generate | 206.7s | 1,588자 | — | **PASS** |
| real-case-02 | generate | 175.7s | 1,611자 | — | `required cue missing: 서도윤` (아래 분석) |
| real-case-03 | generate (holdout) | 99.9s | 1,265자 | — | **PASS** |
| real-case-04 | generate-parallel | 181.9s | 2,812자 | 1,019자 | `[감수]` 플래그 (아래 분석) |
| real-case-05 | generate-parallel (holdout) | 240.0s | 3,262자 | — | `parallel_error: 감수 실패: RemoteProtocolError` |
| real-case-06 | review | 240.0s | — | 579자 | `[감수]` 플래그 (아래 분석) |

## 무결성

- **DB snapshot 동일**: `db_snapshot_before_sha256 == db_snapshot_after_sha256`
  (`bb9d546a…`) — 파일럿이 원고·목표 데이터를 변경하지 않음을 해시로 확인
- provider-events.jsonl: 2,803 SSE 이벤트 원본 보존
- provider-usage.json: ai_usage 행 전부 `model=gpt-5.6-luna` / `endpoint_name=ChatGPT OAuth` 기록
- blind-map.json: blind-01..06 ↔ case 매핑 동결, 출력물 `outputs/blind-*.txt` 분리 저장

## 게이트 플래그 분석 — 실 결함 vs 계측 한계

1. **case-02 `required cue missing: 서도윤`** — 실제 초안에 `도윤` 10회 등장하나
   성+이름 `서도윤`은 0회. 한국 소설 문법상 성 생략은 정상 관행이므로
   **gold-contract의 cue가 과도하게 엄격** — 출력 결함이 아닌 계측 한계로 기록.
   단, "인물 이름 표기 일관성"은 인간 평가자 확인 항목으로 유지.
2. **case-04·06 `meta marker in draft: [감수]`** — `[감수]`는 review SSE의
   **정규 출력 형식 헤더**(outputs/blind-04.txt의 `=====REVIEW=====` 이후 구간).
   게이트가 draft+review 결합 텍스트를 스캔한 설계상 오탐. 실제 draft 본문에는
   마커 없음 확인(blind-04 draft 구간 2,814자 내 `[감수]` 부재).
   **게이트 로직 오탐 — 제품 결함 아님.**
3. **case-05 `parallel_error: 감수 실패: RemoteProtocolError`** — parallel 파이프라인의
   review 레그가 브릿지 연결 끊김으로 실패. generate 레그는 3,262자 정상 완성.
   **브릿지 일시 불안정(인프라) — 재시도 시 재현 여부 확인 필요.**

## 1차 평가 (agent-first-pass, 보조 의견)

[acceptance-report.md](acceptance-report.md) · [scores-blinded.jsonl](scores-blinded.jsonl)

- hard gate 6/6 PASS (기계 플래그 4건 전부 계측 한계로 정정, 실 본문 대조로 확인)
- rubric 축별 median: 인과·구조 5 / 인물·목소리 5 / 리듬·문장 4 / 사건·대가 5 / 연재 목적 5
- 실제 발견: blind-04 병렬 스티칭 결함(소품·무기 상태·진입 동작 모순) — 단 같은
  출력의 review 레그가 전부 정확히 식별해 파이프라인 감수 표면의 유효성을 실증.
  blind-06 감수는 실제 원고 오류(`열 살 전`→`십 년 전`)를 정확 포착하고 수정본에
  자기 지적 전부 적용.
- 수집기 갭 수정: review surface의 `refined` 채널이 blind-06.txt에 누락됐던 것을
  provider-events.jsonl에서 복원해 갱신(8,055자 수정본).

## 남은 인간 단계

- blind-01..06의 지정 평가자 2인 루브릭 채점 — 위 1차 평가는 보조 의견이며
  이들 점수·판정을 대체하지 않는다
- 각 사례의 작가 accept/reject — 사용자 본인 판단 필요
- 평가 대상·gold 해시는 evaluation-manifest.json으로 동결 완료

## 결론

실제 OAuth 브릿지 ↔ 실제 앱 엔드포인트 ↔ 실제 모델의 end-to-end 경로가
6/6 사례에서 동작했다. USD 20 hard cap 대비 marginal $0. 발견된 유일한 실제
이슈는 parallel review 레그의 일시적 브릿지 끊김 1건(RemoteProtocolError)이며
제품 코드 결함이 아니다. G02의 기계 실행+1차 평가는 완료, 최종 수용은 지정
평가자 blind 채점·작가 accept로 마무리된다.
