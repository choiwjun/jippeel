# D04-2 — 실제 provider smoke + 평가 manifest 수용 기록 (2026-09-14)

## 범위

D04-1(fake worker 생명주기) 이후 잔여분: 실제 provider 어댑터의 실호출
검증, 평가 manifest, 운영 runbook. 실행 주체는 사용자 위임 하의 개발 세션.

## 실행 환경

- 브릿지: `openai-oauth` detached 프로세스, `http://127.0.0.1:10531/v1`
  (`/v1/models` 200 확인 후 실행). credential은 브릿지가 소유 — 앱·스크립트는
  localhost transport만 사용.
- DB: 합성 임시 sqlite(`/tmp/summary-smoke-*/smoke.db`) — 운영 DB 무접촉.
- 대상: 합성 프로젝트 1개 + 합성 회차 1개(약 460자 한국어 웹소설 문단).
- 비용: 단일 요약 호출 1회(소스 460자, MAX_SOURCE_CHARS 상한 내).

## 실행 경로

`backend/scripts/summary_smoke.py`:
`plan_summary_jobs` → `run_pending_summary_jobs(provider=make_gpt_summary_provider(session_factory=합성 세션))`.

## 결과 (원시 출력 발췌)

```json
{"planned": [{"id": 1, "status": "planned",
  "idempotency_key": "0433bcb5639555ed76125a5e73408a772ad3b9a4d1818dfaadc49b499592585a"}],
 "duplicates": 0}
```

```json
{
  "job_status": "draft_saved",
  "job_error": null,
  "attempt_count": 1,
  "memory_entry_id": 1,
  "entry_visibility": "draft",
  "entry_kind": "summary",
  "entry_provenance": {
    "generated_by": "summary-worker", "job_id": 1,
    "idempotency_key": "0433bcb5…6f2",
    "prompt_version": "summary-v1",
    "provider_identity": "gpt-oauth-bridge",
    "model_snapshot": "smoke",
    "request_options_hash": "f5909f06…6f2"
  },
  "entry_body": "- 카엘은 폐역 입구에서 추격자들의 발소리를 듣고 멈춘다.\n- 어둠 속 소녀 리아는 녹슨 열쇠를 가지고 있으며, 폐역을 빠져나가려면 열쇠가 필요하다고 말한다.\n- 리아는 자신도 데려가 달라고 요청하고, 카엘은 이를 받아들인다.\n- 카엘과 리아는 환기구로 들어가 도주하며, 뒤에서 폐역 문이 부서진다."
}
```

## 판정 — 평가 manifest 통과

| manifest 항목 | 기대 | 관측 |
|---|---|---|
| 생명주기 | planned→running→draft_saved | draft_saved, attempt_count=1 |
| draft 게이트 | MemoryEntry는 visibility=draft | draft ✓ (자동 승인 없음) |
| provenance | 7키 전부 기록 | 7키 전부 존재 ✓ |
| 멱등 manifest | idempotency_key 생성·영속 | sha256 키 존재 ✓ |
| 사실성 | 원문 사건만 요약, 창작 없음 | 카엘·리아·열쇠·환기구 도주 — 원문 사실과 일치, 신규 고유명사 없음 ✓ |
| 언어 | 한국어, 간결 | 한국어 불릿 4개 ✓ |
| 운영 격리 | 운영 DB 무접촉 | 합성 DB만 사용 ✓ |

## 결론

실제 provider 경로(어댑터→브릿지→worker→MemoryEntry draft)가 end-to-end로
동작한다. 남은 D04 운영 단계는 [runbook](../../runbooks/summary-backfill-operations.md)의
절차를 따르며, 실제 원고 대상 backfill은 작가 승인 후 별도 실행한다.

## 재현

```bash
cd backend && PYTHONPATH=. ./.venv/bin/python scripts/summary_smoke.py
# 종료 코드 0 = draft_saved 성공
```
