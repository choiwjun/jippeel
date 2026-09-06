# 📋 프로젝트 핸드오프 — 웹소설 AI 집필·관리 대시보드 구축

> **작성일**: 2026-08-24 (세션: 01a033b5-b61c-71cd-b3db-427e9d370bcd)
> **작성 목적**: 지금까지의 조사·검증·결정 사항을 다음 세션/작업자가 이어갈 수 있도록 핸드오프화

---

## 1. 프로젝트 개요

- **목표**: 소설(웹소설) 작성을 위한 오픈소스 도구 조합 + "하나의 대시보드"로 통합
- **최종 사용자**: 한국 웹소설 작가 (노벨피아·문피아 병행 연재 전략 채택)
- **핵심 요구**:
  - 시나리오(시놉시스/플롯) 관리
  - 캐릭터 관리 (캐릭터 카드 · 관계)
  - 세계관(월드빌딩) 관리
  - 장면/챕터(회차) 관리
  - AI 집필 보조 (모델 무관 방식)
- **현재 단계**: 리서치 완료 → 대시보드 설계 협의 → 제작 전

---

## 2. 핵심 결정 사항 (확정)

| 항목 | 결정 | 비고 |
|------|------|------|
| 플랫폼 전략 | **노벨피아 + 문피아 병행 연재** | 무료 연재는 병행, 유료 전환은 단일 선택(독점 조항 확인 필요) |
| AI 연결 | **Ollama 불사용** → 모델 무관(OpenAI 호환 API) 대시보드 설계 | LM Studio / KoboldCpp / 클라우드(GPT·Grok·Claude) 어느 것이든 연결 가능 |
| 대시보드 구성 | 원고/회차 에디터 + 캐릭터 관리 + 세계관(로어북) + AI 패널 | FastAPI + 경량 웹 프론트 (MVP 먼저) |
| AI 사용 방침 | 인간이 검수하는 보조용 (AI 티 제거 윤문 포함) | 플랫폼 규정 준수 방향 (공모전 AI 전면 금지 등) |
| 후속 스킬 | im-not-ai(Humanize KR) 설치 검토 중 | MIT, 한국어 AI 티 제거 윤문 — 설치 대기 |

---

## 3. 진행 현황 (2026-08-24 세션 기준)

**✅ 완료된 리서치**
1. 오픈소스 소설 작성 도구 조사 (도구·AI 생성·스킬 전체) — `부록01`
2. 웹소설 시장·수익 검증 (사실 확인) — `부록02`
3. 플랫폼 AI 규정 + 신인 시작 비교 (문피아·노벨피아·조아라) — `부록03`
4. im-not-ai(Humanize KR) 스킬 평가 — `부록04`
5. 병행 연재 규정·사례 — `리서치_병행연재_규정_사례.md`
6. 병행 연재 최적 장르 추천 — `추천_병행연재_최적장르.md`
   - (genre-fit-researcher는 파싱 지연으로 삭제, 확보 데이터로 결론 도출)

