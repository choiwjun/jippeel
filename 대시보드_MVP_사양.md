# 웹소설 AI 집필 대시보드 — MVP 사양 문서

> **버전**: v0.3
> **작성일**: 2026-08-25 (v0.3 갱신)
> **근거 문서**: `HANDOFF.md`, `요구사항_정의서.md`(승인 완료), `부록01_오픈소스_리서치.md`, `부록02_시장_검증.md`, `부록03_플랫폼_정책.md`, `부록04_im-not-ai_평가.md`, `부록05_오픈소스_최적조합.md`, `추천_병행연재_최적장르.md`
> **v0.3 개정 사유**: `QA_기획정합성_리포트.md` 반영 (Major M-1~M-5, Minor m-4·m-9 처리)
> **작업 라우팅**: 본 문서는 기획팀 산출물. 프론트엔드 디자인 작업 시 §6 UI 가이드라인을 minimax 세션에 전달.

## v0.3 변경요약 (2026-08-25)

> 본 개정은 `QA_기획정합성_리포트.md`(2026-08-25)의 Major 5건·Minor 2건 처리 결과이다.

1. **M-1 해소**: FR-109(원고 내보내기, Should)를 MVP에 반영 — S2 에디터 메뉴에 '회차/프로젝트 내보내기(.txt/.md)' 추가(§1.2 M1 행·§3 S2 기능에 명시), §7 백로그 P3의 이중 분류 항목 제거.
2. **M-2 해소**: §3 S5 기능에 NFR-201 전송 고지 명시 — AI 패널 상단 Alert 문구 "선택한 회차·카드·로어북 내용은 지정한 LLM 엔드포인트로 전송됩니다".
3. **M-3 해소**: §3 S7 규정·현황 탭에 NFR-404 안내 문구 추가 + §8 리스크에 명시 — "AI 사용 공개/비공개 판단은 작가의 몫"(앱은 안내 의무만 부담).
4. **M-4 해소**: §5 윤문 span 스키마의 `category` 식별자를 humanize-korean taxonomy ID(A~J)로 고정, 카테고리 10종 목록을 실제 taxonomy로 교체.
5. **M-5 해소**: §8.2 api_key 암호화 방식 확정 — Windows DPAPI 우선(Python keyring), 폴백 Fernet 로컬 키 파일 + 한계 문서화 의무(Q6 종결).
6. **m-4 해소**: §4.1 Chapter 엔티티에 `memo TEXT` 필드 추가(FR-108).
7. **m-9 해소**: §6 UI 가이드라인을 디자인 확정안 기준으로 갱신 — Zustand 4스토어(editor/aiPanel/settings/ui)+TanStack Query 도입 명시, EventSource 표기 삭제(fetch 스트림으로 SSE), package.json 주석 의존성 보강(markdown-it/dompurify/react-router/@tanstack/react-query/jsdiff).
8. **QA v2 R-3 해소**: §2.2 package.json 주석에 **jszip** 신규 등재 — 변경 사유: 디자인 설계서 v1.1에서 프로젝트 내보내기(전 회차 .zip 묶음, FR-109)용으로 도입된 의존성을 npm 실측(jszip 3.10.1, 라이선스 `(MIT OR GPL-3.0-or-later)` → MIT 선택) 후 부록05 매트릭스와 함께 정식 채택.

## v0.2 변경요약 (2026-08-25)

1. 프론트엔드를 Vue 3 → **React**(Vite, TypeScript)로 교체 — 사용자 최종 결정(2026-08-25). UI 라이브러리는 shadcn/ui + Tailwind CSS, 상태관리는 Zustand로 조정.
2. 승인 완료된 `요구사항_정의서.md`와 정합성 확보 — 주요 모듈(M1~M5)과 화면에 FR/NFR 번호 역참조 추가.
3. `부록05` §⑤ 변경 목록 8건 전부 반영: markdown-it+DOMPurify 확정, openai SDK 채택, SQLite 프라그마 표준, 윤문 span 스키마+jsdiff, ST카드 자체 파서, 리스크 보강 등.
4. §6 UI 가이드라인을 minimax 세션 전달용으로 React 스택 기준으로 재작성.

