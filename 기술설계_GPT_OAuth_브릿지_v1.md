# 기술설계 — 고정 GPT OAuth 브릿지 v1

- 상태: 구현 완료(오프라인 계약 기준), 실제 provider 수용 게이트 대기
- 갱신: 2026-09-11
- 범위: Jippeel 집필·감수·부트스트랩·canon 호출의 provider 경로

## 1. 결정

Jippeel은 사용자가 입력한 AI endpoint, `base_url`, API key를 집필 경로에서 읽거나
저장하지 않는다. 모든 AI 호출은 로컬 `openai-oauth` 브릿지의 OpenAI 호환 transport를
통해 고정 provider로 보낸다.

| 항목 | 고정값 | 비고 |
| --- | --- | --- |
| provider | `ChatGPT OAuth` | 계정·OAuth credential은 브릿지 소유 |
| transport | `http://127.0.0.1:10531/v1` | localhost만 허용 |
| 모델 | `gpt-5.6-luna` | 요청 body의 모델 힌트는 무시 |
| 기본 추론 강도 | `xhigh` | 작업별 감수 강도 override는 계약 범위 내 허용 |
| temperature | 미전송 | reasoning 모델 호환성 |

`JIPPEEL_GPT_OAUTH_BASE_URL`, `JIPPEEL_GPT_MODEL`,
`JIPPEEL_GPT_REASONING_EFFORT`는 로컬 테스트·호환성 검증을 위한 환경 설정이다.
base URL은 `http://localhost`, `127.0.0.1`, `::1` 중 하나이며 `/v1`로 끝나야 한다.
원격 URL은 거부한다.

## 2. 런타임 흐름

```text
집필 요청
  -> FastAPI ContextBundle 검증
  -> 고정 GptOAuthProvider 해석
  -> localhost:10531 OpenAI 호환 호출
  -> SSE 또는 JSON 결과
```

브릿지는 OAuth 로그인, refresh token, 계정 상태, upstream 요청을 담당한다. Jippeel은
OAuth token을 읽지 않으며 `AsyncOpenAI`에 OAuth token을 API key로 전달하지 않는다.
SDK가 요구하는 로컬 transport 인증 인자는 실제 credential이 아닌 내부 placeholder다.

Jippeel은 브릿지를 자동 로그인·자동 설치·자동 provider 등록하지 않는다. `scripts/dev.sh`는
`:10531`이 열려 있는지 확인하고, 꺼져 있으면 사용자가 실행할 명령만 안내한다.

```bash
npx openai-oauth login
npx openai-oauth --detach
```

위 명령과 브릿지의 OAuth·ChatGPT 구독 호환성은 실제 provider 수용 게이트에서 별도로
확인한다. 이 저장소의 오프라인 테스트는 외부 OAuth나 유료 호출을 하지 않는다.

## 3. 코드 계약

### 백엔드

- `backend/app/services/gpt_oauth.py`
  - 고정 provider 메타데이터와 localhost URL 검증
  - 빈 모델·허용되지 않은 reasoning effort fail-fast
- `backend/app/services/llm.py`
  - OpenAI 호환 client와 stream/complete 호출만 담당
  - 새 집필 경로는 `provider.base_url`과 placeholder만 사용
- `backend/app/routers/ai_panel.py`
  - 단일·병렬 생성·감수 모두 고정 provider 사용
  - `params.model`과 감수 model 힌트는 provider 모델로 덮어씀
  - SSE `review_start`와 `parallel_start`는 `provider`/`review_provider`를 노출
- `backend/app/services/bootstrap.py`, `routers/quality.py`,
  `routers/foreshadows.py`
  - endpoint row를 조회하지 않고 provider adapter를 사용

`ai_endpoints` 테이블과 암호화 모듈은 기존 로컬 DB 보존 및 마이그레이션 호환을 위해
남겨 둔다. legacy `/ai/endpoints` CRUD·models route는 `include_in_schema=False`인
마이그레이션 호환면이며 신규 UI·신규 AI 실행 경로에서 호출하지 않는다. 운영 migration
승인 없이 테이블을 drop하지 않는다.

### 프론트엔드

- `AiPanel`은 provider·모델을 고정 표시하며 선택 endpoint, API key, server URL을
  요청하지 않는다.
- `SettingsPage`의 AI 탭은 ChatGPT OAuth 연결 안내와 프롬프트 프리셋만 제공한다.
- 결과의 자동 본문 삽입은 금지한다. 기존 끼워넣기·선택 교체·복사 가드는 유지한다.
- SSE parser는 `provider`와 `review_provider`를 읽고 endpoint 명칭을 사용하지 않는다.

## 4. 보안·실패 정책

1. OAuth credential은 Jippeel DB·로그·프론트 상태에 저장하지 않는다.
2. API key와 endpoint 입력 UI는 신규 경로에 없다.
3. localhost 검증 실패는 503으로 반환한다.
4. 브릿지 연결·인증·timeout·rate limit은 credential이나 원문을 노출하지 않는
   사용자 안내로 변환한다.
5. 원격 base URL, 임의 model redirect, 자동 login은 허용하지 않는다.
6. 브릿지 장애 시 원고를 자동 수정하거나 저장하지 않는다. 기존 초안 보존 정책과
   명시적 사용자 삽입 정책을 따른다.

## 5. 검증

### 완료된 오프라인 검증

- `backend/tests/test_gpt_oauth.py`: 기본값, localhost 경계, 모델·reasoning 검증
- 생성·감수·병렬·부트스트랩 회귀: fake `llm.make_client`로 provider URL/model 확인
- `backend` compileall 통과
- `frontend`: `npm run build` 통과
- 실제 OAuth token, 운영 DB, 유료 provider 호출은 수행하지 않음

### 수용 전 게이트

- 승인된 provider 품질 평가 사례 6건 및 독립 평가자 2명
- 비용·구독 한도와 실제 ChatGPT/Codex OAuth 호환성 확인
- 지정 Windows 장치에서 브릿지 로그인·기동·재시작 QA
- 운영 DB 백업 후 migration/backfill 별도 승인

## 6. 관련 문서

- `HANDOFF.md` — 현재 작업 상태와 승인 대기 gate
- `docs/runbooks/long-memory-governance-release.md` — 운영 전 기억 governance gate
- `docs/decisions/2026-09-11-astra-long-memory-release.md` — 자문 기록(실행 승인 아님)
- `대시보드_MVP_사양.md` — 과거 MVP 요구사항과 현재 override 표