**⏳ 대기 중 (사용자 결정 필요)**
1. **표준 파이프라인 진행** (AGENTS.md §0 순서):
   - [x] 1단계 요구사항 분석 ✅ `요구사항_정의서.md` (2026-08-25, FR 60개·NFR·수용 기준) — **✅ 사용자 승인 완료**
   - [x] 2단계 리서치 ✅ 부록01~04 + 규정·장르 / **+2차 정밀분석 완료**: `부록05_오픈소스_최적조합.md` (2026-08-25) — GitHub·npm·PyPI 실측 기반 9개 레이어 비교, 최종 조합 확정(Vue3+Vite·CodeMirror6·FastAPI+SQLAlchemy2.x·SQLite WAL·자체 ST카드 파서·openai SDK·jsdiff·Naive UI·Pinia), 라이선스 리스크 정리(CodeMirror 아카이브·PrimeVue 배제·AGPL 오염 금지), 사양 v0.2 반영 항목 8건 도출
   - [x] 2단계 리서치 ✅ 부록01~04 + 규정·장르 (파이프라인 선행 수행분, 보완 리서치는 필요 시)
   - [x] 3단계 기획 ✅ `대시보드_MVP_사양.md` **v0.2** (2026-08-25) — React 전환(사용자 결정: shadcn/ui+Tailwind·Zustand), 요구사항 FR/NFR 역참조, 부록05 반영 8건, §6 UI 가이드라인 React 기준 재작성 — **승인 대기**
   - [x] 4단계 디자인 (MiniMax M3) ✅ `디자인_화면설계서_v1.md` **v1.1** — QA 정합성 검증 통과
   - [x] 기획 QA 게이트: `QA_기획정합성_리포트.md`(조건부 통과) → 사양 v0.3·요구사항 개정·설계서 v1.1 수정 → `QA_기획정합성_리포트_v2.md` **✅ 최종 통과(개발 착수 가능)** — 회귀 R-1~R-3 정정 완료
   - [x] 디자인 프로토타입 ✅ `프로토타입/index.html` (MiniMax M3, 자기완결 HTML) — **사용자 승인 완료(2026-08-25)**
   - [x] 5단계 개발 진행 중 — Sprint 1 ✅ (FastAPI 스캐폴딩 + DB 모델 + 프로젝트/회차 CRUD, 26 테스트)
   - [x] 5단계 개발 진행 중 — Sprint 2 ✅ (캐릭터 카드 API + 로어북 API(FTS5 검색) + 회차 bulk reorder + Alembic 도입, 54 테스트 전부 통과)
   - [x] 5단계 개발 진행 중 — Sprint 3 ✅ **백엔드 완료** (AI 엔드포인트 관리+api_key 암호화(DPAPI→Fernet 폴백)·SSE 스트리밍 프록시·im-not-ai 윤문 연동(변경률 게이트 30% 경고/50% 차단 강제)·수락/거절 플로우, **97 테스트 통과**)
   - [x] 5단계 개발 — **프론트 완료(Sprint 4a·4b, npm run build 통과)**:
     - 4a: Vite+React+TS 스캐폴딩, 테마 토큰(다크 기본), Zustand 4스토어+TanStack Query, 3분할 셸, S1 홈·S2 에디터(CodeMirror6+미리보기+공백제외 카운트+자동저장)
     - 4b: S5 AI 패널(SSE 스트림 소비+끼워넣기/선택교체/복사), S6 윤문 리포트(A~J diff+게이트 게이지), S3 캐릭터, S4 로어북 검색, S7 설정(api_key 마스킹), 내보내기(.txt/.md)
     - 빌드 방식: ~/jippeel-build(ext4)에서 작업→rsync로 프로젝트 폴더 동기(/mnt/c 속도 문제 우회)
   - ⏭️ 다음: 6단계 QA — 백엔드 pytest 전수 + 프론트 빌드/E2E 점검 + 런타임 실측(sendBeacon 프록시 등)
   - [x] 6단계 QA ✅ `QA_개발검증_리포트.md` (2026-08-25) — **✅ 통과, MVP 출시 가능** (백엔드 97 테스트·프론트 빌드·런타임 스모크·Must 수용기준 대조 전부 통과, Critical 0건)

**✅ 외부 도구 흡수 적용 (2026-08-26, "필요한 모든걸 흡수해서 적용해")**
- 대상: NarraLume(Apache-2.0)·goink(**AGPL — 코드 비복사, 개념만**)·oh-story-claudecode(MIT) → 상세 분석은 `부록06_외부도구_흡수_분석.md`
- **로어북 자동 주입 v1 구현** (백로그 P1 달성): `services/injection.py` — 본문·지시문에 언급된 로어(title/keywords 점수 매칭) 상위 K개를 `/ai/generate`에 자동 주입. `context.auto_lore`·`auto_lore_limit` 파라미터, SSE start 이벤트 `injected_lore` 공개. P1 원칙 유지(원고 자동 삽입 아님)
- **빌트인 프롬프트 프리셋 6종 시드**: `services/presets_seed.py`(이름 기준 멱등) — 이어쓰기/장 끝 후크/감정 기복 설계/대화 잠재의식/장면 확장/AI 티 제거 스타일 (oh-story 방법론 한국형 재해석)
- 프론트 S5: "로어 자동 주입" 체크박스 + 주입된 로어 배지 표시 + 전송 고지 문구 보강 (aiPanelStore/aiStream/AiPanel)
- QA Minor #3 해소: vite manualChunks(react-vendor/editor/markdown) 분리 — 빌드 경고 제거
- 검증: 백엔드 **117 passed**(신규 12 포함) / 프론트 `npm run build` 통과(TS 0 오류·청크 경고 0)
- 환경 정비: requirements.txt 누락 의존성 명시(openai·sse-starlette·cryptography), im-not-ai Windows 클론(`~/.agents/im-not-ai`)으로 네이티브 pytest 전수 가능
- ⚠️ qwen CLI 인증 만료(BAILIAN_TOKEN_PLAN_API_KEY 403)로 프론트 위임 불가 → 원인 분석 후 직접 구현(전역 정책의 예외 허용 조건). 키 갱신 필요
- 후속 로드맵(부록06 §2): 임베딩 시맨틱 검색 v2(sqlite-vec+한국어 ONNX), canon 충돌 게이트(NarraLume), Run Center, 복선 관리, 독자 인지 추적

