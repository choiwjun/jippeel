# 웹소설 AI 집필 대시보드 — MVP 사양 문서

> **버전**: v0.5
> **작성일**: 2026-09-11 (v0.5 갱신)
> **근거 문서**: `HANDOFF.md`, `요구사항_정의서.md`(승인 완료), `부록01_오픈소스_리서치.md`, `부록02_시장_검증.md`, `부록03_플랫폼_정책.md`, `부록04_im-not-ai_평가.md`, `부록05_오픈소스_최적조합.md`, `추천_병행연재_최적장르.md`
> **v0.3 개정 사유**: `QA_기획정합성_리포트.md` 반영 (Major M-1~M-5, Minor m-4·m-9 처리)
> **v0.4 개정 사유**: G3 PRD 게이트 — §9~§13 신규 추가(F-001~F-036 기능 정의, R→F 전수 매핑표, Q1~Q5 결정안, 아키텍처 리스크 C8/C9, Success Metrics)
> **v0.5 개정 사유**: 장편 기억 거버넌스 후속 기획 — M6/S8 추가, MemoryEntry·project ownership·provenance/stale·수동 승인 계약 반영. 자동 요약/backfill과 운영 적용은 별도 승인 범위로 유지.
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
| v0.4 | 2026-08-26 | **G3 PRD 게이트 산출**: ① §9 F-001~F-036 기능 정의(전 기능 MVP 범위) ② §10 R-001~R-054 전수 → F-xxx 매핑표(누락 0건) ③ §11 미결 질문 Q1~Q5 결정안(권 구조 채택, 관계 텍스트 라벨, 프리셋 5종, route_hint 자동 옵션 병행, 자동 백업 백로그 이월) ④ §12 아키텍처 리스크 C8(글자 수 산정)/C9(im-not-ai 호출 검증) 명시 ⑤ §13 Success Metrics 추가 |
| v0.5 | 2026-09-11 | **장편 기억 거버넌스 기획 반영**: M6/S8, MemoryEntry API·UI·ownership·provenance/stale·수동 승인/폐기 수용 기준 추가. 자동 요약/backfill·운영 migration·실제 provider는 별도 승인 게이트로 분리 |
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

### 1.2 포함 기능 (6개 모듈)

> FR/NFR 번호는 `요구사항_정의서.md`(승인 완료) 기준. 수용 기준은 동 문서 §7.

| # | 모듈 | 핵심 내용 | FR 역참조 |
|---|------|-----------|-----------|
| M1 | **원고/회차 에디터** | 마크다운 편집기. 프로젝트 → 회차(권 단위 묶음) 계층 관리. 회차별 상태(초고/수정중/완료), 글자 수 실시간 표시(공백 제외 카운트 — 노벨피아 PLUS 3,000자 조건 확인용), 자동 저장, **회차/프로젝트 원고 내보내기(.txt/.md)** | FR-101~109 / NFR-101·201·203·204 |
| M2 | **캐릭터 카드 관리** | 캐릭터 카드 CRUD. 이름/별칭/역할/외형/성격/말투/배경/관계 필드. SillyTavern 카드 형식과 호환 가능한 구조로 설계(연동은 백로그) | FR-201~205 / NFR-103 |
| M3 | **세계관/로어북 관리** | 용어·설정·장소·세력·마법체계 등 항목형 로어북. 카테고리 필터 + 키워드 검색. 향후 AI 컨텍스트 자동 주입을 고려한 키(keywords)-내용(content) 구조 | FR-301~305 / NFR-103 |
| M4 | **AI 패널** | OpenAI 호환 엔드포인트 설정 UI(base_url / api_key / model / temperature). 프리셋 프롬프트(장면 생성·대사 보강·요약 등) 실행 → 결과를 에디터에 삽입/교체. 스트리밍 응답 지원. Ollama 네이티브 미지원(OpenAI 호환 경유만) | FR-401~409 / NFR-102·202·303·501·503 |
| M5 | **윤문 모듈 (im-not-ai 연동)** | 회차 단위 "AI 티 제거 윤문" 버튼. 백엔드에서 im-not-ai 파이프라인(route_hint light/standard/heavy) 호출 → 진단 리포트(span) + 수정본 diff 뷰 → 수락/거절. 변경률 게이트 내장 | FR-501~507 / NFR-401·402 |
| M6 | **장편 기억 거버넌스** | 작품별 기억 초안 생성·목록·필터·provenance/stale 확인. 작가가 draft를 승인/폐기하며, stale 또는 미승인 기억은 AI context에 자동 주입하지 않음. 자동 요약/backfill은 포함하지 않음 | LM-001~010 |

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
| S8 | **장편 기억 관리** | `/projects/{id}/memory` | 작품 정보와 수동 관리 안내. 종류·상태·stale·근거 회차 필터. body/provenance/source revision/hash/effective range 표시. 초안 추가, 승인·폐기 확인, stale 경고와 자동 주입 제외 사유 표시(LM-001~010) |

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
MemoryEntry    장편 기억 (project_id FK, chapter_id nullable FK,
                     source_revision, source_sha256, kind, body,
                     visibility[draft|approved|retired], effective range,
                     provenance_json, created_at, updated_at)
