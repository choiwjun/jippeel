# 한국어 회차 품질 수직 슬라이스 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선택적 회차 브리프와 한국어 장면별 생성·감수 규칙을 기존 Jippeel AI 흐름에 연결한다.

**Architecture:** `GenerateContext.brief`를 선택적 Pydantic 구조체로 추가하고 기존 `_build_context_blocks`에서 프롬프트 블록으로 직렬화한다. 프롬프트는 고정 수치를 완화한 한국어 웹소설 지침으로 교체하며, 기존 SSE 이벤트와 자동 반영 금지 계약은 유지한다. 브리프 영속화와 별도 review_runs는 다음 단계로 남긴다.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy/SQLite(이번 단계 마이그레이션 없음), React/TypeScript, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-korean-episode-quality.md`

## Global Constraints

- 전체 외부 패키지를 추가하지 않는다.
- SQLite를 작품 데이터 원본으로 유지한다.
- AI 생성 결과는 자동으로 본문에 반영하지 않는다.
- 한국어·문피아·노벨피아 기준으로 작성한다.
- `browser-cdp`, 플랫폼 스캔, 탐지 회피, 외부 hooks/agents는 추가하지 않는다.
- 기존 API/SSE 필드는 삭제·개명하지 않고 add-only로 확장한다.
- 작업 트리의 기존 `HANDOFF.md`, `.eval_tmp/`, 리서치 문서 변경을 되돌리거나 덮어쓰지 않는다.

---

### Task 1: 회차 브리프 계약과 백엔드 주입

**Files:**
- Modify: `backend/app/schemas.py` near `GenerateContext`
- Modify: `backend/app/routers/ai_panel.py` near `NOVEL_SYSTEM_PROMPT` and `_build_context_blocks`
- Test: `backend/tests/test_ai_generate_stream.py`

**Interfaces:**
- Produces `EpisodeBrief` and `GenerateContext.brief: EpisodeBrief | None`.
- Produces a labeled `[이번 화 브리프 — 생성 계약]` user-context block when present.
- Existing payloads without `brief` remain valid and produce no brief block.

- [ ] **Step 1: Write failing tests**

Add tests that post `context.brief` to `/api/v1/ai/generate`, assert HTTP 200, inspect the fake client's final user message, and require the labeled block plus `emotion_goal`, core event, cost, prohibition, and next hook. Add a second test posting no brief and asserting the label is absent. Add a validation test with an empty `emotion_goal` and more than three `core_events` that expects HTTP 422.

- [ ] **Step 2: Run the focused tests and verify failure**

Run from Windows project environment:

```powershell
cd C:\Users\wj941\Documents\jippeel\backend
.venv\Scripts\python.exe -m pytest tests/test_ai_generate_stream.py -q
```

Expected: the new tests fail because `GenerateContext` does not accept `brief` and no brief block is built.

- [ ] **Step 3: Implement the minimal contract**

Define `EpisodeBrief` with bounded fields:

```python
class EpisodeBrief(BaseModel):
    emotion_goal: str = Field(min_length=1, max_length=500)
    core_events: list[str] = Field(min_length=1, max_length=3)
    character_choices: list[str] = Field(min_length=1, max_length=4)
    cost: str = Field(min_length=1, max_length=500)
    prohibitions: list[str] = Field(min_length=1, max_length=10)
    next_hook: str = Field(min_length=1, max_length=500)
    scene_type: Literal["대립", "액션", "정보정리", "감정", "이동"] | None = None
    target_chars_novelpia: int | None = Field(default=None, ge=1000, le=10000)
```

Add `brief: EpisodeBrief | None = None` to `GenerateContext`. In `_build_context_blocks`, serialize only non-empty fields in a stable Korean-labeled block. Do not put the block into the stored chapter or mutate any model. Keep all old context blocks and return tuple shape unchanged.

- [ ] **Step 4: Run focused tests and verify pass**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_ai_generate_stream.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/schemas.py backend/app/routers/ai_panel.py backend/tests/test_ai_generate_stream.py
git commit -m "feat: add optional episode brief to generation context"
```

---

### Task 2: 적응형 한국어 생성·감수 프롬프트

**Files:**
- Modify: `backend/app/routers/ai_panel.py` constants `NOVEL_SYSTEM_PROMPT` and `REVIEW_SYSTEM_PROMPT`
- Test: `backend/tests/test_ai_generate_stream.py`

**Interfaces:**
- Existing generation and review SSE event names remain unchanged.
- System prompt states that `EpisodeBrief` is a priority contract when present.
- System prompt uses scene-dependent rhythm guidance and does not require a universal 35~50% dialogue ratio or universal 1~2 sentence paragraphs.
- Review prompt names structure, character, continuity/settings, prose/rhythm, and Korean platform fit while preserving `[감수]` and `[수정본]` output markers.