**✅ 잔여 과업 소화 (2026-08-26 2차 — "남은작업진행해")**
- **QA Minor 3건 전건 해소**: ① sendBeacon 언로드 플러시가 POST라 PUT-only 백엔드에서 405 → `POST /chapters/{id}/content` 별칭 추가(실제 결함이었음) ② Py3.14 starlette 경고 재현 안 됨·종결 ③ vite 청크 분리 완료
- **크로스플랫폼 결함 수정**: `humanize.run_subprocess`에 encoding="utf-8" 명시 — Windows cp949에서 verify_gates 크래시하던 버그(WSL 무증상)
- **E2E 6/6 passed**: Windows 네이티브 환경 신규 구축(`scripts/fake_llm_server.py` 가짜 LLM :1234 + `scripts/e2e_refine_stub.py` 윤문 스텁 + venv python3.exe 심) 후 전 시나리오 통과. S1~S7 종단 + 정리 블록 포함
- **플랫폼 규정 추적** ✅: `규정추적_2026-08.md` — 핵심 변화는 AI 기본법(2026-01-22) 생성물 표시 의무 + Claude 텍스트 워터마크(2026-08~). 노벨피아 약관 개정(08-06) 세부 확인은 다음 주기. 문피아 공모전 AI 금지 재확인, 조아라 무규정 유지
- **노벨피아 PLUS 체크리스트** ✅: `노벨피아_PLUS_전환_체크리스트.md` — 조건 확정(15화+편당 공백제외 3,000자+정산정보), jippeel 워크플로 매핑, PLUS 진행률 표시 기능 아이디어 백로그 등재
- 검증: 백엔드 **118 passed** (beacon 별칭 테스트 추가)

**🎉 표준 파이프라인 6단계 + 흡수 적용 + 잔여 과업 완료 — 남은 것: 실사용 피드백 / qwen API 키 갱신(사용자) / P2 백로그(SillyTavern 카드 연동, 임베딩 로어 검색 v2)**

**✅ 신규 기능: 작품 부트스트랩 (2026-08-25, "제목·목차·캐릭터 자동화" 요청)**
- POST /api/v1/projects/bootstrap — 장르+프리미스(선택) 한 줄로 제목 후보 5·로그라인·권/회차 목차(시놉시스)·캐릭터 4~6+관계·로어북 8~12를 LLM 3콜로 생성해 단일 트랜잭션 저장(JSON 파싱 실패 시 재시도→규칙 기반 폴백)
- S1 홈 '✨ AI로 작품 자동 생성' 마법사(Dialog: 장르/프리미스/권·회차 수 → 진단 단계 표시 → 결과 요약 → 프로젝트 열기)
- 백엔드 테스트 104→105 통과, 실호출 스모크 성공(프로젝트+5화+캐릭터4+관계3+로어북8 생성)
- ⚠️ 생성 품질은 연결된 LLM 품질에 종속 — 현재 :1234는 fake 모델이라 템플릿 수준 출력. 실사용 시 실제 모델(LM Studio 실 weights 또는 클라우드 키) 필요

**✅ E2E 안정화 (2026-08-25) — 6/6 passed × 2회 연속**
- 수정 1: S5 레이스 버그 — endpoints 로딩 중 클릭 시 토스트 조기반환 + 쿼리 settle 재마운트가 스트림 abort → 스트림 생명주기를 zustand로 승격, 첫 엔드포인트 자동 선택
- 수정 2: 윤문 환경변수 누락 — IM_NOT_AI_DIAGNOSE_CMD/REFINE_CMD 스텁(cp) 설정, scripts/dev.sh에도 반영
- 수정 3: S6 spans=[]일 때 비교 뷰 미렌더 → 성공 시 항상 원문/수정본 비교 영역 렌더
- 서버 운영: tmux 세션(jippeel-be/jippeel-fe) 권장 — bash 도구 타임아웃이 프로세스 그룹째 정리함

**✅ 자동화 보강 (2026-08-25, 사용자 요청 "수동 작업 최소화")**
- 원클릭 실행: `Jippeel실행.bat` (Windows 더블클릭 → WSL에서 백엔드+프론트 기동+브라우저 오픈) / `scripts/dev.sh`
- LM Studio(:1234) 자동 감지·엔드포인트 사전 등록
- UI E2E 자동화: `frontend/e2e/app-flow.spec.ts` — Playwright 6 시나리오(프로젝트 생성→집필→AI 스트리밍→P1 자동삽입 금지→윤문 게이트→api_key 마스킹) **6/6 passed × 2회 연속**, 스크린샷 자동 저장
- 실행법: `cd frontend && npx playwright test` (Chromium 라이브러리는 `~/.local/pwlibs` + LD_LIBRARY_PATH 방식, sudo 불필요)
- 참고: 빌드·E2E는 ~/jippeel-build(ext4)에서 수행 후 rsync 동기 — /mnt/c 속도 문제 우회