## 변경이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| v0.1 | 2026-08-25 | 초안 작성 (기획팀) |
| v0.2 | 2026-08-25 | ① 프론트엔드 React 전환(shadcn/ui + Tailwind, Zustand) ② 요구사항 정의서 FR/NFR 역참조 추가 ③ 부록05 §⑤ 변경 8건 반영(markdown-it+DOMPurify·openai SDK·SQLite 프라그마·윤문 span+jsdiff·ST카드 자체 파서·리스크 갱신) ④ §6 UI 가이드라인 React 스택 재작성 |
| v0.3 | 2026-08-25 | **QA_기획정합성_리포트 반영**: ① FR-109 원고 내보내기 MVP 반영(S2 메뉴 .txt/.md, 백로그 P3 중복 제거) ② S5 AI 패널 전송 고지(NFR-201) 명시 ③ S7 NFR-404 AI 공개 판단 안내 추가(§8 리스크 병기) ④ 윤문 span category를 taxonomy ID(A~J)로 고정 ⑤ api_key 암호화 확정(DPAPI 우선+Fernet 폴백) ⑥ Chapter.memo 필드 추가(FR-108) ⑦ §6 UI 가이드라인 디자인 확정안 기준 갱신(Zustand 4스토어+TanStack Query 등) |

---

## 1. MVP 범위

### 1.1 목표
한국 웹소설 작가(노벨피아·문피아 병행 연재 전략)가 **기획 → 집필 → AI 보조 → 윤문 → 연재 준비**를 하나의 화면에서 처리할 수 있게 하는 최소 기능 제품.

**원칙**
- AI는 모델 무관(OpenAI 호환 API). Ollama 불사용 확정 방침 유지.
- AI 사용은 "인간이 검수하는 보조용" — 초안 품질 다듬기 목적, 규정 준수 방향.
- 로컬 우선: 원고·설정 데이터는 사용자 PC(SQLite 파일)에 저장.
- MVP에서는 외부 도구(SillyTavern/novelWriter) 연동 없음 → 백로그로.

### 1.2 포함 기능 (5개 모듈)

> FR/NFR 번호는 `요구사항_정의서.md`(승인 완료) 기준. 수용 기준은 동 문서 §7.

| # | 모듈 | 핵심 내용 | FR 역참조 |
|---|------|-----------|-----------|
| M1 | **원고/회차 에디터** | 마크다운 편집기. 프로젝트 → 회차(권 단위 묶음) 계층 관리. 회차별 상태(초고/수정중/완료), 글자 수 실시간 표시(공백 제외 카운트 — 노벨피아 PLUS 3,000자 조건 확인용), 자동 저장, **회차/프로젝트 원고 내보내기(.txt/.md)** | FR-101~109 / NFR-101·201·203·204 |
| M2 | **캐릭터 카드 관리** | 캐릭터 카드 CRUD. 이름/별칭/역할/외형/성격/말투/배경/관계 필드. SillyTavern 카드 형식과 호환 가능한 구조로 설계(연동은 백로그) | FR-201~205 / NFR-103 |
| M3 | **세계관/로어북 관리** | 용어·설정·장소·세력·마법체계 등 항목형 로어북. 카테고리 필터 + 키워드 검색. 향후 AI 컨텍스트 자동 주입을 고려한 키(keywords)-내용(content) 구조 | FR-301~305 / NFR-103 |
| M4 | **AI 패널** | OpenAI 호환 엔드포인트 설정 UI(base_url / api_key / model / temperature). 프리셋 프롬프트(장면 생성·대사 보강·요약 등) 실행 → 결과를 에디터에 삽입/교체. 스트리밍 응답 지원. Ollama 네이티브 미지원(OpenAI 호환 경유만) | FR-401~409 / NFR-102·202·303·501·503 |
| M5 | **윤문 모듈 (im-not-ai 연동)** | 회차 단위 "AI 티 제거 윤문" 버튼. 백엔드에서 im-not-ai 파이프라인(route_hint light/standard/heavy) 호출 → 진단 리포트(span) + 수정본 diff 뷰 → 수락/거절. 변경률 게이트 내장 | FR-501~507 / NFR-401·402 |