```

### 4.2 관계 (ERD 요약)

```
Project 1───N Chapter
Project 1───N Character
Character N───N Character   (via Relationship)
Project 1───N LoreEntry
AiEndpoint, PromptPreset : 전역 테이블 (프로젝트 독립)
RefineRun N───1 Chapter
Project 1───N MemoryEntry
Chapter 1───N MemoryEntry (provenance source; 연결 회차 삭제는 409)
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

### 장편 기억 (M6)
```text
GET    /api/v1/projects/{pid}/memories
       # kind/visibility/chapter_id/stale/limit 필터
POST   /api/v1/projects/{pid}/memories
       # chapter_id, kind, body, effective range → 항상 draft
PATCH  /api/v1/projects/{pid}/memories/{mid}
       # visibility/effective range만 수정, pid ownership 검증
```

- 생성 시 source revision/hash/provenance는 서버가 계산한다.
- `retired`는 terminal 상태다.
- source revision/hash가 달라지면 stale로 표시하고 AI context에서 제외한다.
- memory가 연결된 chapter 삭제는 409로 거부해 provenance row를 보존한다.

### 윤문 (M5)
```text
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
> - **화면 목록**: S1 홈, S2 회차 에디터(메인), S3 캐릭터 갤러리, S4 로어북, S5 AI 패널(전역 사이드 패널), S6 윤문 리포트(diff 뷰), S7 설정, S8 장편 기억 관리 — 위 §3 표 참조.
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
| :---: | :--- | :--- |
| P1 | SillyTavern 캐릭터 카드 임포트/익스포트 | PNG metadata(V2/V3 spec) ↔ `card_json` 매핑. **자체 V2/V3 파서 구현**(부록05 L5: Python 성숙 파서 부재 실측 — @motioneffector/cards(MIT) 등 참고, AGPL 코드 비복사). 부록01: ST가 카드 생태계 사실상 표준(⭐32k+) |
| P1 | 로어북 자동 컨텍스트 주입 | 본문 키워드 매칭 → AI 패널 요청에 로어북 항목 자동 포함 (SillyTavern world info 방식) |
| P1 | 자동 요약·backfill | 승인된 원문에서 memory draft 후보를 만드는 별도 설계·평가·승인 작업. 자동 승인·운영 DB 실행은 금지 |
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
*다음 단계: ① v0.5 장편 기억 기획·수용 기준 검토 → ② 운영 migration/provider/Windows QA 승인 게이트 확정 → ③ 자동 요약/backfill 별도 설계 승인 후 dry-run 구현. 현재 M6/S8 governance slice는 구현·검증 완료 상태다.*

---

## 9. 기능 정의 (F-ID 부여) — v0.4 G3 산출

> 규약 v1에 따라 본 사양의 기능에 **F-001~F-036** 고유번호를 부여한다. 모든 기능은 **MVP 범위**이다.
MVP 밖 항목은 §7 백로그로 관리되며, Won't(FR-W1~W6)는 ID 미부여 대상이다.

| F-ID | 기능명 | 설명 | 모듈 | 범위 |
|------|--------|------|------|:---:|
| F-001 | 프로젝트 관리 | 작품(프로젝트) 생성·열기·삭제, 목록(S1 홈). 삭제 확인 대화상자 | M1 | MVP |
| F-002 | 회차·권 관리 | 회차 생성·정렬·삭제, 권(volume) 묶음 및 권 간 회차 이동. volume은 NULL 허용(평면 회차 지원) | M1 | MVP |
| F-003 | 마크다운 에디터·미리보기 | CodeMirror 6 편집기 + markdown-it(+DOMPurify) 미리보기. 3~5만 자 원고에서 입력 반영 100ms 미만 성능 기준 내장 | M1 | MVP |
| F-004 | 실시간 글자 수(공백 제외) | 타이핑 중 1초 이내 갱신. 공백 제외 카운트 별도 표시(노벨피아 PLUS 3,000자 확인용). ※A2: 플랫폼 카운트 검증 샘플 필요 | M1 | MVP |
| F-005 | 회차 상태 관리 | 초고/수정중/완료 상태 지정·변경, 재시작 후 유지 | M1 | MVP |
| F-006 | 자동 저장·종료 복구 | 입력 정지 후 5초 이내 자동 저장(debounce PATCH), 저장 실패 안내. WAL 프라그마로 비정상 종료 시 마지막 커밋 보존 | M1 | MVP |
| F-007 | 회차 메모 | Chapter.memo 별도 필드 — 빠른 메모 저장·재표시·수정 | M1 | MVP |
| F-008 | 원고 내보내기 | 회차/프로젝트 전체 .txt/.md 내보내기(프로젝트는 jszip 묶음) | M1 | MVP |
| F-009 | 캐릭터 카드 CRUD·갤러리 | 카드 생성·조회·수정·삭제, 7필드(이름/별칭/역할/외형/성격/말투/배경), 그리드+상세 드로어(S3) | M2 | MVP |
| F-010 | 캐릭터 관계(텍스트 라벨) | Relationship 테이블 label 필드 기반 단순 링크. 양쪽 카드에서 조회 | M2 | MVP |
| F-011 | 카드 스키마 확장 + ST 매핑표 | card_json 자유 확장 필드 + SillyTavern 필드명 매핑표 문서化(직접 임포트/익스포트는 백로그 P1) | M2 | MVP |
| F-012 | 로어북 엔트리 CRUD | 용어·설정·장소·세력 항목형 엔트리 생성·조회·수정·삭제 | M3 | MVP |
| F-013 | 로어북 카테고리 필터 | 용어/장소/세력/기타 카테고리 부여·필터링 | M3 | MVP |
| F-014 | 로어북 키워드 태그 | 엔트리당 다중 키워드 부여. M4 컨텍스트 선택 목록에 노출 | M3 | MVP |
| F-015 | 로어북 검색 | 키워드·제목·본문 검색(FTS5 선택 적용). 수백 건 기준 1초 이내 | M3 | MVP |
| F-016 | 로어북↔회차 참조 조회 | 특정 엔트리 참조 회차 목록 표시(선택 기능) | M3 | MVP |
| F-017 | AI 엔드포인트 연결(OpenAI 호환 전용) | base_url/api_key/model/temperature UI 설정. S2/S3/S4 어디서든 AI 패널 호출 가능. Ollama 네이티브 경로 없음(OpenAI 호환 경유만 — 제약 C3). 프로파일 교체만으로 모델 전환 | M4 | MVP |
| F-018 | api_key 암호화·마스킹 | DPAPI 우선(keyring)+Fernet 폴백, 화면 마스킹, 저장 파일 평문 0건 | M4 | MVP |
| F-019 | 프롬프트 프리셋 실행 | 초기 5종 한국어 프리셋(장면 생성·대사 보강·요약·전개 브레인스토밍·설정 질의) + 사용자 정의 편집 | M4 | MVP |
| F-020 | 컨텍스트 선택 + 전송 고지 | 현재 회차/선택 캐릭터/선택 로어북 체크박스. 패널 상단 전송 고지 Alert 고정(NFR-201) | M4 | MVP |
| F-021 | 스트리밍 응답 | SSE(fetch 스트림) 실시간 출력. 출력 중 에디터 편집 가능(UI 비차단) | M4 | MVP |
| F-022 | AI 결과 삽입/교체/복사 | 끼워넣기(커서 위치)/선택 교체/클립보드 복사 — 자동 삽입 없음 | M4 | MVP |
| F-023 | 엔드포인트 프로파일 다중·기본값 | 프로파일 2개 이상 저장·전환·기본값 지정, 재시작 유지 | M4 | MVP |
| F-024 | API 오류 안내 | 엔드포인트 불일치·인증 실패·타임아웃 3종 한국어 안내 | M4 | MVP |
| F-025 | 윤문 실행(im-not-ai 연동) | 회차 단위 AI 티 제거 윤문 버튼 → im-not-ai 파이프라인 서브프로세스/모듈 호출 | M5 | MVP |
| F-026 | 윤문 강도 route_hint | light/standard/heavy 사용자 선택 + '자동'(진단 기반 판정, 판정 근거 표시) | M5 | MVP |
| F-027 | 진단 리포트(span) | 10대 카테고리(taxonomy A~J)별 탐지 위치 span 하이라이트 | M5 | MVP |
| F-028 | diff 수락/거절 | 원문↔수정본 jsdiff 문자 단위 diff, 수정 단위별 수락/거절. 자동 덮어쓰기 없음, 거절 시 원문 보존 | M5 | MVP |
| F-029 | 변경률 게이트 | 30% 경고 / 50% 중단(im-not-ai 4대 철칙 동일 값), UI 노출 | M5 | MVP |
| F-030 | 윤문 용도 고지 | '품질 향상 목적' 문구 상시 표시, 탐지 회피 암시 문구 0건 | M5 | MVP |
| F-031 | 윤문 실행 이력 | 대상 회차·강도·변경률·수락 여부·실행 시각 기록·조회(RefineRun) | M5 | MVP |
| F-032 | 플랫폼 규정 요약·확인 시점 | 문피아·노벨피아 규정 요약+최종 확인일+외부 링크(C7 보증 면책), AI 공개 판단 주체 안내(NFR-404) | 공통 | MVP |
| F-033 | 노벨피아 PLUS 충족 현황 | 연작 15편 이상·회차 공백 제외 3,000자 등 조건 충족 현황 프로젝트 단위 표시 | 공통 | MVP |
| F-034 | 로컬 저장·백업/복원·오프라인 | 전 데이터 로컬 SQLite 단일 파일. 수동 백업/복원(파일 단위). 외부 AI 차단 시에도 편집·저장·로컬 윤문 동작 | 기반 | MVP |
| F-035 | 한국어 UI·원클릭 실행·무문서 사용성 | 전 화면 한국어, Jippeel실행.bat 더블클릭 구동, 비개발자 무문서 핵심 흐름(집필→AI→윤문→저장) | 기반 | MVP |
| F-036 | 오픈소스 라이선스 고지 | im-not-ai(MIT) 등 출처·라이선스를 About에 고지 | 기반 | MVP |

**백로그(MVP 밖)**: §7 표 참조 — SillyTavern PNG 카드 임포트/익스포트(P1), 로어북 자동 컨텍스트 주입(P1), novelWriter 임포트(P2), 장면 단위 분해(P2), 연속성 검사(P2), KoboldCpp 네이티브(P3), 플랫폼 발행 API(P3), 연재 캘린더(P3), 멀티 프로젝트 통계(P3), 주기적 자동 백업(P2 — Q5 결정안). 대응 R이 없는 순수 확장 기능이므로 F-ID 미부여한다. **영구 제외(Won't)**: FR-W1~W6 — AI 탐지 회피 등, ID 미부여.

---

## 10. 요구사항↔기능 매핑표 (R-xxx → F-xxx)

> 전체 54건(R-001~R-054)이 정확히 하나 이상의 F-xxx에 매핑됨. 괄호 안은 기존 문서 호환용 FR/NFR 병기.

| R-ID | 요구사항 요지 | 우선순위 | → F-xxx |
|------|--------------|:---:|---------|
| R-001 (FR-101) | 프로젝트 생성·열기·삭제 | Must | F-001 |
| R-002 (FR-102) | 회차 생성·정렬·삭제 + 권 관리 | Should | F-002 |
| R-003 (FR-103) | 마크다운 에디터+미리보기 | Must | F-003 |
| R-004 (FR-104) | 실시간 글자 수(공백 제외) | Must | F-004 |
| R-005 (FR-105) | 회차 상태(초고/수정중/완료) | Must | F-005 |
| R-006 (FR-106) | 5초 자동 저장 | Must | F-006 |
| R-007 (FR-107) | 타이핑 반영 <100ms | Must | F-003 |
| R-008 (FR-108) | 회차 메모 필드 | Could | F-007 |
| R-009 (FR-109) | 원고 내보내기 .txt/.md | Should | F-008 |
| R-010 (FR-201) | 캐릭터 카드 CRUD | Must | F-009 |
| R-011 (FR-202) | 카드 7필드 | Must | F-009 |
| R-012 (FR-203) | 관계 텍스트 라벨 | Should | F-010 |
| R-013 (FR-204) | 확장 필드(JSON)+ST 매핑표 문서 | Should | F-011 |
| R-014 (FR-205) | 카드 그리드 목록 | Could | F-009 |
| R-015 (FR-301) | 로어북 엔트리 CRUD | Must | F-012 |
| R-016 (FR-302) | 카테고리 부여·필터 | Should | F-013 |
| R-017 (FR-303) | 키워드 태그 | Must | F-014 |
| R-018 (FR-304) | 로어북 검색 | Must | F-015 |
| R-019 (FR-305) | 엔트리 참조 회차 조회 | Could | F-016 |
| R-020 (FR-401) | OpenAI 호환 엔드포인트 UI 설정 | Must | F-017 |
| R-021 (FR-402) | api_key DPAPI+Fernet 암호화 | Must | F-018 |
| R-022 (FR-403) | 프롬프트 프리셋 실행 | Must | F-019 |
| R-023 (FR-404) | 컨텍스트 체크박스 | Should | F-020 |
| R-024 (FR-405) | 스트리밍 응답 | Should | F-021 |
| R-025 (FR-406) | 결과 삽입/교체/복사 | Must | F-022 |
| R-026 (FR-407) | 프로파일 다중·기본값 | Should | F-023 |
| R-027 (FR-408) | API 오류 안내 | Must | F-024 |
| R-028 (FR-409) | Ollama 네이티브 미지원(제약) | Must | F-017 |
| R-029 (FR-501) | 회차 단위 윤문 실행 | Must | F-025 |
| R-030 (FR-502) | 윤문 강도 선택/자동 | Should | F-026 |
| R-031 (FR-503) | 카테고리별 span 리포트 | Should | F-027 |
| R-032 (FR-504) | diff 수락/거절 | Must | F-028 |
| R-033 (FR-505) | 변경률 게이트 30/50% | Must | F-029 |
| R-034 (FR-506) | 품질 향상 목적 고지 | Must | F-030 |
| R-035 (FR-507) | 윤문 실행 이력 | Could | F-031 |
| R-036 (FR-601) | 플랫폼 규정 요약 표시 | Could | F-032 |
| R-037 (FR-602) | PLUS 충족 현황 | Could | F-033 |
| R-038 (NFR-101) | 타이핑 지연 <100ms(3~5만 자) | Must* | F-003 |
| R-039 (NFR-102) | 스트리밍 중 UI 비차단 | Must* | F-021 |
| R-040 (NFR-103) | 검색 <1s(수백 건) | Must* | F-015 |
| R-041 (NFR-201) | 로컬 저장+AI 전송 고지 | Must* | F-020, F-034 |
| R-042 (NFR-202) | api_key 평문 노출 금지 | Must* | F-018 |
| R-043 (NFR-203) | 파일 단위 백업/복원 | Must* | F-034 |
| R-044 (NFR-204) | 강제 종료 시 마지막 저장 보존 | Must* | F-006 |
| R-045 (NFR-301) | 무문서 핵심 흐름 수행 | Must* | F-035 |
| R-046 (NFR-302) | 한국어 UI | Must* | F-035 |
| R-047 (NFR-303) | AI 패널 전역 호출 | Must* | F-017 |
| R-048 (NFR-401) | 탐지 회피 문구 금지 | Must* | F-030 |
| R-049 (NFR-402) | im-not-ai 라이선스 고지 | Must* | F-036 |
| R-050 (NFR-403) | 규정 확인 시점 표시 | Must* | F-032 |
| R-051 (NFR-404) | AI 공개 판단 주체 안내 | Must* | F-032 |
| R-052 (NFR-501) | 외부 AI 장애 시 로컬 동작 | Must* | F-034 |
| R-053 (NFR-502) | bat 더블클릭 실행 | Must* | F-035 |
| R-054 (NFR-503) | 설정만으로 모델 교체 | Must* | F-017 |

> \* NFR(R-038~R-054)은 요구사항 정의서 §4에 우선순위 열이 없어 MVP 기반 필수(Must)로 처리했다.
> 매핑 누락 R: **없음**. status=dropped 처리한 R도 없다(전 항목 MVP 구현 대상).

---

## 11. 기획 단계 미결 질문(Q1~Q5) 결정안 — v0.4

| # | 질문 | 결정안 | 근거 |
|---|------|--------|------|
| Q1 | 회차 "권(volume)" 개념 필요 여부 | **MVP 채택** — Chapter.volume nullable. 권 없는 평면 회차 목록도 허용 | R-002(Should) + 장편 연재 관행(부록02). 데이터 모델에 이미 반영(v0.3 §4.1)이라 제거 비용이 더 큼 |
| Q2 | 캐릭터 관계 표현 방식 | **MVP는 텍스트 라벨 확정**(Relationship.label). 양방향 링크·그래프는 백로그(FR-W2와 일치) | R-012 수용기준이 "텍스트 라벨 수준"으로 명시. 최소 구현 비용 |
| Q3 | 프리셋 초기 세트 | **한국어 기본 5종**: 장면 생성·대사 보강·요약(요구사항 명시 3종) + 전개 브레인스토밍·설정 질의(추가 2종). 사용자 편집·삭제 가능 | R-022(Must) 최소 3종 충족 + 집필 루틴 보조 가치. 추가 2종은 프리셋 편집으로 언제든 제거 가능해 리스크 낮음 |
| Q4 | 윤문 강도 route_hint 자동 판정 | **사용자 선택 기본 + '자동' 옵션 병행** — 자동 선택 시 판정 근거를 화면에 표시 | R-030 수용기준이 선택·자동 판정 양쪽을 모두 명시. im-not-ai 진단 결과 재사용으로 구현 비용 소 |
| Q5 | 백업/복원 방식 | **MVP는 수동 버튼만**(파일 단위). 주기적 자동 백업은 백로그 P2로 이월 | NFR-203(R-043) 수용기준이 "파일 단위 백업/복원"만 요구. 자동 주기 설계는 확신 부족 → 불확실 항목 MVP 밖 원칙 적용 |

---

## 12. 아키텍처 리스크·제약 반영 (G3 → G4 인수)

| # | 리스크 | PRD 반영 내용 | 후속 조치 |
|---|--------|--------------|-----------|
| C8 (A2) | 노벨피아 공백 제외 글자 수 산정 방식과 앱 카운트 불일치 가능 | F-004에 "플랫폼 카운트 검증 샘플 필요" 주석 내장. 수용기준(R-004, §7 M1③)도 검증 샘플 1건 이상 일치를 요구 | QA 단계(G7)에서 실측 샘플 비교 검증 |
| C9 (A3) | im-not-ai 스킬의 앱 프로세스 내 호출 가능 여부 미검증(가정 A3) | F-025/F-026은 서브프로세스/모듈 호출을 전제로 설계하되, 이 전제가 성립하지 않으면 M5 설계 변경 필요 | **G4 아키텍처 진입 시 최우선 검증 과제**: 스크립트/모듈 호출 실측 → 실패 시 래퍼 설계 재검토 |

---

## 13. Success Metrics (MVP 완료 판정 지표)

> 출처: 요구사항_정의서.md §7 수용 기준 + 개별 R 수용기준. 전부 충족 시 MVP 완료로 판정한다.

| 구분 | 지표 | 목표값 |
|------|------|--------|
| 성능 | 타이핑 입력 화면 반영 (3~5만 자 원고) | 100ms 미만 (R-007/R-038) |
| 성능 | 로어북·캐릭터 수백 건 검색 반환 | 1초 이내 (R-018/R-040) |
| 성능 | 글자 수 갱신 | 타이핑 중 1초 이내, 공백 제외 카운트가 플랫폼 검증 샘플과 일치 (R-004, C8) |
| 신뢰성 | 편집 입력 정지 후 자동 저장 | 5초 이내, 저장 실패 시 안내 표시 (R-006) |
| 신뢰성 | 강제 종료(kill) 후 원고 복구 | 마지막 자동 저장 시점까지 보존 (R-044) |
| 신뢰성 | 외부 AI 차단 상태 | 편집·저장·윤문(로컬분) 정상 동작 (R-041/R-052) |
| AI 연동 | 실측 응답 수신 엔드포인트 | 로컬(LM Studio 등)+클라우드 각 1곳 이상 (R-020) |
| 보안 | api_key 평문 노출 | 저장 파일 덤프 0건 + 화면 마스킹 (R-021/R-042) |
| AI 패널 | 스트리밍 중 에디터 편집 | 가능(수동 조작 응답 <100ms) (R-024/R-039) |
| 윤문 | 진단→윤문→diff→수락 흐름 | AI 티 샘플에서 1회 이상 완결 (R-029) |
| 윤문 | 변경률 게이트 | 30% 경고 / 50% 중단 동작 확인 (R-033) |
| 윤리 | 탐지 회피 암시 문구 | UI·문서·로그 0건 (R-034/R-048) |
| 사용성 | 코딩 비전공자 1인 무문서 수행 | 집필→AI→윤문→저장 흐름 성공 (R-045) |
| 사용성 | 한국어 UI 커버리지 | 화면·메뉴·오류 메시지 100% (R-046) |
| 운영 | 실행 방법 | Jippeel실행.bat 더블클릭만으로 구동 (R-053) |
| 데이터 | 백업→신규 환경 복원 | 전체 데이터 동일성 확인 (R-043) |
| 데이터 | 프로파일 교체로 모델 전환 | 설정 변경만 가능, 창작 데이터 변경 0건 (R-054) |