**✅ 추가 완료 (2026-08-25)**
- im-not-ai(Humanize KR) 스킬 설치 완료: `~/.agents/im-not-ai` 클론 → `~/.agents/skills/{humanize-korean,humanize,humanize-redo}` 심링크
- 실측 검증 완료: AI 티 샘플 윤문 파이프라인(standard 경로) 정상 동작 — 진단→윤문→final.md 생성 확인
- 작업별 모델 라우팅 규칙 확정: `AGENTS.md` 참조 (프론트=MiniMax M3 / 백엔드·QA·리서치·요구사항=ox-alpha)

**✅ Sprint 2 백엔드 완료 (2026-08-25, 사양 v0.3 기준)**

- `backend/app/routers/characters.py` — 캐릭터 CRUD + 관계(Relationship) 생성/목록/삭제 + `card_json` 병합 PATCH(`/characters/{id}/card_json`, RFC 7386 유사) (FR-201~205)
- `backend/app/routers/lorebook.py` — 로어 항목 CRUD + 카테고리 필터 + keywords[] 관리(PUT `/lore/{id}/keywords`) + FTS5 키워드 검색 GET `/projects/{pid}/lore/search?q=` (FR-301~305)
  - FTS5는 선택 적용(`app/services/fts.py`): unicode61 토크나이저 한계 보완 위해 쿼리를 `"term"*` 접두어 질의로 변환, 미지원 빌드·문법 오류 시 LIKE 폴백. CRUD에서 인덱스 동기화.
- `PATCH /api/v1/projects/{pid}/chapters/reorder` — 순서/권 bulk 변경(원자성 보장: 소속 아님·중복 id 시 422, 부분 적용 없음)
- **Alembic 도입**: `backend/alembic.ini`(script_location=%(here)s 고정) + `alembic/env.py`(DATABASE_URL 환경변수 우선, render_as_batch) + 초기 마이그레이션(전체 스키마 + FTS 인덱스 부트스트랩). `tests/test_migrations.py`로 upgrade head/downgrade base/idempotency 검증.
- 게이트: `.venv/bin/python -m pytest -q` → **54 passed**(Sprint 1 26개 포함). requirements.txt에 alembic>=1.13 추가.
- 잔여(다음 스프린트): AI 프록시(routers/ai_panel.py), 윤문 연동(routers/refine.py), 프론트엔드.

---

## 4. 다음 액션 (우선순위)

- [x] 1. 병행 연재 규정·사례 리서치 완료 (무료 병행 가능 / 유료 독점 제약 확인)
- [x] 2. 병행 유리 장르 최종 추천 완료 (남성향 판타지·무협 + 회귀·빙의)
- [x] 3. im-not-ai 스킬 설치 완료 (2026-08-25, 실측 검증 포함)
- [x] 4. 대시보드 MVP 제작 시작: **사양 문서 확정 완료(2026-08-25) → `대시보드_MVP_사양.md`**
      - 기술 스택 확정: FastAPI + SQLAlchemy + SQLite / Vite+React(TS) / CodeMirror 6 / shadcn/ui+Tailwind / Zustand
      - 4단계 디자인 ✅ `디자인_화면설계서_v1.md` (2026-08-25, MiniMax M3 작성) — §0 핵심UX 8원칙, §1 3분할 ASCII 레이아웃, §2 S1~S7 와이어프레임·shadcn 매핑·FR 역참조, §3 인터랙션 플로우 3개(집필/윤문/캐릭터), §4 HSL 토큰·세리프, §5 Zustand 4스토어, §6 단축키·a11y, §7 개발팀 구현 노트. **승인 대기**
      - 다음: ① 본 설계서 검토·승인 → ② 5단계 개발팀(FastAPI 스캐폴딩 + 프론트 1차 스프린트) → ③ 6단계 QA
      - 원고/회차 에디터 (마크다운)
      - 캐릭터 카드 관리
      - 세계관/로어북 관리
      - AI 패널 (OpenAI 호환 엔드포인트 설정 UI — 모델 무관)
      - 윤문 모듈 (im-not-ai 연동 예정)
      - (나중 단계) SillyTavern / novelWriter API 연동