공통/플랫폼 대응(FR-601 규정 요약 표시, FR-602 노벨피아 PLUS 충족 현황)은 S7 설정 및 S1 홈에 배치한다(Could).

### 1.3 MVP 제외 (의도적 범위 제한)
- 복수 사용자/인증 (단일 로컬 사용자 가정)
- 플랫폼(문피아·노벨피아) 직접 발행 API
- 캘린더/연재 일정 관리
- SillyTavern · novelWriter · KoboldCpp 네이티브 프로토콜 연동
- 클라우드 동기화, 협업 편집

---

## 2. 기술 스택

### 2.1 선정 결과

| 레이어 | 선택 | 이유 |
|--------|------|------|
| 프론트 | **Vite + React (TypeScript)** | 사용자 최종 결정(2026-08-25)으로 Vue 3 대체. 생태계 최대, CodeMirror 6·jsdiff 등 주변 라이브러리와 프레임워크 무관 호환 (부록05 L1 실측 데이터 참고) |
| UI 라이브러리 | **shadcn/ui + Tailwind CSS** | React 전환에 따른 조정. 컴포넌트 코드가 프로젝트 내에 복사되어 자유 수정 가능 → 저채도 세리프 톤·다크/라이트 테마 요구에 유리. Radix 기반 접근성 (Naive UI는 Vue 전용이라 무효화) |
| 상태관리 | **Zustand** | Pinia 대체. 경량·보일러플레이트 최소, 에디터/AI패널/설정 스토어 분리 운용 |
| 마크다운 에디터 | **CodeMirror 6 (+lang-markdown) + markdown-it(+DOMPurify) 미리보기** | 가상 스크롤 렌더링으로 수만~십만 자 원고(NFR-101) 무지연. 미리보기는 markdown-it 15.x 확정(플러그인 구조 유리) + DOMPurify로 XSS 방지 (부록05 §⑤-1) |
| diff | **jsdiff (`diff` npm, BSD-3-Clause)** | 윤문 리포트(S6) 문자 단위 diff — 한국어 조사·어미 변화 대응, 변경률 게이트(FR-505) 계산 (부록05 L8) |
| 백엔드 | **Python 3.12 + FastAPI** | 비동기 SSE 스트리밍(AI 응답) 지원(sse-starlette 병행). Pydantic 스키마 검증 |
| DB | **SQLite + SQLAlchemy 2.x (+Alembic)** | 단일 사용자 로컬 앱 최적. 파일 1개 백업(NFR-203). 추후 PostgreSQL 전환 여지 확보 |
| AI 통신 | 백엔드 경유 프록시 — **openai Python SDK 채택(base_url 오버라이드)** | api_key를 프론트에 노출하지 않음. LM Studio·KoboldCpp·클라우드 즉시 호환(FR-401), SSE 스트리밍 내장(FR-405). httpx는 SDK 비호환 엔드포인트 발견 시 폴백 (부록05 L7) |
| 윤문 엔진 | im-not-ai 저장소(`~/.agents/im-not-ai`)를 서브프로세스/모듈로 호출 | MIT 라이선스. route_hint 3경로 그대로 활용 |

> **프론트엔드 React 전환 사유**: 부록05의 정량 평가는 Vue 3 우위였으나, 사용자가 2026-08-25 **React를 최종 결정**함에 따라 프레임워크·UI 라이브러리(Naive UI→shadcn/ui + Tailwind)·상태관리(Pinia→Zustand)를 일괄 교체했다. 에디터(CodeMirror 6), diff(jsdiff), 백엔드(FastAPI+SQLAlchemy 2.x+Alembic), SQLite WAL, openai SDK 결정은 프레임워크와 무관하게 유지된다.

**SQLite 접속 프라그마 표준** (부록05 §⑤-4 — 모든 DB 세션에서 공통 적용):

```
PRAGMA journal_mode=WAL;      -- 읽기·쓰기 병행(자동저장+조회)
PRAGMA synchronous=NORMAL;    -- WAL 모드에서 안전한 성능 최적점
PRAGMA busy_timeout=5000;     -- 쓰기 잠금 대기
PRAGMA foreign_keys=ON;
```

