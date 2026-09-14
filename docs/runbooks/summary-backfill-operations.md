# 자동 요약 backfill 운영 runbook (D04)

`summary_jobs` + `summary_worker` + `summary_provider`로 회차 요약을
MemoryEntry **draft**로 만드는 절차. 요약은 작가가 MemoryPage에서 승인해야
컨텍스트에 반영된다 — job이 draft를 승인으로 바꾸는 경로는 없다.

## 전제

- 브릿지 기동: `openai-oauth` 프로세스가
  `JIPPEEL_GPT_OAUTH_BASE_URL`(기본 `http://127.0.0.1:10531/v1`)에서 응답.
  확인: `curl -s -o /dev/null -w '%{http_code}' $BASE/models` → 200.
- credential은 브릿지 소유. 이 절차의 어떤 단계도 키를 읽거나 쓰지 않는다.
- 운영 DB 대상 실행은 별도 승인 게이트 — 먼저 합성 smoke로 검증한다.

## 절차

### 1. smoke(합성 DB, 실제 provider 1회)

```bash
cd backend
PYTHONPATH=. ./.venv/bin/python scripts/summary_smoke.py
```

`"job_status": "draft_saved"` + 종료 코드 0이면 통과. 출력의
`entry_body`를 눈으로 읽어 사실성을 확인한다(원문 밖 고유명사가
있으면 프롬프트 버그로 보고 중단).

### 2. 대상 회차 job 계획 (운영)

```python
from app.database import SessionLocal
from app.services.summary_worker import plan_summary_jobs
from app.services.summary_provider import SUMMARY_PROMPT_VERSION
from app.services.gpt_oauth import get_provider

with SessionLocal() as db:
    created, dup = plan_summary_jobs(
        db, project_id=PID, chapter_ids=[...],
        prompt_version=SUMMARY_PROMPT_VERSION,
        provider_identity=get_provider().name,
        model_snapshot=get_provider().default_model,
        request_options={})
```

- 동일 idempotency_key의 기존 job은 `duplicates`로 재사용 — 재계획은 안전하다.
- 계획 시점의 `source_revision`·`source_sha256`이 기록된다.

### 3. worker 실행

```python
from app.services.summary_provider import make_gpt_summary_provider
from app.services.summary_worker import run_pending_summary_jobs

with SessionLocal() as db:
    provider = make_gpt_summary_provider()   # 운영 SessionLocal 사용
    processed = run_pending_summary_jobs(db, provider, project_id=PID, limit=5)
```

- `limit`으로 비용을 통제한다 — 1 job = 1 provider 호출.
- 비용 cap 권장: 1회 실행당 5~10 jobs. 대량 backfill은 여러 번 나눠 실행.

### 4. 결과 확인

```python
for job in processed:
    print(job.id, job.status, job.error)
```

| status | 의미 | 조치 |
|---|---|---|
| `draft_saved` | MemoryEntry draft 생성됨 | MemoryPage에서 검토·승인 |
| `skipped_empty` | 회차 본문 없음 | 정상 — 다음 회차 진행 |
| `stale_source` | 계획 후 원문 변경됨 | 재계획(새 revision으로 job 재생성) |
| `provider_error` | 브릿지/모델 오류 | `retry_summary_job(db, job.id)`로 재시도 |
| `duplicate_skipped` | 동일 결과 이미 존재 | 정상 — 멱등 동작 |
| `rejected` | 회차 부재/타 작품 | 데이터 정합 확인 |

### 5. 작가 승인

요약은 `visibility=draft`의 MemoryEntry로만 생긴다. MemoryPage
(`/projects/{pid}/memory`)에서 draft → approved로 명시 승인해야 이후
컨텍스트 번들에 반영된다.

## 안전 규칙

- **절대** job 결과를 approved로 직접 UPDATE하지 않는다 — 승인은 작가만.
- worker 재실행은 언제든 안전하다 — running 잔여는 planned로 복구되고,
  중복 draft는 idempotency_key로 차단된다.
- 원문이 바뀐 job은 stale_source로 자동 종결 — 오래된 요약이 새 원고를
  덮는 일은 없다.
- provider 장애 시 running이 planned로 복구되므로 프로세스가 죽어도
  재실행으로 수습된다.