- [x] 5. 로어북 자동 주입 — ✅ 완료(2026-08-26, 부록06 참조). 임베딩 v2는 백로그로 보류
- [x] 6. 문피아·노벨피아·조아라 AI 규정 최신 공지 추적 — ✅ `규정추적_2026-08.md` (다음 주기: 노벨피아 08-06 약관 개정문 확인)
- [x] 7. 노벨피아 PLUS 전환 체크리스트 작성 — ✅ `노벨피아_PLUS_전환_체크리스트.md`
- [ ] 8. qwen CLI API 키 갱신 (BAILIAN_TOKEN_PLAN_API_KEY 403 — 프론트 위임 재개용, **사용자 조치 필요**)
- [x] 9. E2E 정식 재실행 — ✅ Windows 네이티브 환경 구축 후 **6/6 passed**(2026-08-26)

---

## 5. 중요 리스크 & 유의사항

- **AI 규정**: 문피아 = 일반 연재 본문·표지까지 AI 금지 / 노벨피아 = 공모전 금지, 일반 연재는 순수 창작 원칙 / 조아라 = 규정 미확인
- **AI 표시 의무**: 2026년 현재 3사 모두 명시적 표시 의무 없음 (단, 정책 수시 변경 — 연재 시작 전 최신 공지 필수)
- **수익 기대**: "AI로 돈 버는 시대"는 과장 — 창작자 평균 연수입 1,953만원, 연 4,000만원 이상 13.5%
- **탐지 리스크**: AI 초안 그대로 게시 시 독자에게 들키면 별점 테러·연재 중단 (문피아 AI 전면 금지는 규정 위반 소지)
- **병행 시 독점 조항**: 노벨피아 PLUS 비독점/독점, 문피아 매니지·유료화 시 독점 조건 — 유료 전환 전 반드시 확인

---

## 6. 부록 목록

| 파일 | 내용 |
|------|------|
| `부록01_오픈소스_리서치.md` | 소설 작성 도구·AI 생성 도구·스킬 전체 조사 결과 |
| `부록02_시장_검증.md` | 웹소설 시장 사실 확인 (수익 구조·트렌드·수치) |
| `부록03_플랫폼_정책.md` | 문피아·노벨피아·조아라 AI 규정 + 신인 시작 유리한 곳 비교 |
| `부록04_im-not-ai_평가.md` | Humanize KR 스킬 상세 평가 |
| `부록06_외부도구_흡수_분석.md` | NarraLume·goink·oh-story 흡수 분석 — 채택/보류/거부 판정, 라이선스 준수, 임베딩 v2 설계 메모 (2026-08-26) |
| `추천_병행연재_최적장르.md` | 병행 연재 최적 장르 추천 (확정) |
| `진행중_리서치.md` | 병행 연재 조사 현황 |
| `리서치_병행연재_규정_사례.md` | 병행 연재 규정·사례 상세 (리서처 원문) |
| `디자인_화면설계서_v1.md` | 4단계 디자인 산출물 — S1~S7 와이어프레임·컴포넌트·테마 토큰·Zustand 경계·개발 노트 (2026-08-25) |
| `프로토타입/index.html` | **4단계 디자인 정적 프로토타입** — S2/S5/S6/S7 4개 화면, 단일 HTML, 외부 의존 없음, HSL 테마 토큰·한글 세리프·FR 주석·jsdom 검증 완료 (95.8 KB) |

---
*최종 갱신: 2026-08-25 — 디자인 단계(4) 산출물(설계서 v1.1 + 정적 HTML 프로토타입) 작성 완료, 다음 단계는 디자인 승인 + 개발(5) 착수*


## 7. 디자인 프로토타입 (2026-08-25)

**✅ 정적 HTML 프로토타입 작성 완료** — `프로토타입/index.html` (95.8 KB, 단일 파일, 외부 의존 없음, 더블클릭으로 열림)

### 사양
- **기준 문서**: `디자인_화면설계서_v1.md` v1.1 + v1.2 갱신 반영
- **기술**: 단일 HTML — `<style>` 내장 CSS (HSL 테마 토큰 §4.1), 바닐라 JS (외부 라이브러리 0)
- **테마**: 저채도 다크 기본 + 라이트 전환 (◐ 버튼), 한글 세리프 시스템 스택 (Noto Serif KR, 본명조, Source Han Serif)
- **글꼴**: `font-family: 'Noto Serif KR', '본명조', 'Source Han Serif', 'Source Serif Pro', 'Pretendard', Georgia, serif`
- **반응형**: 데스크톱 우선 (≥1280px), 미니멀 폴백