> WAL은 앱 비정상 종료 시 마지막 커밋까지 보존(NFR-204)에 부합. 로어북 검색(FR-304)은 FTS5 인덱스를 선택 적용.

> **DB 선정 근거**: HANDOFF의 "로컬 우선" 방침 + 부록01의 오픈소스 도구들이 모두 파일 기반 저장을 쓰는 점. SQLite는 설치 없이 동작하고 원고 전체를 한 파일로 백업할 수 있어 개인 창작 도구에 적합. 동시 쓰기가 거의 없는 단일 사용자 패턴이므로 성능 이슈 없음.

### 2.2 디렉터리 구조 (제안)

```
jippeel-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 엔트리
│   │   ├── models.py          # SQLAlchemy 모델
│   │   ├── schemas.py         # Pydantic 스키마
│   │   ├── routers/
│   │   │   ├── projects.py    # 프로젝트·회차
│   │   │   ├── characters.py  # 캐릭터 카드
│   │   │   ├── lorebook.py    # 세계관/로어북
│   │   │   ├── ai_panel.py    # AI 프록시·프롬프트
│   │   │   └── refine.py      # 윤문(im-not-ai)
│   │   └── services/
│   │       ├── ai_client.py   # OpenAI 호환 클라이언트
│   │       └── humanize.py    # im-not-ai 래퍼
│   └── alembic/               # 마이그레이션
    └── pyproject.toml

frontend/                       # React + Vite (TypeScript)
├── index.html
├── package.json                # react, react-router, zustand, @tanstack/react-query, markdown-it, dompurify, @codemirror/*, diff(jsdiff), jszip(프로젝트 내보내기 zip 묶음, MIT — 부록05 참조), tailwindcss
├── vite.config.ts              # dev 프록시 → FastAPI (/api)
└── src/
    ├── main.tsx
    ├── App.tsx                 # 라우팅(S1~S7) + 전역 레이아웃
    ├── components/
    │   ├── ui/                 # shadcn/ui 생성 컴포넌트 (Button, Dialog, Sheet, Tabs ...)
    │   ├── editor/             # CodeMirror 6 래퍼, 미리보기(markdown-it+DOMPurify), 글자 수 표시
    │   ├── panels/             # AI 패널(전역 사이드 패널), 윤문 리포트(diff 뷰)
    │   └── features/           # 회차 트리, 캐릭터 카드 그리드, 로어북 리스트 등
    ├── pages/                  # S1 홈, S2 에디터, S3 캐릭터, S4 로어북, S7 설정
    ├── stores/                 # Zustand: editorStore, aiPanelStore, settingsStore, uiStore
    ├── lib/                    # API 클라이언트(fetch 스트림으로 SSE — EventSource 미사용), jsdiff 유틸, utils(cn)
    └── styles/                 # Tailwind 설정 + 다크/라이트 테마 토큰
```

---

## 3. 화면 목록 및 핵심 기능

| # | 화면 | URL(예) | 핵심 기능 |
|---|------|---------|-----------|
| S1 | **홈 / 프로젝트 목록** | `/` | 프로젝트(작품) 카드 목록. 생성·열기·삭제. 최근 작업 회차 바로가기 |
| S2 | **회차 에디터 (메인)** | `/projects/{id}/write` | 좌: 회차 트리(권/화). 중앙: 마크다운 편집기 + 미리보기 탭. 우: 글자 수(공백 포함/제외), 회차 상태, 빠른 메모. 상태 칩(초고→수정중→완료). 에디터 메뉴에 회차/프로젝트 내보내기(.txt/.md) 제공(FR-109) |
| S3 | **캐릭터 갤러리** | `/projects/{id}/characters` | 캐릭터 카드 그리드. 클릭 시 상세 드로어(외형·성격·말투·배경·관계 편집). 관계 링크 표시(MVP는 텍스트 필드 수준) |
| S4 | **세계관/로어북** | `/projects/{id}/lore` | 항목 리스트(카테고리별 필터: 용어/장소/세력/기타). 키워드 태그 편집. 검색창. 항목 ↔ 회차 참조 표시(선택) |
| S5 | **AI 패널 (사이드 패널)** | S2/S3/S4 어디서든 열림 | 엔드포인트 설정 폼(base_url, api_key, model 목록 조회, temperature, max_tokens). 프롬프트 프리셋 선택 → 컨텍스트(현재 회차/선택 캐릭터/로어북 항목) 체크박스로 포함. 스트리밍 출력 영역. 결과 "에디터 끼워넣기 / 선택 교체 / 복사" 버튼. **패널 상단 전송 고지 Alert 고정 표시**(NFR-201): "선택한 회차·카드·로어북 내용은 지정한 LLM 엔드포인트로 전송됩니다" |
| S6 | **윤문 리포트** | S2에서 진입 (모달/전용 뷰) | route_hint 경로 표시(light/standard/heavy). 카테고리별 탐지 span 하이라이트. 원문↔수정본 diff. 변경률 게이트(30% 경고 / 50% 차단) 안내. 수락 시 에디터 반영 |
| S7 | **설정** | `/settings` | AI 엔드포인트 전역 기본값 관리(프로젝트별 오버라이드 가능). im-not-ai 경로·윤문 강도 기본값. 자동 저장 주기. **규정·현황 탭에 NFR-404 안내 문구 고정 표시**: "AI 사용 여부의 공개/비공개 판단은 작가의 몫입니다"(앱은 안내 의무만 부담 — 권장 방침 유도 수준) |

