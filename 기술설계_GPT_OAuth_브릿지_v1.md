# 기술설계 — GPT OAuth 브릿지 (ChatGPT 구독으로 집필하기) v1

- 작성: 개발팀 · 일자: 2026-09-05
- 요구: API 크레딧 별도 구매 없이 ChatGPT 구독(Plus/Pro) 계정으로 S5 집필·부트스트랩 생성을 사용
- 선행 문서: `기술설계_v1.md`, `대시보드_MVP_사양.md` §2.1(모델 무관 AI 연결), `QA_개발검증_리포트_v2.md`
- 판정 근거 실측: Node v24.19.0 확인(Windows·WSL 공통), jippeel `llm.py`는 api_key 미설정 시 더미 키("sk-local") 사용 → 키 없는 로컬 프록시와 즉시 호환

---

## 1. 결론(요약)

**직접 OAuth를 앱에 구현하지 않는다.** Apache-2.0 커뮤니티 SDK `openai-oauth`(npm)의 로컬 프록시를
사이드카로 띄우고, jippeel에는 일반 OpenAI 호환 엔드포인트로 등록한다 — **앱 코드 수정 0**으로
ChatGPT 구독 기반 집필이 가능하다. 네이티브 구현은 필요성이 확인될 때 2단계로 보류한다.

| 방식 | 앱 수정 | 소요 | 리스크 | 판정 |
|---|---|---|---|---|
| A. 네이티브 OAuth+Responses API 구현 (Python) | 큼 (DB·llm.py·S7·테스트) | 수일 | 비공식 스펙 역추적·유지보수 부담 | 2단계 보류 |
| **B. openai-oauth 프록시 사이드카** | **0** (스크립트·문서만) | **1시간 내** | 프록시 의존(아래 §6) | **✅ 1단계 채택** |
| C. OpenAI 플랫폼 API 키 | 0 | 2분 | 과금(화당 수십~수천 원) | 병행 가능(폴백) |

## 2. 채택 방식(B)의 동작 원리

Codex CLI가 `chatgpt.com/backend-api/codex` 엔드포인트를 OAuth 토큰으로 호출하는 것과
동일한 토큰 체계를 재사용한다(`openai-oauth`, Apache-2.0). 프록시가 OpenAI 호환 표면을 제공하므로
jippeel은 "로컬 LM Studio"를 등록하듯 등록하면 된다.

```
[S5 AI 패널 / 부트스트랩]
   │ OpenAI chat.completions (SSE 스트리밍)
   ▼
jippeel backend :8000  ── make_client(base_url=http://127.0.0.1:10531/v1, api_key=더미)
   ▼
openai-oauth 프록시 :10531 (npx, Node)
   │  · /v1/chat/completions · /v1/responses · /v1/models · 스트리밍 지원
   │  · OAuth 토큰 저장·갱신 자동 (~/.codex/auth.json — Codex CLI와 동일 위치)
   ▼
chatgpt.com/backend-api/codex  (OAuth: auth.openai.com, client_id app_EMoamEEZ73f0CkXaXp7hrann)
```

## 3. Phase 1 — 사이드카 연결 (실행 항목)

1. **로그인(1회, 사용자 브라우저 개입)**
   `npx openai-oauth login` → 브라우저에서 ChatGPT 인증 → 콜백 `http://localhost:1455/auth/callback`
   → 토큰이 `~/.codex/auth.json`에 저장(이후 자동 갱신). Chrome/Firefox 지원.
2. **프록시 기동**: `npx openai-oauth --detach` (백그라운드) · `openai-oauth status/logs/stop` 관리.
3. **엔드포인트 등록 (S7 또는 API)** — 기존 스키마 그대로:
   ```json
   POST /api/v1/ai/endpoints
   {"name": "ChatGPT 구독(OAuth)", "base_url": "http://127.0.0.1:10531/v1",
    "api_key": null, "default_model": "<모델 목록에서 선택>"}
   ```
   `GET /ai/endpoints/{id}/models`가 프록시의 `/v1/models`를 그대로 프록시하므로
   계정 플랜별 사용 가능 모델(gpt-5.6-terra 계열 등)이 S7 모델 드롭다운에 노출된다.
4. **실행 스크립트 통합** — `scripts/dev.sh`·`Jippeel실행.bat`에 LM Studio 자동감지 패턴(:1234)을
   복제해 :10531 감지 시 엔드포인트 사전 등록. 미감지 시 안내 문구만(필수 아님).
5. **사용**: S5 집필 스트리밍·끼워넣기, 부트스트랩 3콜(JSON 생성) 모두 기존 경로 그대로 동작.
   윤문(im-not-ai)은 LLM과 무관하므로 영향 없음.

### 호환성 체크포인트 (실측 필요 항목 — 구현 전 스모크로 확인)

| 항목 | 기대 | 비고 |
|---|---|---|
| SSE 스트리밍 (S5) | 프록시가 chat.completions 스트리밍 지원 → OK 예상 | 실측 1회 |
| temperature | reasoning 모델 계열은 파라미터 거부 가능 | 400/422 발생 시 해당 엔드포인트만 temperature 미전송 옵션 추가(소규모 패치) |
| max_tokens | Responses 계열은 max_output_tokens 매핑 여부 | 실패 시 미전송(모델 기본값) |
| 부트스트랩 JSON 3콜 | complete_chat 경로 — 프록시 비스트리밍 응답 필요 | 실측. `_content_from_sse` 폴백 이미 존재 |
| 응답 지연 | 첫 토큰 수 초 — REQUEST_TIMEOUT=120s 여유 충분 | |