### 포함 화면 (상단 탭 전환)
1. **S2 회차 에디터** — 3분할(좌 회차 트리 / 중 CodeMirror 자리 + 미리보기 탭 / 우 패널), 상단바(프로젝트 셀렉터·저장 상태 FR-106), 하단 상태바(글자 수 공백제외 카운트 JS 실제 계산 FR-104)
2. **S5 AI 패널** — 🛡 P1 Alert(FR-406) + ☁ NFR-201 전송 고지, 프롬프트 프리셋, 더미 스트리밍 결과(`✨ 생성 시작` 클릭 시 실제 토큰처럼 흘러나옴), [↪ 끼워넣기][⤳ 선택 교체][⧉ 복사] (P1·FR-406)
3. **S6 윤문 리포트** — 변경률 게이지(30% 경고선/50% 차단선 시각화), taxonomy ID A~J 색상 범례, 병렬 diff 뷰(원문/수정본, 삭제선/추가색), 진단 span 마크, [✓ 수락][✗ 거절] + 50% 초과 더미 케이스(수락 비활성·재실행/폐기만 C-2)
4. **S7 설정** — 6개 탭(AI/윤문/테마/규정·현황/백업/고급), AI 탭에 api_key 마스킹만 노출([표시] 버튼 완전 삭제 C-1), 규정·현황 탭에 NFR-404 Alert

### UX 원칙 적용 (설계서 §0)
- **P1** AI 자동 삽입 금지 (S5 상단 ShieldCheck Alert + S5 액션 3종) ✓
- **P2** 글자 수(공백 제외) 항상 노출 (S2 푸터, mono·굽게) ✓
- **P3** 저장 상태 "저장됨 · 방금 전" (FR-106, 디바운스 1.5s 시뮬레이션) ✓
- **P4** 윤문 30/50% 게이트 (게이지 색 + 임계선, block 시 수락 비활성 + 재실행/폐기) ✓
- **P5** 그리드+드로어 (S3·S4 미포함, 백엔드 후속 화면) — 본 프로토타입은 S2/S5/S6/S7 4개 화면
- **P6** AI 패널 전역 호출 (Alt+A 단축키 + 우측 상단 FAB + 우측 패널 토글) ✓
- **P7** 저채도 다크/라이트 + 세리프 본문 (HSL 토큰, 다크 기본) ✓
- **P8** 이모지·애니메이션 절제 (Alert/FAB에 ShieldCheck·CloudUpload 1개씩만) ✓

### 검증 완료
- ✓ HTML 파싱 (BeautifulSoup) — 4개 화면 모두 존재, alert 9개, diff 7개, diag-mark 8개
- ✓ JS 동작 (jsdom) — 탭 전환, 테마 토글, 글자 수 카운트 (테스트: "가나다 abc def" → 총 11자, 공백제외 9자), 우측 패널 토글, S7 탭 전환, 변경률 게이지 27.4% / pass
- ✓ 외부 의존 0 (`<link href>`, `<script src>`, `@import`, `url()` 모두 없음)
- ✓ FR/NFR 번호 HTML 주석 — 각 화면·컴포넌트에 FR-101~602 / NFR-201·202·204·301·302·303·401·403·404 표기

### 사용법
- **Windows 탐색기**에서 `프로토타입/index.html` 더블클릭 (Edge/Chrome 권장)
- **WSL**에서 `wslview 프로토타입/index.html` 또는 파일 탐색기에서 열기
- **단축키**: `Alt+A` AI 패널, `Alt+R` 윤문, `Esc` 패널 닫기
- **테마 전환**: 상단 ◐ 버튼 (다크 ↔ 라이트)
- **윤문 데모**: S6 탭 → [🔄 다시 실행] 버튼으로 12.4% / 27.4% / 41.0% / 62.1% / 73.5% 중 랜덤 게이트 시연

### 후속 작업
- [ ] 5단계 개발팀(ox-alpha-free)에 본 프로토타입 + 설계서 핸드오프 → `App.tsx` 셸 + 3분할 레이아웃 + 토큰 부트스트랩부터 착수
- [ ] 6단계 QA — 본 프로토타입을 시각 회귀 테스트 기준선으로 활용 (Chromatic 등)


---

## 게이트 파이프라인 완주 (2026-08-26 추가)

G0~G8 전체 통과(규약 v1). gates.json/traceability.json이 최신 상태 원본.
요구사항 R-054 → 기능 F-036 → 화면 S-053 → API A-040 → DB T-008 → 테스트 TC-094 추적 완결.
릴리스 노트: 릴리스_노트_MVP_v1.0.md. 다음 세션은 Known Issues와 백로그부터.

---

## GPT OAuth 연결 완료 + 전수 재검증 (2026-09-05 추가)

