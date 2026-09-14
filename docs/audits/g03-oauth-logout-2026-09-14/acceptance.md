# G03 OAuth 로그아웃·credential 복구 시연 — 2026-09-14

## 판정: 수용 — 브릿지 소유 로그아웃·복구 전 주기 실증

## 환경

- bridge: `openai-oauth` v2.0.0 @127.0.0.1:10531 (detach 모드)
- credential 검색 순서(브릿지 고지): `$CODEX_HOME/auth.json` → `~/.codex/auth.json`
- 실제 사용 credential: `$CODEX_HOME/auth.json`(Orca 관리 Codex 계정 홈, mode=chatgpt)

## 시연 절차·결과 (재현 명령)

| 단계 | 명령 | 결과 |
|------|------|------|
| 1. 기준선 | `curl /v1/models` | HTTP 200 — 인증 상태 정상 |
| 2. 서비스 로그아웃 | `npx openai-oauth stop` | "OpenAI OAuth stopped." — 포트 연결 불가(HTTP 000) |
| 3. 계정 credential 제거 | `auth.json` 2개 경로 모두 이동 | 브릿지 재기동 거부: **"No auth file was found in the default search paths: …/home/auth.json, ~/.codex/auth.json. Run `npx openai-oauth login` and try again."** |
| 4. 무인증 호출 | `POST /v1/chat/completions` | 브릿지 미기동으로 호출 자체 불가 — 무인증 상태에서 어떤 요청도 provider에 도달 불가 |
| 5. credential 복구 | 백업본 `auth.json` 원위치 복원 + `--detach` | 브릿지 정상 기동, 모델 목록 정상 |
| 6. 복구 검증 | 실 chat.completions 호출 | **"복구 완료"** 응답 + usage 기록(prompt 13 / completion 7 / total 20) |

## 관찰 사실

- `openai-oauth`에는 `stop`/`login`만 있고 별도 `logout` 명령은 없다.
  클라이언트 측 로그아웃 = credential 파일 제거 + 브릿지 중지이며, 이 조합으로
  "자격 없이는 어떤 provider 호출도 불가" 상태가 실증됐다.
- 서버 측 토큰 폐기(revocation)는 이 도구가 노출하지 않는다 — 완전한 계정 로그아웃은
  auth 파일 제거 + ChatGPT 계정의 세션 관리(사용자 브라우저)로 완결된다.
- 시연에 사용한 임시 credential 사본은 검증 직후 전부 파기했다(`shred`).
  로그·문서 어디에도 토큰 값이 기록되지 않았다.
- 완전 재로그인 경로: `npx openai-oauth login` → 브라우저 ChatGPT 인가(지정 계정).

## 이전 단계 증거(동일 게이트)

- `docs/audits/g01-production-migration-2026-09-13/g03-real-crypto-path.txt` —
  실 `get_cipher()` 경로 왕복·실 Windows 키 cross-decrypt 거부·무관 키 거부
- `g03-partial-key-verify.txt` — 키 분리 확인

## 결론

브릿지 소유 로그아웃(서비스 중지 + credential 부재 거부)과 지정 계정 credential
복구(복원 → 실 호출 성공)가 실증됐다. 서버 측 세션 폐기와 완전 재로그인은
사용자 브라우저가 필요한 유일한 잔여이며, 절차는 위에 명문화했다.