---

## 4. 데이터 모델 개요

### 4.1 엔티티

```
Project        작품 (제목, 장르, 시놉시스, 플랫폼 메모, 생성/수정일)
Chapter        회차 (project_id FK, 권/volume, 정렬 순서, 제목,
                     content_md TEXT, status[초고|수정중|완료],
                     word_count_cache,
                     memo TEXT  ← 빠른 메모(FR-108))
Character      캐릭터 (project_id FK, name, aliases[], role[주연|조연|...],
                     appearance, personality, speech_style, background,
                     card_json JSON  ← ST 호환 확장 여지)
Relationship   관계 (from_character_id FK, to_character_id FK,
                     label 예: "주군-가신", note)          [MVP: 단순 텍스트 링크]
LoreEntry      로어북 항목 (project_id FK, category[용어|장소|세력|기타],
                     title, content, keywords[])
AiEndpoint     AI 엔드포인트 (name, base_url, api_key_encrypted,
                     default_model, temperature, is_default)
PromptPreset   프롬프트 프리셋 (name, template_text,
                     context_flags[]  ← chapter/characters/lore 포함 여부)
RefineRun      윤문 실행 기록 (chapter_id FK, route_hint, changed_ratio,
                     report_json, result_text, accepted BOOL)
```

### 4.2 관계 (ERD 요약)

```
Project 1───N Chapter
Project 1───N Character
Character N───N Character   (via Relationship)
Project 1───N LoreEntry
AiEndpoint, PromptPreset : 전역 테이블 (프로젝트 독립)
RefineRun N───1 Chapter
```

- 회차 본문은 마크다운 통짜 텍스트(`content_md`)로 저장. MVP에서 장면 단위 분해는 하지 않음(백로그).
- 캐릭터 카드는 자체 필드 + `card_json`(JSON) 병행으로 두어, 나중에 SillyTavern PNG 카드(V2 spec) 임포트/익스포트 시 매핑 비용을 낮춤.
- 로어북의 `keywords[]`는 향후 AI 패널에서 "본문에 키워드가 등장하면 해당 로어북 항목을 컨텍스트로 자동 주입"하는 기능의 기반.

---

## 5. API 엔드포인트 초안

공통 prefix: `/api/v1`. 인증 없음(로컬 단일 사용자).

### 프로젝트·회차 (M1)
```
GET    /api/v1/projects                        # 프로젝트 목록
POST   /api/v1/projects                        # 생성
GET    /api/v1/projects/{pid}                  # 상세
PATCH  /api/v1/projects/{pid}
DELETE /api/v1/projects/{pid}

GET    /api/v1/projects/{pid}/chapters         # 회차 트리
POST   /api/v1/projects/{pid}/chapters
GET    /api/v1/chapters/{cid}                  # 본문 포함
PATCH  /api/v1/chapters/{cid}                  # 본문/상태/제목 저장 (자동저장: PATCH debounce)
DELETE /api/v1/chapters/{cid}
PATCH  /api/v1/projects/{pid}/chapters/order   # 순서/권 이동 (bulk)
```