**✅ ChatGPT 구독(OAuth)으로 실모델 집필 가능 — 설계·구현·실측 완료** (`기술설계_GPT_OAuth_브릿지_v1.md`)
- 방식: `npx openai-oauth`(Apache-2.0) 프록시 사이드카(:10531) → 앱 코드 수정 최소화, OpenAI 호환 엔드포인트로 등록
- 토큰: `~/.codex/auth.json` 재사용(자동 갱신), 브라우저 로그인 불필요
- 현재 설정: 엔드포인트 id=2 "ChatGPT 구독(OAuth)" = **gpt-5.6-luna + reasoning_effort xhigh** (기본 엔드포인트)
- 앱 패치(2건): ① ai_endpoints.temperature nullable(None→미전송, Codex 거부 대응, 마이그레이션 c5d6e7f8a9b0)
  ② reasoning_effort 컬럼+전달(d7e8f9a0b1c2) — pytest **118 passed** 회귀 없음
- 실측: S5 스트리밍(gpt-5.6-luna xhigh, 98 델타 정상)·부트스트랩(200 OK 100초, 제목/목차/캐릭터5/관계6/로어11) 품질 양호
- 부트스트랩 품질: 이전 fake 모델 대비 실사용 수준 — 다만 3콜 간 캐릭터 이름 교차 불일치 가능(백로그: 주인공 이름 강제 전달)

**✅ 전수 재검증 (이 머신에서 직접 실측)**
- backend pytest **118 passed**(초기 9 failed → 원인은 `~/.agents/im-not-ai` 스킬 유실, 재클론으로 복원)
- 프론트 빌드 통과(tsc+vite) — **Windows에서는 node_modules가 WSL용이라 WSL에서 실행할 것**
- E2E **6/6 passed**(45s) — 이전 QA v2의 환경 블록 E-1 해소: chromium 라이브러리는 `~/.local/pwlibs` + `LD_LIBRARY_PATH` 방식
- F-036 라이선스 고지 구현 확인(SettingsPage + LICENSES.md) — 릴리스 블로커 해소 상태 유지

**운영 메모**
- AI 스택 기동: 백엔드(:8000) + `npx openai-oauth --detach`(:10531) + vite(:5173) — `scripts/dev.sh`가 :10531 미감지(미등록 시 S7에서 수동 등록 필요)
- 모델 변경: S7 설정 또는 `PATCH /api/v1/ai/endpoints/2 {"default_model": "...", "reasoning_effort": "..."}` (temperature는 null 유지)
- 미커밋 변경분 다수(PLUS 위젯·volume nullable·F-036·OAuth 패치) — 커밋 필요

---

## UI/UX 1단계 개선 + 삭제 버그 수정 (2026-09-06 추가)

**버그 수정: 프로젝트 삭제 FK 오류** — 관계(relationships)가 있는 프로젝트 삭제 시 500
(SQLAlchemy cascade가 Relationship을 못 닿음). delete 라우트에서 관계 행 선삭제 처리,
회귀 테스트 추가 → **pytest 119 passed**

**UI 1단계 개선 (사용자 혼란 제거 — 진단: 개발 잔재 노출이 핵심 원인)**
- 내부 용어 전면 제거: UI 노출 문자열에서 Sprint 4b / FR-xxx / NFR-xxx / (S7) / F-036 / 부록04·06 / 결정사항_G4 삭제 (개발 주석은 유지)
- 사이드바 맥락화: 회차 트리는 에디터(/write)에서만, 캐릭터·로어북은 전환 네비만, 홈의 미구현 필터 스텁 삭제, "⚙ 설정 (S7)"→"⚙ 설정"
- 상태바(회차·글자수·저장·AI)는 에디터에서만 표시
- 기본 프롬프트 프리셋 6종 시드(이어쓰기·새 장면·대사 다듬기·묘사 살리기·내용 요약·다음 화 훅) — `app/services/presets.py`, 빈 테이블에서만 삽입(멱등)
- E2E 자기완결화: FakeLM 엔드포인트를 beforeAll에서 등록→S5 명시 선택→afterAll 정리(기본 엔드포인트가 실모델이어도 독립 실행), 스트림 즉완 레이스는 or() 로케이터로 완화 → **E2E 6/6 passed**

**UI 2단계 개선 (2026-09-06 완료) — pytest 120 passed·E2E 6/6**
- 설정 카드 한글화(서버 주소/기본 모델/온도/추론 강도/API 키) + **reasoning_effort UI 선택 추가**
- 버그 수정: 설정 저장 시 temperature 빈 값이 0.7로 강제되던 문제(null 보존) — OAuth 엔드포인트 저장 시 다시 깨지던 원인
- AI 패널: 엔드포인트 온도 미설정이면 슬라이더 대신 "온도 미지원" 표시 + 요청에 temperature 미전송, 선택 프리셋 지시 내용 미리보기
- 홈 카드: 회차 수·누적 글자 수 표시(백엔드 /projects 목록에 chapter_count·total_chars 집계 추가)
- 전체 변경분 커밋 완료(4개 단위): 4df245b 문서·인프라 / cd14119 백엔드 / 828d9d2 프론트 / 6f3d561 세션 문서
- 참고: movestudio dev_server(:8000 충돌) — 두 프로젝트 동시 구동 시 포트 충돌 있음