## 4. Phase 2 — 네이티브 내장 (보류, 트리거 시 착수)

Phase 1으로 불충분한 경우(프로세스 분리 제거, Node 의존 제거, 토큰을 앱에서 완전 관리)에만 진행.

- `AiEndpoint.auth_type` 컬럼 추가(`api_key`|`chatgpt_oauth`) + Alembic 마이그레이션
- `app/services/chatgpt_oauth.py`: PKCE 생성, 인가 URL, :1455 원샷 콜백 리스너,
  토큰 교체/갱신(auth.openai.com/oauth/token), 만료 60초 전 선제 갱신
- 토큰 저장: refresh_token을 기존 Fernet(`crypto.get_cipher`)으로 암호화해 DB 저장,
  응답·로그 노출 금지(NFR-202·TC-305/306 준수)
- `llm.py`에 Responses API 어댑터: messages→instructions/input 매핑,
  `response.output_text.delta` 파싱, temperature/max_tokens 정책 반영
- S7: "ChatGPT로 로그인" 버튼 + 계정·플랜·만료 표시 + 재로그인/로그아웃
- 테스트: 가짜 인가/토큰 서버 + 가짜 SSE(기존 test_ai_panel_api.py 패턴), PKCE·갱신 단위 테스트

## 5. 보안 검토

- OAuth 토큰은 앱 밖(`~/.codex/auth.json`)에만 존재 → jippeel DB에 신규 민감정보 0.
  앱은 더미 키만 보유하므로 기존 api_key 암호화·마스킹 체계와 충돌 없음.
- 프록시는 127.0.0.1 바인딩 기본(TC-307과 동일 방침). 네트워크 노출 금지 플래그 유지.
- 계정 자격은 본인만, 토큰 공유·풀링 금지(SDK Legal 조항 + OpenAI 이용약관).

## 6. 리스크 & 제약 (수용 전 확인 필수)

1. **비공식 경로**: openai-oauth는 커뮤니티 프로젝트로 OpenAI와 무관하며, "OpenAI가 언제든
   서비스를 변경·차단할 수 있다"를 명시. Codex 밖 재사용은 이용약관 그레이 존 →
   **계정 제재 가능성을 사용자가 감수**해야 함(프로젝트 문서에도 고지 유지).
2. **모델·한도**: Codex 지원 모델만 가능(플랜별 상이), 구독 사용량 한도(rate limit) 적용.
   대량 연재(수십 화/일)에는 부적합할 수 있음 → 대량 생성은 C(API 키) 병행 권장.
3. **의존성**: Node.js 필요(본기 확보됨), 프록시 프로세스 상시 구동.
4. **롤백**: 엔드포인트 삭제로 즉시 무영향. 기존 LM Studio/클라우드 경로와 완전 병행 가능.

## 7. 검증 계획 (Phase 1 완료 기준)

- [x] `~/.codex/auth.json` 기존 토큰 확인(만료 2026-09-15, refresh_token 보유) — **브라우저 로그인 불필요**
- [x] 프록시 기동 `npx openai-oauth --detach` → `127.0.0.1:10531` LISTEN 확인
- [x] 모델 목록: gpt-6-astra / gpt-5.6-sol·terra·luna / gpt-5.5 / gpt-5.4-mini / gpt-image-2
- [x] S7 등록: "ChatGPT 구독(OAuth)" base_url=http://127.0.0.1:10531/v1, api_key 없음
- [x] **실측 패치 1** — temperature: Codex 백엔드가 `Unsupported parameter: temperature`로 400 반환
      → ai_endpoints.temperature nullable 전환(마이그레이션 c5d6e7f8a9b0), None이면 미전송(llm/bootstrap 반영)
- [x] **실측 패치 2** — reasoning_effort: 엔드포인트별 추론 강도 지원 추가(마이그레이션 d7e8f9a0b1c2,
      Literal validation, llm·bootstrap·ai_panel 전달) — 사용자 요구 gpt-5.6-luna + xhigh 대응
- [x] 회귀: backend pytest **118 passed** (패치 후 전수 통과)
- [x] S5 스트리밍 실측: gpt-5.6-luna + xhigh → 98 델타 start→done 정상, 웹소설 문체 출력 확인
- [x] 부트스트랩 실측: 현대 판타지 프리미스 1회 → 200 OK (100초), 제목·로그라인·목차 5화·
      캐릭터 5+관계 6·로어북 11 used_ai=true 생성. 품질 양호(캐릭터별 말투·관계 라벨·로어 정합성 높음)
- [ ] HANDOFF.md 갱신 — **완료(2026-09-05)**

### 관측된 한계 (후속 백로그 후보)

- 캐릭터 이름이 호출 간 불일치 가능(목차 콜 "한도윤" vs 캐릭터 콜 "윤도현") — 3콜이
  독립 JSON 생성이라 교차 정합성은 모델 의존. 개선 여지: world 콜 프롬프트에 주인공 이름 강제 전달
- UI(S7)에 reasoning_effort 입력 필드는 미구현 — 현재는 API PATCH로 설정(이미 luna+xhigh 적용됨)
- 구독 사용량 한도·비공식 경로 리스크(§6)는 유효

## 8. 참조

- openai-oauth (Apache-2.0): https://github.com/EvanZhouDev/openai-oauth — 프록시/로그인/플래그 사양 출처
- Codex 인증 문서: https://learn.chatgpt.com/docs/auth (구독 인증 = Codex 전용 공식 지원)
- OpenAI 이용약관: https://openai.com/policies/terms-of-use/
- 대안 비교 근거: 커뮤니티 채택 사례(LangChain chatgpt_oauth 등)는 모두 "비공식" 명시