### 캐릭터 (M2)
```
GET    /api/v1/projects/{pid}/characters
POST   /api/v1/projects/{pid}/characters
GET    /api/v1/characters/{chid}
PATCH  /api/v1/characters/{chid}
DELETE /api/v1/characters/{chid}
POST   /api/v1/projects/{pid}/characters/relations     # 관계 링크 생성/수정
```

### 로어북 (M3)
```
GET    /api/v1/projects/{pid}/lore             # ?category=&q= 필터/검색
POST   /api/v1/projects/{pid}/lore
GET    /api/v1/lore/{lid}
PATCH  /api/v1/lore/{lid}
DELETE /api/v1/lore/{lid}
```

### AI 패널 (M4)
```
GET    /api/v1/ai/endpoints                    # 저장된 엔드포인트 목록 (key 마스킹)
POST   /api/v1/ai/endpoints
PATCH  /api/v1/ai/endpoints/{eid}
DELETE /api/v1/ai/endpoints/{eid}
GET    /api/v1/ai/endpoints/{eid}/models       # GET {base_url}/models 프록시 → 모델 목록

GET    /api/v1/ai/presets                      # 프롬프트 프리셋 목록
POST   /api/v1/ai/generate                     # POST → SSE 스트리밍
       body: { endpoint_id, preset_id, prompt_override?,
               context: { chapter_id?, character_ids?, lore_ids? },
               params: { temperature?, max_tokens? } }
```

### 윤문 (M5)
```
POST   /api/v1/refine                          # 회차 본문 윤문 실행
       body: { chapter_id, force_route?: "light"|"standard"|"heavy" }
       resp: { run_id, route_hint,
               spans: [                        # 진단 span 목록 (S6 하이라이트 규격 — 부록05 §⑤-5)
                 { category: string,           # humanize-korean taxonomy ID 고정(A~J):
                                               #   A 번역투 / B 영어인용 / C 구조적패턴 /
                                               #   D 관용구 / E 리듬 / F 수식중복 /
                                               #   G Hedging / H 접속사 / I 형식명사 / J 시각장식
                   start: int, end: int,       # 원본 텍스트 기준 문자 오프셋
                   severity?: string,          # info | warn
                   message?: string } ],
               original: string, refined: string,
               changed_ratio: float,           # 변경률 게이트(30% 경고/50% 차단) 판정값
               gate: "pass"|"warn"|"block" }
GET    /api/v1/refine/runs/{run_id}            # 리포트 재조회
POST   /api/v1/refine/runs/{run_id}/accept     # 수락 → 회차 본문 교체 + 기록
POST   /api/v1/refine/runs/{run_id}/reject     # 거절 → 기록만 남김
```

> **diff 계산 책임 분리**: 백엔드는 원문/수정본 + 카테고리 span만 반환하고, 프론트는 **jsdiff(BSD-3-Clause)** 로 문자 단위 diff를 재계산해 하이라이트한다(한국어 조사·어미 변화 대응). 자동 덮어쓰기 없음(FR-504), 변경률 게이트는 FR-505 그대로 UI에 노출.

---

## 6. 프론트엔드 UI 가이드라인 (minimax 세션 전달용 — v0.3: 디자인 확정안 기준 갱신)

아래 내용을 그대로 프론트엔드 디자인 세션(`prime-agent --provider minimax --model MiniMaxAI/MiniMax-M3`)에 전달한다.