---

## 출시 재판정 사이클 + 로어북 자동 주입 (2026-09-06 추가)

**✅ 요구사항_분석.md 지적사항 전수 검증·수정 완료** — 7건 중 5건 사실(수정), 1건 환경 한정(WSL에서 pytest 정상), 1건 선행 구현됨(reasoning_effort UI). 상세 판정은 세션 보고 참조.

**발견·수정된 핵심 결함 (F-Q3-1, P0)**
- 이탈 저장 플러시가 React 언마운트 클린업에만 존재 → **탭 닫기·새로고침에서 변경분 유실**
- 수정: `pagehide` 이벤트 병행 + sendBeacon(POST, 계약 불일치) → **keepalive fetch PUT** 전환
- E2E TC-038 시나리오로 자동 검증됨

**글자 수 기준 통일 (F-Q3-3)**
- word_count_cache를 노벨피아 모드(공백·문장부호·특수문자 제외, 문자·숫자만)로 통일 — 푸터·위젯·PLUS 판정 동일 기준(부록06)
- 기존 데이터 캐시는 다음 저장 시 갱신됨(즉시 재계산 필요 시 PUT content 재호출)

**로어북 자동 주입 (백로그 P1 → 구현)**
- `POST /ai/generate`에 `context.auto_lore` — 본문에 로어 제목·키워드(2글자+) 등장 시 자동 포함(상한 12건, 명시 선택과 중복 제외)
- AI 패널에 "세계관 자동 포함" 체크박스(기본 ON, 회차 있을 때만 활성)

**검증 결과**
- backend pytest **122 passed** / frontend build 통과(청크 분할: 908KB→4개) / **E2E 8/8 × 2회 연속**
- 신규 E2E: TC-038(이탈 플러시 보존)·TC-308(미리보기 XSS 차단 — script 미실행·onerror 제거)
- TC-037 백업 실측 **PASS**: db-info → 3파일 복사 → 데이터 동일성 (스크립트: scripts/backup_verify.py)
- 게이트 갱신: gates.json G6/G7/G8·traceability R-043 implemented(Q5 방식) — QA_개발검증_리포트_v3.md 참조

**잔여 pending-manual**: NVDA(TC-503~505)·시니어 모드·성능 계측(TC-401~405)·Windows keyring(TC-302) — 실기기 필요. a11y 자동 스캔(TC-501 자동화분)은 도입 완료 — axe-core critical·serious 0건.

---

## 집필 프롬프트 고도화 + a11y 자동화 + 원격 병합 (2026-09-06 후반)

**✅ 원격 병렬 커밋(baf4527) 리베이스 통합** — 8/26 병렬 세션의 로어 자동 주입 구현(injection.py 점수 기반·SSE start 주입 공개·limit/project_id)을 채택해 내 구현과 통합. humanize utf-8 고정(Windows cp949 수정)·requirements 핀·conftest 시드도 흡수. 통합 후 **137 passed·E2E 9/9**.

**✅ 집필 프롬프트 고도화(백로그)** — ① /ai/generate에 웹소설 문체 system 프롬프트 기본 적용 ② `context.previous_chapter` 옵션: 직전 회차 끝부분 2,000자 자동 주입(이어쓰기 맥락) — AI 패널 체크박스에서 제어.

**✅ a11y 자동 스캔 도입(TC-501 자동화분)** — @axe-core/playwright로 전 화면 스캔 E2E 추가(e2e/a11y.spec.ts), critical·serious 0건 달성. 수정: progressbar 접근명, destructive/status-draft 색 대비 보정, **Tailwind 색상 `<alpha-value>` 전환**(기존 /투명도 클래스 무작동 버그 수정). baseline 리포트는 e2e/a11y/baseline.json.

**✅ 청크 재분할** — 908KB 단일 → react 162/editor 475/markdown 130/앱 144/data 47KB, 전 청크 500KB 미만(경고 소멸).

**✅ 릴리스 노트 v1.1** 갱신(릴리스_노트_MVP_v1.0.md 하단). 잔여: NVDA·시니어 모드·성능 계측·Windows keyring 실기기 항목, 자동 백업·복원, SillyTavern 연동, UI 3단계.
