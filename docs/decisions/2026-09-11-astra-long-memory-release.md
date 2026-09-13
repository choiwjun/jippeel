# Astra 결정 기록 — 장편 기억 release 후속

- 결정일: 2026-09-11
- 자문 모델: `openai-codex/gpt-6-astra`
- 범위: coverage, 실제 provider 평가, Windows QA, 자동 요약/backfill
- 상태: **자문 기록 완료 / 실행 승인은 항목별 별도 게이트**
- 현재 provider 기준: 고정 `ChatGPT OAuth` / localhost `openai-oauth` bridge / `gpt-5.6-luna`.

## 결정 요약

| 항목 | 선택 |
| --- | --- |
| Coverage | `pytest-cov==7.1.0`, `coverage==7.16.0`를 test-only dev dependency로 추가. memory router/schema/long-memory service 각각 line coverage 80% 이상. branch coverage는 첫 baseline에서 보고만 하고 critical branch 테스트는 필수. |
| Provider 평가 | 고정 `ChatGPT OAuth`의 `gpt-5.6-luna`를 평가 대상으로 사용. bridge availability/정책/비용 확인 전에는 호출하지 않는다. 6개 real-case pilot, 평가자 2명, USD 20 hard cap, USD 16에서 신규 작업 중지. |
| Windows QA | Windows 11 x64 물리 장치 1대를 기준 장치로 지정. 전용 QA 계정, disposable SQLite, dummy credential, fake provider, Edge/NVDA, 후보 port 18080/15173/11234. 장치·계정·시간 창 확정 전 실행하지 않는다. |
| Auto-summary/backfill | 먼저 provider 없는 deterministic manifest planner만 사용한다. worker/schema/migration/provider 호출은 별도 승인 후 설계·구현한다. 외부 queue·scheduler·자동 승인·overwrite는 사용하지 않는다. |

## 1. Coverage 결정

### 계약

```text
backend/requirements-dev.txt
  -r requirements.txt
  pytest-cov==7.1.0
  coverage==7.16.0
```

초기 gate는 다음 세 모듈을 각각 80% 이상으로 본다.

- `app/routers/memories.py`
- `app/schemas.py`
- `app/services/long_memory.py`

전체 suite는 임시 SQLite runner로 수행한다. branch coverage는 JSON/HTML evidence로 수집하지만 첫 release에서 숫자 threshold로 차단하지 않는다. ownership, stale batch boundary, state transition, deletion 409, context injection 같은 critical branch는 별도 테스트로 강제한다.

검증 기록: OAuth 변경 전 임시 SQLite 전체 `292 passed` 기준선을 보존했고, OAuth 변경 후 변경 범위 `108 passed`를 확인했다. pytest-cov 재수집 결과 핵심 네 모듈은 memories router 80%, schemas 98%, long_memory 92%, summary_jobs 85%(827 statements 중 53 misses, 합산 line `93.59%`, branch 91%)다. ResourceWarning은 별도 조사 대상으로 기록하며 deprecation gate와 혼동하지 않는다.

## 2. Provider 평가 결정

### 실행 조건

다음 항목이 기록되기 전에는 실제 호출하지 않는다.

- model availability, current price, data policy 확인
- source owner가 승인한 6개 real-case
- prompt/config/revision/hash manifest freeze
- 한국 웹소설 편집자 1명과 작가 1명의 독립 평가자
- USD 20 hard cap, USD 16 신규 작업 중지 threshold
- worst-case reservation과 parallel fan-out 예산 계산
- SDK/repair/orchestration 자동 retry 비활성화
- usage/latency/error/cost evidence 저장 방식

기존 six-case manifest는 유지하되, fixed provider 계약과 비용 gate를 반영해 실행 전 다시 freeze한다.

- 1~3: single generation
- 4~5: parallel generation holdout
- 6: canon/review

평가용 요청에서는 `include_draft_memory=false`를 명시한다. backfill edge-case fixture와 paid quality pilot dataset을 혼용하지 않는다.

### PASS 기준

- 6개 hard contract 통과
- 모든 사례 author acceptance
- rubric 각 적용 축 median 3/5 이상
- 평가자 점수 차이가 2점을 초과하면 adjudication 완료
- usage 누락·비용 불명확·cap 초과 가능성이 있으면 즉시 pause

## 3. Windows QA 결정

기준 장치 제안:

- Windows 11 x64 physical machine
- dedicated local QA account
- 16 GB RAM / SSD
- 승인된 WSL2 distribution
- native Python과 WSL Node 의존성 분리
- Edge와 NVDA
- candidate ports: backend 18080, frontend 15173, fake provider 11234

실행 전 반드시 launcher의 hardcoded path를 확인하고, 기존 service/port를 종료하지 않는다. `JIPPEEL_KEY_FILE`이 keyring 사용을 우회한다고 가정하지 않는다. native test-keyring round-trip과 Fernet fallback을 분리해 증명한다.

## 4. Auto-summary/backfill 결정

### Job unique key

```text
project_id
chapter_id
source_revision
source_sha256
kind
prompt_version
provider_identity
model_snapshot
request_options_hash
```

request options는 canonical JSON으로 정규화한다. credential, timestamp, batch ID는 key에서 제외한다.

### Job 규칙

- source allowlist는 author-approved manifest로 고정한다. `Chapter.status=완료`만으로 승인으로 추정하지 않는다.
- fresh summary draft/approved summary가 있으면 기본 skip한다.
- 동일 key는 기존 job/result를 재사용한다. retired result는 재활성화하지 않는다.
- provider 호출 중 DB write transaction을 열어두지 않는다.
- 결과 memory draft와 `draft_saved` job link는 짧은 단일 transaction으로 저장한다.
- crash 후 outcome이 불명확하면 `needs_review`로 멈추고 무조건 retry하지 않는다.
- 초기 실행은 concurrency 1, batch 5 chapters, chapter 단위 checkpoint다.
- rollback은 선택 batch의 아직 draft인 결과만 승인 후 retired 처리한다.
- worker는 DB restore 전 중지하고, restore 후 lease를 무효화한 뒤 manifest를 재검증한다.

### 구현 순서

1. provider 없는 deterministic manifest planner — 완료 (`backend/app/services/summary_jobs.py`, 3 tests)
2. 임시 DB + fake provider로 duplicate/crash/stale/restore 테스트 — schema/worker 승인 후
3. 별도 schema/migration 승인
4. `summary_jobs` unique constraint와 durable lease 구현
5. 실제 provider pilot 승인
6. 운영 backfill은 별도 승인

## 승인 필요 항목

- [ ] provider availability/pricing/data policy 확인
- [ ] 6개 source ID와 source owner 확정
- [ ] 독립 평가자 2명 확정
- [ ] Windows 장치·QA 계정·test key·시간 창 확정
- [ ] `summary_jobs` schema/migration 승인
- [ ] production backup/restore owner와 retention 확정

이 결정 기록은 운영 DB, 실제 provider, keyring, Windows 장치를 조작하지 않는다.