> ### UI 가이드라인 요약
> - **제품**: 한국 웹소설 작가용 데스크톱 우선 웹 대시보드. 긴 글(회차당 5천~1만 자)을 오래 쓰는 환경이므로 **눈 피로 최소화와 집중 모드가 최우선**.
> - **기술 스택(확정)**: **React + Vite (TypeScript)**, **shadcn/ui + Tailwind CSS**, 상태관리 **Zustand**(스토어 4종: editor / aiPanel / settings / ui), 서버 상태 **TanStack Query(@tanstack/react-query)**, 라우팅 react-router, 에디터 CodeMirror 6(+lang-markdown), 미리보기 markdown-it+DOMPurify, diff jsdiff. Vue/Pinia/Naive UI는 폐기(v0.2 결정). AI 응답 스트리밍은 **fetch 스트림으로 SSE 수신**(EventSource 미사용 — POST 불가).
> - **레이아웃**: 3분할 기준 — 좌측 사이드바(회차 트리/카테고리), 중앙 에디터(최대 폭 ~720px, 장문 가독 행길이), 우측 패널(AI 패널·윤문 리포트가 겹쳐 열리는 Sheet/Drawer).
> - **화면 목록**: S1 홈, S2 회차 에디터(메인), S3 캐릭터 갤러리, S4 로어북, S5 AI 패널(전역 사이드 패널), S6 윤문 리포트(diff 뷰), S7 설정 — 위 §3 표 참조.
> - **shadcn/ui 컴포넌트 매핑 제안**: 회차 트리=커스텀 Tree(shadcn 미제공 → Radix Collapsible 조합 또는 react-arborist 검토), 캐릭터 상세·AI 패널=Sheet, 윤문 리포트=Dialog, 카테고리 필터·상태 칩=Tabs/Badge, 설정 폼=Form(Input, Select, Switch). 컴포넌트 소스가 프로젝트 내 `src/components/ui`에 생성되므로 토큰 수정으로 저채도 테마를 직접 구현할 것.
> - **톤 & Tailwind 테마**: 차분한 저채도 배경 + 다크/라이트 테마 지원(CSS 변수 기반 테마 토큰). 액센트 컬러 1개(예: 남성향 판타지·무협 타깃 감성 — 딥블루/브론즈 계열 제안). 소설 도구이므로 대시보드 느낌의 밝은 파랑·SaaS 그라데이션은 배제. shadcn/ui 기본 뉴트럴 팔레트를 그대로 쓰지 말고 반드시 커스텀 토큰으로 조정.
> - **타이포**: 본문 에디터는 국산 세리프/고딕 가독형(예: Pretendard, Noto Serif KR 선택 옵션). 행간 1.7~1.9, 자간 살짝 넓게. Tailwind `fontFamily`/`leading` 확장 설정으로 관리.
> - **핵심 UX 요구**:
>   1. 에디터에서 글자 수(공백 제외)가 항상 보여야 함 (노벨피아 3,000자 조건 확인용 — FR-104).
>   2. AI 결과는 절대 자동 삽입하지 않고 "끼워넣기/선택 교체/복사" 명시 버튼 (FR-406).
>   3. 윤문 diff는 원문/수정본 병렬 + 변경 하이라이트(jsdiff 문자 단위), 진단 span(category 오프셋) 하이라이트, 변경률 게이트(30% 경고/50% 차단)를 시각적으로 안내 (FR-503~505).
>   4. 저장 상태 표시("저장됨 · 방금 전") — 자동저장 신뢰감 (FR-106).
>   5. 캐릭터 카드는 그리드 + 상세 드로어 방식 (FR-205).
> - **산출물 구조**: 컴포넌트 시안은 `frontend/src/components`(ui/ · editor/ · panels/ · features/) 구조로 산출. 페이지 단위는 `src/pages`. Zustand 스토어 경계(editor / aiPanel / settings / ui)와 TanStack Query 캐시 경계(API 데이터)를 설계에 명시할 것.
> - **금지**: 이모지 아이콘 남발(lucide-react 아이콘 사용), 과한 애니메이션, 정보 밀도 높은 위젯 총출 — 작가의 작업 흐름을 방해하는 요소 일절.

---

## 7. 백로그 (MVP 이후)

