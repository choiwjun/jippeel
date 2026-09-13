# 릴리스 노트 — jippeel 웹소설 AI 집필 대시보드

> 이 파일의 v1.0/v1.1 기록은 historical release다. 현재 구현·검증 기준은 아래 v1.2와
> `기술설계_GPT_OAuth_브릿지_v1.md`, `HANDOFF.md`를 우선한다.

## v1.2 — 고정 GPT OAuth provider 전환 (2026-09-11, 미릴리스)

- 집필·감수·병렬 집필·부트스트랩·canon·복선 제안이 고정 `ChatGPT OAuth` provider를 사용한다.
- 기본 transport는 `http://127.0.0.1:10531/v1`, 모델은 `gpt-5.6-luna`, 기본 reasoning은 `xhigh`다.
- S5/S7에서 사용자 endpoint, base URL, API key, 모델 선택·관리 UI를 제거했다. 모델은 고정 표시만 하며 선택되지 않는다.
- `GenerateParams.temperature`는 현재 API 계약에서 제거되어, 이전 payload에 남아 있어도 provider 요청으로 전달되지 않는다.
- OAuth token은 `openai-oauth` 브릿지가 관리하며 Jippeel DB·프론트·로그에 저장하지 않는다.
- 기존 `ai_endpoints` 테이블과 hidden compatibility route는 운영 migration 전 보존한다.
- fake bridge 회귀와 `cd frontend && npm run build`는 통과했다. 실제 provider·비용·운영 DB·Windows
  실기기 QA는 수행하지 않았으며 수용 전 gate로 남아 있다.

---

## Historical release note — MVP v1.0 (2026-08-26)

- **게이트**: 당시 G0~G8 전체 통과 기록 (현재 수용 판정이 아님)
- **품질 증거**: 당시 backend pytest 118 passed / frontend build 통과 기록

## 포함 기능

M1 에디터(마크다운·자동저장·글자수 3종 카운트) / M2 캐릭터 / M3 로어북(FTS5 검색) /
M4 AI 패널(모델 무관 OpenAI 호환, SSE 스트리밍) / M5 윤문(im-not-ai 연동, 변경률 게이트 30/50%) /
S7 설정(api_key DPAPI+Fernet 암호화, 라이선스 고지)

## Known Issues / 보류

1. UI e2e·a11y 자동 스캔: chromium 시스템 라이브러리 부재로 미실행(Infra팀 install-deps 후 재실행 필요)
2. 실기기 항목 보류: Windows keyring(DPAPI) 실측(TC-302), NVDA 스크린리더(TC-503~505), 노벨피아 글자수 실측(C8 — 현재 추정식 \p{L}\p{N} 적용)
3. 백로그: F-011 카드 JSON 편집, F-016 참조 회차, F-030 임계값 UI, F-034 자동 백업
4. 경미: TC-110 응답 스키마(has_api_key) 플랜과 상이

## 라이선스 준수

LICENSES.md 참조 — im-not-ai(MIT) 고지 포함, 19개 패키지 그룹 실측 확인.

---

# Historical release note v1.1 (2026-09-06)

- **품질 증거**: backend pytest **137 passed** / frontend build 통과(전 청크 500KB 미만) / **E2E 9/9 × 연속 통과**(a11y axe-core 스캔 신규 포함) / TC-037 백업 실측 PASS (QA_개발검증_리포트_v3.md)

## 신규

1. **GPT OAuth 연결 기록** — openai-oauth 프록시 사이드카 방식(기술설계_GPT_OAuth_브릿지_v1.md). 당시 endpoint 설정 UI와 provider 품질 문구는 historical 기록이며, 현재 실제 provider 품질 evidence로 사용하지 않는다.
2. **로어북 자동 주입** — 본문·지시문에 언급된 로어를 점수순(제목×3+키워드×2)으로 자동 주입, SSE start 이벤트로 주입 내역 공개. AI 패널 토글 + limit/project_id 지원
3. **집필 프롬프트 고도화** — 웹소설 문체 system 프롬프트 기본 적용, 직전 회차 끝부분(2,000자) 자동 주입 옵션
4. **기본 프롬프트 프리셋 6종 시드**(이어쓰기·새 장면·대사 다듬기·묘사 살리기·내용 요약·다음 화 훅)
5. **a11y 자동 스캔 도입** — axe-core로 전 화면 critical·serious 위반 0건 달성(색 대비 토큰 보정·progressbar 접근명·투명도 수식어 버그 수정). baseline 리포트 상시 산출
6. **백업 안내** — S7에 DB 경로·파일 단위 백업/복원 절차 표시(R-043/Q5 방식) + 실측 스크립트

## 수정된 결함

- 이탈 저장 플러시: 탭 닫기·새로고침에서 미실행되던 문제(pagehide 병행) + sendBeacon POST/PUT 계약 불일치(keepalive PUT 전환)
- 프로젝트 삭제: 캐릭터 관계 존재 시 500 오류
- 글자 수 기준: 에디터 표시(노벨피아 모드)와 서버 캐시·PLUS 판정 불일치 → 통일
- nullable volume 프론트 미반영("null권" 표시), 설정 저장 시 temperature 강제 0.7, LM Studio 자동등록 필드명 오류
- UI 전면: 개발 임무 용어·내부 번호(Sprint/FR/S7) 노출 제거, 화면별 사이드바 맥락화, 설정 한글화

## Known Issues / 보류 (갱신)

1. a11y 실기기 항목: NVDA(TC-503~505)·시니어 모드·키보드 전용 흐름 실측 — axe 자동 스캔은 통과
2. 성능 계측(TC-401~405)·Windows keyring 실측(TC-302) — 도구·실기기 필요
3. 백로그: 자동 백업·복원(현재 파일 복사 안내 방식), SillyTavern 카드 연동, UI 3단계(온보딩·단축키 안내)
4. Tailwind 색상 정의를 `<alpha-value>` 형식으로 전환 — 기존 `/투명도` 클래스가 실제로는 미작동했던 부분 수정(시각적 변화 일부 있음)