- [ ] **Step 1: Write failing prompt-contract tests**

Add tests that call `/ai/generate` with a fake endpoint and inspect `messages[0]["content"]`. Assert the generation prompt contains `회차 브리프` and `장면 유형` and does not contain the old absolute phrase `전체 분량의 35~50%는 대사다`. Add a review-enabled test asserting the review system prompt contains `구조`, `캐릭터`, `연속성`, `문장`, `플랫폼`, `[감수]`, and `[수정본]`.

- [ ] **Step 2: Run focused tests and verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_ai_generate_stream.py -q
```

Expected: the new prompt-contract assertions fail against the current fixed prompt.

- [ ] **Step 3: Replace only the prompt constants**

Rewrite `NOVEL_SYSTEM_PROMPT` in Korean with these rules: brief first; scene type controls dialogue density and paragraph rhythm; action uses readable action beats; confrontation may be dialogue-led; information scenes explain only what the scene needs; the opening should enter the scene's conflict or question at an appropriate pace rather than a universal character count; end with a meaningful unresolved question/action when the brief calls for a hook; never output meta commentary. Retain Korean web-novel voice, concrete action, restrained exposition, and no automatic insertion.

Rewrite `REVIEW_SYSTEM_PROMPT` in Korean with five review lenses and evidence-based concise findings. Require important issues only, each with category, location/evidence, reason, and suggested fix in Korean prose. Require the exact markers `[감수]` and `[수정본]`; output the complete revised draft after the marker; preserve good passages and do not invent facts outside the brief/canon. Do not copy text from the external repository.

- [ ] **Step 4: Run focused and full backend tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_ai_generate_stream.py tests/test_quality.py -q
.venv\Scripts\python.exe -m pytest -q
```

Expected: focused and full suites pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/routers/ai_panel.py backend/tests/test_ai_generate_stream.py
git commit -m "feat: use adaptive Korean generation and review prompts"
```

---

### Task 3: AI 패널 브리프 입력 UI와 요청 직렬화

**Files:**
- Modify: `frontend/src/stores/aiPanelStore.ts`
- Modify: `frontend/src/components/panels/AiPanel.tsx`
- Modify: `frontend/src/lib/aiStream.ts` only if a new start field is actually needed; otherwise do not change it

**Interfaces:**
- Produces an optional, user-editable Korean brief form.
- Sends `context.brief` only when the user has entered the required fields.
- Keeps the existing prompt textarea and all existing context switches.
- Does not insert generated text automatically.

- [ ] **Step 1: Implement state and form with existing component patterns**

Add a small `episodeBrief` state object with the backend field names, defaulting to empty strings/arrays. Render a collapsible `이번 화 브리프` section near the existing prompt section with labeled controls for 감정 목표, 핵심 사건 (one per line, maximum three), 인물 선택·대가 (one per line), 대가, 금지사항 (one per line), 다음 화 훅, 장면 유형, and optional target characters. Show a short note that empty brief fields are not sent and that the result still requires human review.

- [ ] **Step 2: Serialize only valid non-empty input**

Before calling `streamGenerate`, convert newline lists to trimmed arrays, build `context.brief` only when all required fields are non-empty, and omit it otherwise. Do not change the existing context flags or review settings. Keep the UI Korean and make the controls keyboard accessible with stable labels.

- [ ] **Step 3: Build the frontend**

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npm run build
```

Expected: TypeScript compilation and Vite build succeed.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/stores/aiPanelStore.ts frontend/src/components/panels/AiPanel.tsx frontend/src/lib/aiStream.ts
git commit -m "feat: add episode brief controls to AI panel"
```

---

### Task 4: 통합 회귀 검증과 문서 기록

**Files:**
- Modify: `HANDOFF.md` only by appending a dated completion note; preserve existing text
- Test: existing backend suite and frontend build

- [ ] **Step 1: Run backend regression**

```powershell
cd C:\Users\wj941\Documents\jippeel\backend
.venv\Scripts\python.exe -m pytest -q
```

Expected: baseline 175 tests plus new tests pass, with no failures.

- [ ] **Step 2: Run frontend regression**

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npm run build
```

Expected: build exits 0.

- [ ] **Step 3: Inspect diff and check forbidden changes**

```powershell
cd C:\Users\wj941\Documents\jippeel
git diff --check
git status --short
git diff --stat
```

Confirm no new dependency, scraper, browser automation, external skill package, automatic editor insertion, or destructive change to existing dirty artifacts.

- [ ] **Step 4: Append a concise handoff note**

Record changed files, test commands/results, the request-only nature of `EpisodeBrief`, and the follow-up backlog (`blueprint` persistence and structured review history). Do not claim output quality improvement until a human-rated Korean sample comparison is run.

- [ ] **Step 5: Commit**

```powershell
git add HANDOFF.md
git commit -m "docs: record Korean episode quality slice"
```