| 우선순위 | 항목 | 비고 |
|:---:|------|------|
| P1 | SillyTavern 캐릭터 카드 임포트/익스포트 | PNG metadata(V2/V3 spec) ↔ `card_json` 매핑. **자체 V2/V3 파서 구현**(부록05 L5: Python 성숙 파서 부재 실측 — @motioneffector/cards(MIT) 등 참고, AGPL 코드 비복사). 부록01: ST가 카드 생태계 사실상 표준(⭐32k+) |
| P1 | 로어북 자동 컨텍스트 주입 | 본문 키워드 매칭 → AI 패널 요청에 로어북 항목 자동 포함 (SillyTavern world info 방식) |
| P2 | novelWriter 연동/임포트 | GPL-3.0. `.nwx`(XML) 프로젝트 가져오기. 부록01: OpenAI/Ollama 연동 내장 최신 버전 |
| P2 | 장면(Scene) 단위 분해 | 회차 → 장면 계층. 장면별 AI 생성·재작성 |
| P2 | 연속성 검사 | 캐릭터 말투·설정·시간축 불일치 탐지 (saga의 지식그래프 아이디어 참조) |
| P3 | KoboldCpp 네이티브 연동 | 부록01: 소설 특화 로컬 엔진. OpenAI 호환 모드 외 전용 API |
| P3 | 플랫폼 발행 보조 | 직접 API 발행 연동만 해당(규정 리스크로 보류). 회차/프로젝트 내보내기는 MVP 반영(FR-109 — v0.3)으로 분리 |
| P3 | 연재 캘린더·업로드 일정 관리 | 주 5회·일일 연재 루틴 지원 |
| P3 | 멀티 프로젝트 통계 | 회차별 글자 수 추이, 집필 속도 |
| 검토 | 클라우드 동기화 / Git 기반 버전 관리 | 원고 백업·이전 버전 복구 |

---

## 8. 리스크·유의사항 (사양 결정에 반영됨)

1. **AI 규정**: 문피아 일반 연재 AI 전면 금지, 노벨피아 순수 창작 원칙 (부록03). → 윤문 모듈은 "품질 다듬기 보조" 위치로 설계, AI 자동 생성→무검수 게시 흐름을 만들지 않음.
2. **API 키 보안**: api_key는 백엔드에만 저장(DB 암호화), 프론트 전송 시 마스킹. **암호화 방식 확정(v0.3)**: Windows DPAPI 우선(Python `keyring` 사용), DPAPI 불가 환경의 폴백은 **Fernet 로컬 키 파일**. 폴백 사용 시 키 파일 저장 위치와 한계(동일 PC 로컬 공격자에 대한 방어 한계 등 위협 모델)를 문서화할 의무.
3. **im-not-ai 게이트**: 변경률 30% 경고/50% 강제 중단 규칙을 윤문 리포트 UI에 그대로 노출 — 과윤문 방지.
4. **규정 변동**: 플랫폼 AI 규정은 수시 변경(HANDOFF §5) — 대시보드에 직접 관여하는 기능(자동 발행 등)은 보류.
5. **CodeMirror 6 저장소 이전**: codemirror 조직 GitHub 저장소가 2026-04 중 아카이브(read-only) 확인. npm 배포는 @codemirror/view 6.43.9(2026-08-16)까지 지속되며 개발 인프라가 `code.haverbeke.berlin`으로 이전된 것으로 판단 → **분기별 npm 배포 여부 모니터링** 필요 (부록05 §④-1).
6. **UI 라이브러리 라이선스 방어**: PrimeVue는 npm license 필드 불명확 + 라이선스 변경 이력으로 배제. 채택한 shadcn/ui+Tailwind CSS(MIT 계열)·jsdiff(BSD-3)·openai SDK(Apache-2.0)로 라이선스 리스크 최소화 (부록05 §④-2).
7. **AI 클라이언트 경량 유지**: LiteLLM은 의존성 트리 과중으로 배제 확정 — openai SDK 단일 경로 유지(NFR-502 비전공자 PC 실행 부담 최소화). httpx 폴백 사용 시에만 버전 고정 (부록05 §④-3).
8. **AI 사용 공개 여부 (NFR-404)**: AI 사용 공개/비공개 판단은 작가의 몫 — 앱은 S7 규정·현황 탭에서 이를 안내할 의무만 진다. 탐지 회피 기능 영구 제외(FR-W5) 원칙은 유지.

---
*다음 단계: ① 본 사양(v0.3) 검토·승인 → ② minimax 세션에서 S1~S7 와이어프레임/컴포넌트 설계(§6 React 스택 가이드라인 전달) → ③ 백엔드 스캐폴딩(FastAPI + Alembic 초기 마이그레이션 + SQLite 프라그마 표준 적용)*