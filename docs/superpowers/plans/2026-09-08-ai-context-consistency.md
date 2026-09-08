# AI Context Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generation, review, parallel writing, canon, and quality use one validated request context with consistent current identity, purpose, relationships, payoff permissions, and revision provenance.

**Architecture:** Add a deep backend `ContextBundle` module at `backend/app/services/ai_context.py`. Existing routers adapt their Pydantic payloads into one `ContextBundleRequest`, then use the bundle's blocks, style text, directive text, and metadata. Frontend changes build one saved request snapshot per AI run and store request-scoped directives in memory by `(project_id, chapter_id)`.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy/SQLite, OpenAI-compatible async client, SSE, React, TypeScript, Zustand, Playwright, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-ai-context-consistency.md`

## Global Constraints

- Branch: `feat/ai-context-consistency` at baseline `70ec67e`.
- Preserve completed manuscript preservation feature at commit `42fad7c`; do not weaken `frontend/src/lib/manuscriptDrafts.ts` ownership checks.
- No historical-memory extraction.
- No persistent chapter-goal system.
- No new database migration unless a reviewer proves existing JSON metadata fields cannot carry input provenance.
- No generic token-budget engine or global truncation refactor.
- Preserve existing context caps, deterministic ordering, and included-ID metadata.
- Label unknown historical facts as unknown/current record; do not fabricate.
- Future foreshadow reference based on chapter `(sort_order, id)` is only a coarse existing-data filter/label.
- Future plans may guide generation but are not current facts or character knowledge.
- Reject cross-project referenced foreshadow chapters when consumed; do not fix unrelated foreshadow CRUD in this phase.
- Keep AI/canon/quality controls small in existing `AiPanel`, `CanonDialog`, and `QualityDialog`.
- No frontend redesign, no new package dependencies.
- Tests must use temp DBs and dedicated ports only. Never use port `8000`, port `5173`, production `backend/jippeel.db`, WAL/SHM files, real services, real LLMs, or secrets.
- Use native Windows Python and Windows `node_modules` for project commands. Do not run Linux Node against this frontend.
- Use the negative corpus in `docs/audits/ai-context-baseline-probes.md` and `.json` for regression tests: A1 cross-project selected character/lore, A2 mixed explicit project/style/auto context, B relationship omission, C parallel style omission.
- Current style/lore records are current records, not historical truth. Historical memory remains deferred.
- Implementation workers must not commit unless the parent explicitly authorizes commits after review.
- Backend changes are implemented and reviewed before frontend work consumes them.
- Dedicated QA owns only new tests/scripts/config and docs, not production source.

---

## File structure

### Backend production files

- Create `backend/app/services/ai_context.py`
  - The deep module for context ownership, deterministic block assembly, purpose directives, relation inclusion, foreshadow labels, and metadata.
  - Public interface: `ContextBundleRequest`, `ContextBundle`, `request_from_generate()`, `request_from_canon()`, `build_context_bundle()`, `purpose_directive()`.
- Modify `backend/app/schemas.py`
  - Add `EpisodePurpose` alias.
  - Add fields to `GenerateContext`.
  - Add `EpisodeBrief.ending_intent` and make `next_hook` purpose-validated through `GenerateContext`.
  - Add `ParallelScenePlan.ending_intent` and allow optional `closing_hook` with purpose-specific validation in service code.
  - Extend `CanonCheckRequest` additively.
- Modify `backend/app/routers/ai_panel.py`
  - Replace local context assembly with `ai_context.build_context_bundle()`.
  - Keep existing SSE event names and existing start fields.
  - Add `context_metadata` to `start` and `parallel_start`.
  - Pass the same bundle text/directives to generation, single review, parallel planner, parallel workers, and parallel review.
  - Remove unconditional hook/unresolved-conflict prompt directives.
- Modify `backend/app/services/canon.py`
  - Consume `ContextBundle` for canon blocks.
  - Treat approved foreshadow IDs as allowed payoff/reveal for that run only.
  - Capture immutable checked input body/revision/SHA256 before provider work.
  - Store `checked_input_revision` and `checked_input_hash` in existing context JSON and response `checked_context`.
- Modify `backend/app/routers/quality.py`
  - Add `episode_purpose` query parameter to `chapter_quality()`.
  - Store purpose in `QualityCheck.metrics_json` and dedupe by text hash plus purpose.
- Modify `backend/app/services/quality.py`
  - Make hook penalty/suggestions purpose-aware.
  - Do not invent a finale score.
- Modify `backend/app/services/parallel_writer.py`
  - Add purpose-specific scene contract validation without changing order assembly or cancellation.

### Backend tests

- Create `backend/tests/test_ai_context_bundle.py`
- Create `backend/tests/test_ai_context_directives.py`
- Modify `backend/tests/test_ai_generate_stream.py`
- Modify `backend/tests/test_foreshadows_canon.py`
- Modify `backend/tests/test_quality.py`
- Modify `backend/tests/test_parallel_writer.py`
- Modify `backend/tests/test_parallel_quality.py`

### Frontend production files

- Modify `frontend/src/stores/aiPanelStore.ts`
  - Add current `projectId`, `includeChapterContent`, directive map, and result origin state.
- Modify `frontend/src/components/panels/AiPanel.tsx`
  - Flush current chapter before generation.
  - Build request body from saved identity and revision.
  - Add purpose, relationship, and approved-foreshadow controls.
  - Block insertion/replacement when result origin does not match active editor identity.
- Modify `frontend/src/components/editor/CanonDialog.tsx`
  - Add small purpose/relationship/payoff controls and send expected revision when available.
- Modify `frontend/src/components/editor/QualityDialog.tsx`
  - Add purpose select and display hook applicability.
- Modify `frontend/src/pages/EditorPage.tsx`
  - Keep `aiPanelStore` current identity synchronized with `editorStore` and loaded chapter detail.
  - Fix the local status-change hook warning so it uses shared purpose.
- Modify `frontend/src/lib/aiStream.ts`
  - Parse optional `context_metadata` from `start` and `parallel_start`.
- Modify `frontend/src/lib/api.ts`
  - Add frontend types for episode purpose/directive metadata if needed by components.

### QA-only files

- Create `scripts/ai_context_fake_llm_server.py`
  - Deterministic OpenAI-compatible local provider on a caller-supplied dedicated port.
  - Writes every outbound prompt to JSONL.
- Create `scripts/ai_context_backend_fixture.py`
  - Native Windows fixture that creates a temp DB, migrates it, starts backend on a dedicated port, seeds data, and points default endpoint to the fake provider.
- Create `frontend/playwright.ai-context.config.ts`
  - Dedicated ports, no reuse, no `8000` or `5173`.
- Create `frontend/e2e/ai-context-consistency.spec.ts`
  - Real browser integration against the temp backend and deterministic provider.
- Create `docs/audits/ai-context-consistency-validation.md`
  - QA evidence with command output and prompt-log paths.

---

## Worker sequence and review gates

1. Task 1 implementer: backend `ContextBundle` ownership/parity/metadata.
2. Task 1 reviewer: separate fresh reviewer inspects diff and runs Task 1 gates.
3. Task 2 implementer: backend purpose/payoff/brief/parallel/canon/local quality rules.
4. Task 2 reviewer: separate fresh reviewer inspects diff and runs Task 2 gates plus Task 1 focused tests.
5. Task 3 implementer: frontend request snapshot, shared controls, result-origin safety.
6. Task 3 reviewer: separate fresh reviewer inspects diff and runs frontend build plus backend compatibility gates.
7. Task 4 QA implementer: integration fixture, deterministic provider, Playwright tests, validation doc.
8. Task 4 reviewer: separate fresh reviewer runs full new integration and focused backend/frontend gates.

Each task is independently rejectable. Do not let a worker edit files outside its task file list.

---

### Task 1: Backend ContextBundle assembler, ownership validation, parity, and metadata

**Files:**
- Create: `backend/app/services/ai_context.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/ai_panel.py`
- Modify: `backend/app/services/canon.py`
- Modify: `backend/app/routers/quality.py` — Task 1 only: canon validation before endpoint/client creation and immutable checked-input provenance routing. Local quality purpose behavior belongs to Task 2.
- Test: `backend/tests/test_ai_context_bundle.py`
- Test: `backend/tests/test_ai_generate_stream.py`
- Test: `backend/tests/test_foreshadows_canon.py`

**Interfaces:**
- Consumes existing models: `Project`, `Chapter`, `Scene`, `Character`, `LoreEntry`, `Foreshadow`, `Relationship`, `VolumeNote`.
- Produces `ContextBundleRequest` dataclass in `backend/app/services/ai_context.py`.
- Produces `ContextBundle` dataclass in `backend/app/services/ai_context.py`.
- Produces `request_from_generate(payload: GenerateRequest) -> ContextBundleRequest`.
- Produces `request_from_canon(payload: CanonCheckRequest, chapter: Chapter) -> ContextBundleRequest`.
- Produces `build_context_bundle(db: Session, request: ContextBundleRequest) -> ContextBundle`.
- Produces `ContextBundle.metadata` with deterministic included ID lists.
- `ai_panel._build_messages(payload, db)` may keep its name for caller stability, but internally it must call `ai_context.request_from_generate()` and `ai_context.build_context_bundle()`.
- `canon.build_messages(db, chapter, payload)` must use `request_from_canon()` and `build_context_bundle()`.

- [ ] **Step 1: Write failing tests for identity/body separation and legacy compatibility**

Create `backend/tests/test_ai_context_bundle.py` with this starting content:

```python
import pytest
from fastapi import HTTPException

from app.schemas import CanonCheckRequest, GenerateContext, GenerateRequest
from app.services.ai_context import build_context_bundle, request_from_canon, request_from_generate


def _db(client):
    from app.database import get_db
    return next(iter(client.app.dependency_overrides[get_db]()))


def _project_with_chapter(client, title="P", body="본문"):
    pid = client.post("/api/v1/projects", json={"title": title}).json()["id"]
    chapter = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화", "sort_order": 1}).json()
    client.put(f"/api/v1/chapters/{chapter['id']}/content", json={"content_md": body, "expected_revision": 0})
    return pid, client.get(f"/api/v1/chapters/{chapter['id']}").json()


def test_legacy_chapter_id_includes_body_by_default(client):
    pid, chapter = _project_with_chapter(client, body="레거시 본문")
    payload = GenerateRequest(endpoint_id=1, prompt_override="이어 써줘", context=GenerateContext(chapter_id=chapter["id"]))
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    joined = "\n\n".join(bundle.blocks)
    assert bundle.project_id == pid
    assert bundle.chapter_id == chapter["id"]
    assert bundle.metadata["include_chapter_content"] is True
    assert "[현재 회차: 1화]" in joined
    assert "레거시 본문" in joined


def test_current_identity_survives_body_opt_out(client):
    pid, chapter = _project_with_chapter(client, body="보내면 안 되는 본문")
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="새 장면을 제안해줘",
        context=GenerateContext(
            project_id=pid,
            chapter_id=chapter["id"],
            include_chapter_content=False,
            expected_revision=chapter["revision"],
            auto_outline=True,
        ),
    )
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    joined = "\n\n".join(bundle.blocks)
    assert bundle.project_id == pid
    assert bundle.chapter_id == chapter["id"]
    assert bundle.chapter_revision == chapter["revision"]
    assert bundle.metadata["include_chapter_content"] is False
    assert "보내면 안 되는 본문" not in joined
    assert bundle.metadata["outline"]["current"] is False or "current" not in bundle.metadata["outline"]
```

The second assertion intentionally allows no current outline when no memo exists. It must not allow the body text.

- [ ] **Step 2: Write failing tests for ownership rejection before provider work**

Append to `backend/tests/test_ai_context_bundle.py`:

```python
def test_project_chapter_mismatch_rejected(client):
    pid_a, _chapter_a = _project_with_chapter(client, title="A")
    _pid_b, chapter_b = _project_with_chapter(client, title="B")
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="이어 써줘",
        context=GenerateContext(project_id=pid_a, chapter_id=chapter_b["id"]),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 422
    assert "project" in str(exc.value.detail).lower() or "작품" in str(exc.value.detail)


def test_selected_character_wrong_project_rejected(client):
    pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    wrong_char = client.post(f"/api/v1/projects/{pid_b}/characters", json={"name": "타작품 인물"}).json()
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="이어 써줘",
        context=GenerateContext(
            project_id=pid_a,
            chapter_id=chapter_a["id"],
            character_ids=[wrong_char["id"]],
        ),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 422


def test_stale_expected_revision_rejected(client):
    pid, chapter = _project_with_chapter(client)
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="이어 써줘",
        context=GenerateContext(project_id=pid, chapter_id=chapter["id"], expected_revision=0),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "revision_conflict"
    assert exc.value.detail["current_revision"] == chapter["revision"]


def test_selected_lore_wrong_project_rejected_probe_a1(client):
    pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    wrong_lore = client.post(f"/api/v1/projects/{pid_b}/lore", json={
        "category": "용어", "title": "B_INTRUDER_LORE_TITLE", "content": "B_INTRUDER_LORE_CONTENT",
    }).json()
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="selected mismatch prompt",
        context=GenerateContext(project_id=pid_a, chapter_id=chapter_a["id"], lore_ids=[wrong_lore["id"]]),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 422


def test_explicit_project_b_cannot_mix_with_chapter_a_probe_a2(client):
    pid_a, chapter_a = _project_with_chapter(client, title="A", body="A_PID_CHAPTER_BODY_ONLY")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    client.post(f"/api/v1/projects/{pid_b}/lore", json={
        "category": "용어", "title": "B_AUTO_LORE_TITLE", "keywords": ["B_AUTO"], "content": "B_AUTO_LORE_CONTENT",
    })
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="B_AUTO",
        context=GenerateContext(project_id=pid_b, chapter_id=chapter_a["id"], auto_lore=True, auto_foreshadow=True),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 422
```



- [ ] **Step 2a: Write provider-before-validation negative tests for routes**

Append these route-level regressions to `backend/tests/test_ai_context_bundle.py`. They must fail against the current ordering or current missing validation. They protect the exact ordering: validation returns 409/422 before provider client creation, endpoint resolution, or provider await.

```python
def test_generate_422_does_not_create_provider_client(client, monkeypatch):
    from app.routers import ai_panel

    ep = client.post("/api/v1/ai/endpoints", json={"name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    pid_a, _chapter_a = _project_with_chapter(client, title="A")
    _pid_b, chapter_b = _project_with_chapter(client, title="B")
    touched = {"make_client": False}

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created after validation failure")

    monkeypatch.setattr(ai_panel.llm, "make_client", fail_make_client)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "should reject before provider",
        "context": {"project_id": pid_a, "chapter_id": chapter_b["id"]},
    })
    assert resp.status_code == 422
    assert touched["make_client"] is False


def test_generate_409_does_not_create_provider_client(client, monkeypatch):
    from app.routers import ai_panel

    ep = client.post("/api/v1/ai/endpoints", json={"name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    pid, chapter = _project_with_chapter(client, title="A")
    touched = {"make_client": False}

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created after revision conflict")

    monkeypatch.setattr(ai_panel.llm, "make_client", fail_make_client)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "should reject stale revision",
        "context": {"project_id": pid, "chapter_id": chapter["id"], "expected_revision": 0},
    })
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "revision_conflict"
    assert touched["make_client"] is False


def test_canon_409_does_not_resolve_endpoint_or_create_provider_client(client, monkeypatch):
    from app.routers import quality as quality_router

    _pid, chapter = _project_with_chapter(client, title="A")
    touched = {"resolve_endpoint": False, "make_client": False}

    def fail_resolve_endpoint(*_args, **_kwargs):
        touched["resolve_endpoint"] = True
        raise AssertionError("endpoint resolution must not run after revision conflict")

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created after revision conflict")

    monkeypatch.setattr(quality_router, "resolve_endpoint", fail_resolve_endpoint)
    monkeypatch.setattr(quality_router.llm, "make_client", fail_make_client)
    resp = client.post("/api/v1/canon-check", json={"chapter_id": chapter["id"], "expected_revision": 0})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "revision_conflict"
    assert touched == {"resolve_endpoint": False, "make_client": False}


def test_canon_422_does_not_resolve_endpoint_for_wrong_project_approved_foreshadow(client, monkeypatch):
    from app.routers import quality as quality_router

    _pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    fs_b = client.post(f"/api/v1/projects/{pid_b}/foreshadows", json={"title": "B_ONLY_FORESHADOW"}).json()
    touched = {"resolve_endpoint": False, "make_client": False}

    def fail_resolve_endpoint(*_args, **_kwargs):
        touched["resolve_endpoint"] = True
        raise AssertionError("endpoint resolution must not run after ownership failure")

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created after ownership failure")

    monkeypatch.setattr(quality_router, "resolve_endpoint", fail_resolve_endpoint)
    monkeypatch.setattr(quality_router.llm, "make_client", fail_make_client)
    resp = client.post("/api/v1/canon-check", json={
        "chapter_id": chapter_a["id"],
        "approved_foreshadow_ids": [fs_b["id"]],
    })
    assert resp.status_code == 422
    assert touched == {"resolve_endpoint": False, "make_client": False}
```

- [ ] **Step 3: Write failing tests for deterministic relationships and metadata**

Append:

```python
def test_selected_relationships_include_only_both_selected_endpoints(client):
    pid, chapter = _project_with_chapter(client)
    a = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "한서윤"}).json()
    b = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "강무진"}).json()
    c = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "남궁린"}).json()
    rel_ab = client.post(f"/api/v1/projects/{pid}/characters/relations", json={
        "from_character_id": a["id"], "to_character_id": b["id"], "label": "사제", "note": "공개적으로 감싸지 못한다",
    }).json()
    client.post(f"/api/v1/projects/{pid}/characters/relations", json={
        "from_character_id": a["id"], "to_character_id": c["id"], "label": "동료", "note": "임시 동맹",
    })
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="대화 장면",
        context=GenerateContext(
            project_id=pid,
            chapter_id=chapter["id"],
            character_ids=[b["id"], a["id"]],
            include_relationships=True,
        ),
    )
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    joined = "\n\n".join(bundle.blocks)
    assert "[인물 관계" in joined
    assert "한서윤" in joined and "강무진" in joined
    assert "남궁린" not in joined
    assert bundle.metadata["included_character_ids"] == [b["id"], a["id"]]
    assert bundle.metadata["included_relationship_ids"] == [rel_ab["id"]]


def test_relationships_with_one_selected_character_are_empty_not_422(client):
    pid, chapter = _project_with_chapter(client)
    a = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "한서윤"}).json()
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="독백 장면",
        context=GenerateContext(
            project_id=pid,
            chapter_id=chapter["id"],
            character_ids=[a["id"]],
            include_relationships=True,
        ),
    )
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    assert "[인물 관계" not in "\n\n".join(bundle.blocks)
    assert bundle.metadata["included_relationship_ids"] == []


def test_canon_consumed_relationship_with_wrong_project_endpoint_is_rejected(client):
    from app.models import Chapter, Relationship

    pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    a = client.post(f"/api/v1/projects/{pid_a}/characters", json={"name": "A인물"}).json()
    b = client.post(f"/api/v1/projects/{pid_b}/characters", json={"name": "B인물"}).json()
    db = _db(client)
    db.add(Relationship(from_character_id=a["id"], to_character_id=b["id"], label="깨진 관계", note="타작품 endpoint"))
    db.commit()
    chapter = db.get(Chapter, chapter_a["id"])
    payload = CanonCheckRequest(chapter_id=chapter_a["id"], include_relationships=True)
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(db, request_from_canon(payload, chapter))
    assert exc.value.status_code == 422
```

- [ ] **Step 4: Run focused tests and verify RED**

Run from native Windows PowerShell:

```powershell
cd C:\Users\wj941\Documents\jippeel
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:DATABASE_URL = "sqlite:///$env:TEMP/jippeel-ai-context-task1-red-$PID.db"
$env:JIPPEEL_ALLOW_TEMP_CREATE_ALL = "1"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_context_bundle.py -q
```

Expected: collection fails because `app.services.ai_context` does not exist and schemas do not yet contain the new fields.

- [ ] **Step 5: Add schema fields with validation**

In `backend/app/schemas.py` near `EpisodeBrief`, `GenerateContext`, `ParallelScenePlan`, and `CanonCheckRequest`, add:

```python
EpisodePurpose = Literal["serial", "volume_end", "series_finale"]
class EpisodeBrief(BaseModel):
    emotion_goal: BriefText
    core_events: list[BriefText] = Field(min_length=1, max_length=3)
    character_choices: list[BriefText] = Field(min_length=1, max_length=4)
    cost: BriefText
    prohibitions: list[BriefText] = Field(min_length=1, max_length=10)
    next_hook: BriefText | None = None
    ending_intent: BriefText | None = None
    scene_type: Literal["대립", "액션", "정보정리", "감정", "이동"] | None = None
    target_chars_novelpia: int | None = Field(default=None, ge=1000, le=10000)
```

Add these fields to `GenerateContext`:

```python
include_chapter_content: bool = True
expected_revision: int | None = Field(default=None, ge=0)
episode_purpose: EpisodePurpose = "serial"
approved_foreshadow_ids: list[int] = Field(default_factory=list, max_length=20)
include_relationships: bool = False
```

Add a `@model_validator(mode="after")` on `GenerateContext`:

```python
@model_validator(mode="after")
def validate_context_contract(self):
    if self.expected_revision is not None and self.chapter_id is None:
        raise ValueError("expected_revision requires chapter_id")
    if self.brief is not None:
        has_hook = bool(self.brief.next_hook)
        has_ending = bool(self.brief.ending_intent)
        if self.episode_purpose == "serial" and not has_hook:
            raise ValueError("serial brief requires next_hook")
        if self.episode_purpose == "volume_end" and not (has_hook or has_ending):
            raise ValueError("volume_end brief requires next_hook or ending_intent")
        if self.episode_purpose == "series_finale" and not has_ending:
            raise ValueError("series_finale brief requires ending_intent")
    return self
```

Extend `CanonCheckRequest` additively:

```python
class CanonCheckRequest(BaseModel):
    chapter_id: int
    expected_revision: int | None = Field(default=None, ge=0)
    episode_purpose: EpisodePurpose = "serial"
    approved_foreshadow_ids: list[int] = Field(default_factory=list, max_length=20)
    include_relationships: bool = False
```

- [ ] **Step 6: Implement `backend/app/services/ai_context.py`**

Create the module with these public dataclasses and functions. The implementation can use helper functions, but callers must only need the listed public functions.

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, Character, Foreshadow, LoreEntry, Project, Relationship, Scene, VolumeNote
from app.schemas import CanonCheckRequest, EpisodeBrief, GenerateRequest
from app.services import injection

ContextTarget = Literal["generate", "canon"]
EpisodePurpose = Literal["serial", "volume_end", "series_finale"]
@dataclass(frozen=True)
class ContextBundleRequest:
    target: ContextTarget
    project_id: int | None
    chapter_id: int | None
    include_chapter_content: bool
    expected_revision: int | None
    scene_id: int | None
    character_ids: list[int]
    lore_ids: list[int]
    auto_lore: bool
    auto_lore_limit: int
    auto_lore_semantic: bool
    previous_chapter: bool
    auto_outline: bool
    auto_foreshadow: bool
    auto_foreshadow_limit: int
    style_profile: bool
    brief: EpisodeBrief | None
    prompt_text: str | None
    episode_purpose: EpisodePurpose
    approved_foreshadow_ids: list[int]
    include_relationships: bool

@dataclass(frozen=True)
class ContextBundle:
    project_id: int | None
    chapter_id: int | None
    chapter_revision: int | None
    episode_purpose: EpisodePurpose
    blocks: list[str]
    style_profile_text: str | None
    metadata: dict
    source_text: str
```

Required implementation behavior:

```python
def request_from_generate(payload: GenerateRequest) -> ContextBundleRequest:
    ctx = payload.context
    instruction = payload.prompt_override or ""
    return ContextBundleRequest(
        target="generate",
        project_id=ctx.project_id,
        chapter_id=ctx.chapter_id,
        include_chapter_content=ctx.include_chapter_content,
        expected_revision=ctx.expected_revision,
        scene_id=ctx.scene_id,
        character_ids=list(ctx.character_ids or []),
        lore_ids=list(ctx.lore_ids or []),
        auto_lore=ctx.auto_lore,
        auto_lore_limit=ctx.auto_lore_limit,
        auto_lore_semantic=ctx.auto_lore_semantic,
        previous_chapter=ctx.previous_chapter,
        auto_outline=ctx.auto_outline,
        auto_foreshadow=ctx.auto_foreshadow,
        auto_foreshadow_limit=ctx.auto_foreshadow_limit,
        style_profile=ctx.style_profile,
        brief=ctx.brief,
        prompt_text=instruction,
        episode_purpose=ctx.episode_purpose,
        approved_foreshadow_ids=list(ctx.approved_foreshadow_ids or []),
        include_relationships=ctx.include_relationships,
    )
```

For `request_from_canon(payload, chapter)`, set:

```python
target="canon"
project_id=chapter.project_id
chapter_id=chapter.id
include_chapter_content=True
expected_revision=payload.expected_revision
scene_id=None
character_ids=[]
lore_ids=[]
auto_lore=False
auto_outline=False
auto_foreshadow=True
style_profile=False
brief=None
prompt_text=None
episode_purpose=payload.episode_purpose
approved_foreshadow_ids=list(payload.approved_foreshadow_ids or [])
include_relationships=payload.include_relationships
```

`build_context_bundle()` must:

- Resolve project from explicit `project_id`, `chapter_id`, and `scene_id`.
- Reject mismatches with `HTTPException(status_code=422, detail="...")`.
- Check `expected_revision` against `Chapter.revision` and raise the existing preservation-compatible 409 detail object with `code="revision_conflict"`, `current_revision`, and the stable existing helper if available.
- Include current chapter body only when `include_chapter_content` is true.
- Still use the current chapter for previous chapter, outline, volume note, auto lore source, auto foreshadow, style profile, and metadata when `include_chapter_content` is false.
- Preserve the existing caps:
  - previous chapter tail: 2,000 chars for generation, 1,000 chars for canon if canon keeps its shorter cap internally.
  - volume fields: 400 chars.
  - next chapter memo: 600 chars.
  - foreshadow content: 400 chars.
- Preserve deterministic ordering and included-ID metadata.
- When generation relationship inclusion is enabled with zero or one selected same-project character, return no relationship block and `included_relationship_ids: []`, not an error.
- Validate every consumed relationship endpoint belongs to the resolved project; reject missing or cross-project endpoints instead of fabricating names.

- [ ] **Step 7: Wire single and parallel generation to the bundle**

In `backend/app/routers/ai_panel.py`:

- Build and validate the `ContextBundle` before `llm.make_client()` or any provider await.
- For `/ai/generate-parallel`, validate the bundle before planner client creation and before `complete_chat()`.
- Keep `_build_messages(payload, db)` as a local adapter.
- Replace `_build_context_blocks()` internals with the bundle call or remove it if no tests import it.
- Build `context_text` from `bundle.blocks`.
- Task 1 builds the system prompt from existing `NOVEL_SYSTEM_PROMPT` and `bundle.style_profile_text` only. Do not call or implement `purpose_directive()` in Task 1. Task 2 owns that function, its wiring in every phase, and all purpose-specific prompt removals/changes. Task 1 may reserve schema/metadata fields, but its prompt behavior stays serial-compatible until Task 2; no intermediate deployment is allowed.
- Return metadata from `_build_messages()`:

```python
return "default", messages, injected_lore, injected_outline, injected_foreshadows, bundle.metadata
```

Keep existing `start` data fields and add `context_metadata`:

```python
yield {"event": "start", "data": json.dumps({
    "model": model,
    "injected_lore": injected_lore,
    "injected_outline": injected_outline,
    "injected_foreshadows": injected_foreshadows,
    "review_enabled": review_cfg is not None,
    "context_metadata": context_metadata,
}, ensure_ascii=False)}
```

Do the same add-only field for `parallel_start`.

- [ ] **Step 7a: Add intercepted-message regression for baseline Probe C**

In `backend/tests/test_ai_generate_stream.py`, add a test using the existing `parallel_llm` fixture. It must prove `style_profile` reaches planner, both workers, and parallel reviewer, not only single generation:

```python
def test_parallel_context_includes_style_profile_in_all_phases_probe_c(client, parallel_llm):
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "medium", "base_url": "http://x/v1", "default_model": "medium-model", "reasoning_effort": "medium",
    }).json()
    pid = client.post("/api/v1/projects", json={"title": "STYLE_PROJECT"}).json()["id"]
    client.patch(f"/api/v1/projects/{pid}", json={"style_profile": "STYLE_TOKEN_PROJECT_A — hardboiled terse rhythm"})
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "STYLE_CHAPTER", "sort_order": 1}).json()
    client.put(f"/api/v1/chapters/{ch['id']}/content", json={"content_md": "STYLE_CHAPTER_BODY", "expected_revision": 0})
    payload = _parallel_payload(ep["id"])
    payload["context"] = {"project_id": pid, "chapter_id": ch["id"], "style_profile": True}

    response = client.post("/api/v1/ai/generate-parallel", json=payload)
    assert response.status_code == 200, response.text

    all_calls = parallel_llm["complete_calls"] + parallel_llm["stream_calls"]
    assert len(all_calls) >= 4
    for call in all_calls:
        combined = "\n".join(m["content"] for m in call["messages"])
        assert "STYLE_TOKEN_PROJECT_A" in combined
        assert "STYLE_CHAPTER_BODY" in combined
```

- [ ] **Step 8: Wire canon to the bundle without changing mutation behavior**

In `backend/app/services/canon.py`:

- Change `build_messages(db, chapter)` to accept the request or a bundle:

```python
def build_messages(db: Session, chapter: Chapter, payload: CanonCheckRequest | None = None) -> tuple[list[dict], dict]:
```

- Existing tests that call without `payload` must still work by creating a default `CanonCheckRequest(chapter_id=chapter.id)`.
- Capture immutable `checked_input_body = chapter.content_md or ""`, `checked_input_revision = chapter.revision`, and `checked_input_hash = sha256(checked_input_body.encode("utf-8")).hexdigest()` before awaiting the provider.
- Use `ContextBundle.metadata` as the returned context JSON base and add `checked_input_revision` plus `checked_input_hash`.
- Keep `run_canon_check()` returning `(issues, counts, model)`.
- Do not mutate manuscript/canon state except existing `CanonRun` creation in the router.
- Return `checked_context` with the captured revision/hash so result labels and history stay bound to the original input even if the chapter changes while the provider runs.

In `backend/app/routers/quality.py`, build/validate the canon bundle and capture immutable input revision/hash before `resolve_endpoint(db)` and before `llm.make_client()`. Pass the request payload or bundle to `canon_service.run_canon_check()`.

- [ ] **Step 9: Run focused tests and verify GREEN**

Run:

```powershell
cd C:\Users\wj941\Documents\jippeel
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:DATABASE_URL = "sqlite:///$env:TEMP/jippeel-ai-context-task1-green-$PID.db"
$env:JIPPEEL_ALLOW_TEMP_CREATE_ALL = "1"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_context_bundle.py backend\tests\test_ai_generate_stream.py::test_generate_streams_deltas backend\tests\test_foreshadows_canon.py::test_canon_check_success -q
```

Expected: all listed tests pass. Existing `test_generate_streams_deltas` still sees chapter body for legacy `chapter_id`.

- [ ] **Step 10: Review gate for Task 1**

Reviewer checks:

- No provider client creation, endpoint resolution, or provider await occurs before ownership/revision validation; the 409/422 monkeypatch tests prove this for generation and canon.
- Existing SSE field names are not removed.
- `ContextBundle` is a deep module: routers do not reimplement ownership checks.
- No public relationship scope field/type was added; generation uses selected-character policy and canon uses all same-project policy.
- No production DB, migration, or frontend file changed in Task 1.
- `backend/app/services/parallel_writer.py` ordering/cancellation has not changed in Task 1.

---

### Task 2: Backend purpose, payoff, brief, parallel, canon, and local quality rules

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/services/ai_context.py`
- Modify: `backend/app/routers/ai_panel.py`
- Modify: `backend/app/services/canon.py`
- Modify: `backend/app/services/quality.py`
- Modify: `backend/app/routers/quality.py`
- Modify: `backend/app/services/parallel_writer.py`
- Test: `backend/tests/test_ai_context_directives.py`
- Test: `backend/tests/test_parallel_writer.py`
- Test: `backend/tests/test_parallel_quality.py`
- Test: `backend/tests/test_quality.py`
- Test: `backend/tests/test_foreshadows_canon.py`
- Test: `backend/tests/test_ai_generate_stream.py`

**Interfaces:**
- Consumes Task 1 `ContextBundle` and metadata.
- Produces purpose-specific prompt directive text through `purpose_directive(purpose)`.
- Produces purpose-specific brief validation in `GenerateContext`.
- Produces `parse_parallel_plan(raw: str, episode_purpose: EpisodePurpose = "serial") -> ParallelPlan` in `backend/app/services/parallel_writer.py`.
- Produces `quality.analyze_chapter(text: str, episode_purpose: EpisodePurpose = "serial") -> dict`.
- Produces `quality.score_and_suggest(metrics: dict, episode_purpose: EpisodePurpose = "serial") -> tuple[int, list[str], list[str]]`.

- [ ] **Step 1: Write failing tests for brief purpose validation**

Create `backend/tests/test_ai_context_directives.py`:

```python
import json

import pytest

from tests.test_ai_generate_stream import _parse_sse


def _endpoint(client):
    return client.post("/api/v1/ai/endpoints", json={"name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()


def _base_brief(**extra):
    data = {
        "emotion_goal": "불안을 끝내는 안도감",
        "core_events": ["황궁 지하 문을 연다"],
        "character_choices": ["주인공은 복수보다 구출을 택한다"],
        "cost": "왕좌를 포기한다",
        "prohibitions": ["새 흑막을 만들지 않는다"],
    }
    data.update(extra)
    return data


def test_serial_brief_requires_next_hook(client, fake_llm):
    ep = _endpoint(client)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "이어 써줘",
        "context": {"episode_purpose": "serial", "brief": _base_brief()},
    })
    assert resp.status_code == 422


def test_series_finale_brief_accepts_ending_intent_without_next_hook(client, fake_llm):
    ep = _endpoint(client)
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "완결 장면을 써줘",
        "context": {"episode_purpose": "series_finale", "brief": _base_brief(ending_intent="주인공이 선택의 대가를 받아들이고 시리즈 갈등을 닫는다")},
    })
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "결말 의도" in user_text
    assert "주인공이 선택의 대가" in user_text
```

- [ ] **Step 2: Write failing tests for purpose prompt contradictions**

Append:

```python
@pytest.mark.parametrize("purpose, must_contain, must_not_contain", [
    ("serial", "연재화 목적", "무조건 갈등을 다 풀지 마라"),
    ("volume_end", "권말 목적", "훅이 없어도 장면의 긴장이 완전히 풀리기 전에 끝낸다"),
    ("series_finale", "최종화 목적", "갈등을 다 풀지 마라"),
])
def test_generation_system_prompt_is_purpose_aware(client, fake_llm, purpose, must_contain, must_not_contain):
    ep = _endpoint(client)
    context = {"episode_purpose": purpose}
    if purpose == "serial":
        context["brief"] = _base_brief(next_hook="문밖의 발소리로 넘긴다")
    elif purpose == "volume_end":
        context["brief"] = _base_brief(ending_intent="권의 감정선을 닫고 다음 권 질문만 남긴다")
    else:
        context["brief"] = _base_brief(ending_intent="시리즈 핵심 갈등을 닫는다")
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "써줘", "context": context,
    })
    assert resp.status_code == 200
    sys_text = fake_llm["client"].last_kwargs["messages"][0]["content"]
    assert must_contain in sys_text
    assert must_not_contain not in sys_text
    assert "최종화 문학성 점수" not in sys_text
```

- [ ] **Step 3: Write failing tests for approved/unapproved payoff semantics and wrong project rejection**

Append:

```python
def _project_chapter(client, title):
    pid = client.post("/api/v1/projects", json={"title": title}).json()["id"]
    chapter = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화", "sort_order": 1}).json()
    return pid, chapter


def test_approved_foreshadow_block_allows_this_request_only(client, fake_llm):
    ep = _endpoint(client)
    pid, chapter = _project_chapter(client, "P")
    fs = client.post(f"/api/v1/projects/{pid}/foreshadows", json={
        "title": "검의 진짜 주인", "content": "검은 타인의 것이다", "status": "설치",
    }).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"],
        "prompt_override": "이번 화에서 검의 진실을 밝혀줘",
        "context": {"project_id": pid, "chapter_id": chapter["id"], "approved_foreshadow_ids": [fs["id"]], "auto_foreshadow": True},
    })
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "[이번 요청에서 회수/공개 허용된 복선: 검의 진짜 주인]" in user_text
    assert "상태값은 자동 변경하지 마라" in user_text
    after = client.get(f"/api/v1/projects/{pid}/foreshadows").json()[0]
    assert after["status"] == "설치"
    assert after["audience_knows"] is False


def test_wrong_project_approved_foreshadow_rejected_before_llm(client, fake_llm):
    ep = _endpoint(client)
    pid_a, chapter_a = _project_chapter(client, "A")
    pid_b, _chapter_b = _project_chapter(client, "B")
    fs_b = client.post(f"/api/v1/projects/{pid_b}/foreshadows", json={"title": "타작품 복선"}).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "써줘",
        "context": {"project_id": pid_a, "chapter_id": chapter_a["id"], "approved_foreshadow_ids": [fs_b["id"]]},
    })
    assert resp.status_code == 422
    assert fake_llm["client"].last_kwargs is None or "타작품 복선" not in str(fake_llm["client"].last_kwargs)
```

- [ ] **Step 4: Write failing tests for local quality purpose rules**

Modify `backend/tests/test_quality.py`:

```python
def test_series_finale_does_not_penalize_missing_hook():
    text = "모든 싸움이 끝났다. 그는 검을 내려놓았다.\n\n문은 닫혔고, 남은 사람들은 서로를 바라보았다."
    serial = analyze_chapter(text, episode_purpose="serial")
    finale = analyze_chapter(text, episode_purpose="series_finale")
    assert serial["metrics"]["hook_score_applicable"] is True
    assert finale["metrics"]["hook_score_applicable"] is False
    assert finale["score"] >= serial["score"]
    assert "장 끝 후크" in serial["suggested_preset_names"]
    assert "장 끝 후크" not in finale["suggested_preset_names"]
    assert not any("다음 화" in s and "클릭" in s for s in finale["suggestions"])


def test_quality_history_dedup_includes_purpose_not_hash(client):
    pid = client.post("/api/v1/projects", json={"title": "P"}).json()["id"]
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "완결", "sort_order": 99}).json()
    client.put(f"/api/v1/chapters/{ch['id']}/content", json={"content_md": "끝났다. 그는 웃었다.", "expected_revision": 0})
    assert client.get(f"/api/v1/chapters/{ch['id']}/quality?episode_purpose=serial").status_code == 200
    assert client.get(f"/api/v1/chapters/{ch['id']}/quality?episode_purpose=serial").status_code == 200
    assert client.get(f"/api/v1/chapters/{ch['id']}/quality?episode_purpose=series_finale").status_code == 200
    rows = client.get(f"/api/v1/chapters/{ch['id']}/quality/history").json()
    purposes = [row["metrics_json"]["episode_purpose"] for row in rows]
    assert sorted(purposes) == ["serial", "series_finale"]
```

If `QualityCheckOut` currently does not expose `metrics_json`, add it to `backend/app/schemas.py` only if the existing model already contains it. Do not create a migration.

- [ ] **Step 5: Write failing tests for parallel purpose validation**

Modify `backend/tests/test_parallel_writer.py`:

```python
from app.services.parallel_writer import validate_plan_for_purpose


def test_parallel_serial_requires_closing_hook():
    p1 = valid_scene(1).model_copy(update={"closing_hook": None})
    p2 = valid_scene(2)
    plan = ParallelPlan(scenes=[p1, p2])
    with pytest.raises(ValueError, match="closing_hook"):
        validate_plan_for_purpose(plan, "serial")


def test_parallel_series_finale_allows_ending_intent_on_final_scene():
    p1 = valid_scene(1).model_copy(update={"closing_hook": "마지막 선택으로 이어진다"})
    p2 = valid_scene(2).model_copy(update={"closing_hook": None, "ending_intent": "두 인물이 작별하며 시리즈 갈등을 닫는다"})
    plan = ParallelPlan(scenes=[p1, p2])
    validate_plan_for_purpose(plan, "series_finale")


def test_parallel_series_finale_rejects_legacy_hook_only_final_scene():
    p1 = valid_scene(1).model_copy(update={"closing_hook": "마지막 선택으로 이어진다"})
    p2 = valid_scene(2).model_copy(update={"closing_hook": "다음 사건처럼 보이는 문장", "ending_intent": None})
    plan = ParallelPlan(scenes=[p1, p2])
    with pytest.raises(ValueError, match="final scene requires ending_intent"):
        validate_plan_for_purpose(plan, "series_finale")
```

- [ ] **Step 6: Run focused tests and verify RED**

Run:

```powershell
cd C:\Users\wj941\Documents\jippeel
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:DATABASE_URL = "sqlite:///$env:TEMP/jippeel-ai-context-task2-red-$PID.db"
$env:JIPPEEL_ALLOW_TEMP_CREATE_ALL = "1"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_context_directives.py backend\tests\test_quality.py::test_series_finale_does_not_penalize_missing_hook backend\tests\test_parallel_writer.py::test_parallel_serial_requires_closing_hook -q
```

Expected: failures for missing purpose directives, old required `next_hook`, missing `ending_intent`, and old quality hook behavior.

- [ ] **Step 7: Implement purpose directive text and brief formatting**

In `backend/app/services/ai_context.py`, implement:

```python
def purpose_directive(purpose: EpisodePurpose) -> str:
    if purpose == "volume_end":
        return (
            "[권말 목적]\n"
            "- 이 화는 권의 감정선·사건선을 닫는 회차다.\n"
            "- 다음 권 질문은 작가가 준 경우에만 남긴다.\n"
            "- 결말 의도가 있으면 억지 cliffhanger보다 closure를 우선한다."
        )
    if purpose == "series_finale":
        return (
            "[최종화 목적]\n"
            "- 이 화는 시리즈 핵심 갈등과 감정선을 닫는 회차다.\n"
            "- 작가가 명시하지 않은 새 sequel hook을 만들지 않는다.\n"
            "- 해결된 결말을 약점으로 보지 않는다. 최종화 문학성 점수 같은 별도 점수는 만들지 않는다."
        )
    return (
        "[연재화 목적]\n"
        "- 이 화는 다음 회차로 이어지는 연재화다.\n"
        "- next_hook이 있으면 그 방향으로 끝낸다.\n"
        "- 단, 모든 갈등을 일부러 미완으로 남기라는 뜻은 아니다."
    )
```

Update brief formatting so it uses labels:

```python
if brief.next_hook:
    lines.append(f"다음 화 훅: {brief.next_hook}")
if brief.ending_intent:
    lines.append(f"결말 의도: {brief.ending_intent}")
```

- [ ] **Step 8: Remove unconditional hook and unresolved directives from prompts**

In `backend/app/routers/ai_panel.py` constants:

- Remove the serial-only phrases from global `NOVEL_SYSTEM_PROMPT`:
  - `훅이 없어도 장면의 긴장이 완전히 풀리기 전에 끝낸다`
  - `갈등을 다 풀지 마라. 해결은 다음 화에 남긴다.`
- Replace them with purpose-neutral wording:

```python
"- 결말 방식은 [연재화 목적]/[권말 목적]/[최종화 목적] 블록과 브리프의 next_hook 또는 ending_intent를 따른다.\n"
```

- In review prompts, replace unconditional platform hook wording with:

```python
"- 플랫폼/목적: episode_purpose에 맞는 마무리인지. serial은 다음 화 압력, volume_end는 권 단위 closure, series_finale는 시리즈 closure를 본다.\n"
```

Keep `[감수]` and `[수정본]` markers unchanged for single review.

- [ ] **Step 9: Implement approved payoff and future-reference labels**

In `ai_context.build_context_bundle()`:

- Validate all consumed foreshadow rows exist, belong to the resolved project, and have same-project `planted_chapter_id`/`resolved_chapter_id` references when those references are present.
- Explicit approval rows are always consumed and included even when `auto_foreshadow=false` or `auto_foreshadow_limit` would omit them.
- When an approved ID is also in auto foreshadow rows, render the approved block once and do not render the unapproved block for the same ID.
- Approval remains scoped only to listed IDs.
- Future `planted_chapter_id` means the clue is not-yet-fact for this chapter.
- Future `resolved_chapter_id` does not make an already planted clue nonexistent; retain the planted clue as current record and label only the resolution as future plan.
- Approved future plan may be realized by author permission, but it must not be asserted as preexisting fact.
- Set `metadata["approved_foreshadow_ids"]` in caller order after validation.
- Set `metadata["future_reference_foreshadow_ids"]` in ascending ID order.



- [ ] **Step 10a: Write canon immutable-input regression**

Add to `backend/tests/test_foreshadows_canon.py` a regression that changes the chapter while the provider is awaiting and proves the stored run remains bound to the original input:

```python
def test_canon_run_records_checked_input_revision_and_hash_before_provider(client, monkeypatch, chapter):
    import hashlib
    import json
    from app.routers import quality as quality_router
    from tests.test_bootstrap_api import _Response

    original_text = "ORIGINAL_CANON_INPUT"
    changed_text = "CHANGED_AFTER_PROVIDER_STARTED"
    client.put(f"/api/v1/chapters/{chapter['id']}/content", json={"content_md": original_text, "expected_revision": 0})
    saved = client.get(f"/api/v1/chapters/{chapter['id']}").json()
    holder = {"entered": False}

    class _Completions:
        async def create(self, **kwargs):
            holder["entered"] = True
            # Simulate external concurrent update after canon captured the input.
            db = next(iter(client.app.dependency_overrides[quality_router.get_db]()))
            row = db.get(quality_router.Chapter, chapter["id"])
            row.content_md = changed_text
            row.revision += 1
            db.commit()
            return _Response(json.dumps({"issues": []}, ensure_ascii=False))

    class _FakeClient:
        def __init__(self):
            self.chat = type("NS", (), {"completions": _Completions()})()

    monkeypatch.setattr(quality_router.llm, "make_client", lambda *a, **k: _FakeClient())
    client.post("/api/v1/ai/endpoints", json={"name": "e", "base_url": "http://x/v1", "default_model": "m", "is_default": True})
    resp = client.post("/api/v1/canon-check", json={"chapter_id": chapter["id"], "expected_revision": saved["revision"]})
    assert resp.status_code == 200
    ctx = resp.json()["checked_context"]
    assert ctx["checked_input_revision"] == saved["revision"]
    assert ctx["checked_input_hash"] == hashlib.sha256(original_text.encode("utf-8")).hexdigest()
```

- [ ] **Step 10: Implement canon approved payoff semantics**

In `backend/app/services/canon.py`:

- Include the purpose directive and approved foreshadow block in canon messages.
- Add canon system text:

```python
"작가가 이번 요청에서 회수/공개 허용한 복선 ID는 그 공개 자체만으로 미회수 복선 오류로 판정하지 않는다. 그러나 다른 설정·관계·세계관 모순은 계속 지적한다."
```

- Do not mutate foreshadow rows.
- Store bundle metadata in `CanonRun.context_json` through the existing `counts` return value.

- [ ] **Step 11: Implement local quality purpose behavior**

In `backend/app/services/quality.py`:

```python
def analyze_text(text: str, episode_purpose: EpisodePurpose = "serial") -> dict:
    ...
    metrics["episode_purpose"] = episode_purpose
    metrics["hook_score_applicable"] = episode_purpose == "serial"
```

In `score_and_suggest()`:

```python
if episode_purpose == "serial" and not metrics.get("hook_present", False):
    penalty += 20
    suggestions.append("마지막 300자에 후크(질문·위기·반전 시그널)가 없습니다 — 다음 화를 클릭하게 만드는 문장으로 끝내세요.")
    presets.append("장 끝 후크")
elif episode_purpose == "volume_end" and not metrics.get("hook_present", False):
    suggestions.append("권말 회차입니다. 다음 화 훅보다 권의 감정선·사건선이 닫혔는지 확인하세요.")
elif episode_purpose == "series_finale":
    suggestions.append("최종화 목적입니다. 후크 점수는 적용하지 않고 결말 의도와 설정 정합성을 사람이 확인하세요.")
```

In `backend/app/routers/quality.py`:

- Add query `episode_purpose: EpisodePurpose = "serial"`.
- Pass it to `quality_service.analyze_chapter(text, episode_purpose=episode_purpose)`.
- Dedupe with:

```python
last_purpose = (last.metrics_json or {}).get("episode_purpose") if last else None
if last is None or last.content_hash != content_hash or last_purpose != episode_purpose:
    db.add(QualityCheck(...))
```

- [ ] **Step 12: Implement parallel scene purpose validation**

In `backend/app/services/parallel_writer.py` add internal validation and expose it through `parse_parallel_plan(raw, episode_purpose="serial")`. Keep `validate_plan_for_purpose()` importable for focused tests if useful:

```python
def validate_plan_for_purpose(plan: ParallelPlan, purpose: str) -> None:
    scenes = sorted(plan.scenes, key=lambda s: s.order)
    if purpose == "serial":
        missing = [s.order for s in scenes if not s.closing_hook]
        if missing:
            raise ValueError(f"serial scenes require closing_hook: {missing}")
        return
    if purpose == "volume_end":
        missing = [s.order for s in scenes if not (s.closing_hook or s.ending_intent)]
        if missing:
            raise ValueError(f"volume_end scenes require closing_hook or ending_intent: {missing}")
        return
    if purpose == "series_finale":
        missing = [s.order for s in scenes if not (s.closing_hook or s.ending_intent)]
        if missing:
            raise ValueError(f"series_finale scenes require closing_hook or ending_intent: {missing}")
        if not scenes[-1].ending_intent:
            raise ValueError("series_finale final scene requires ending_intent")
        return
    raise ValueError(f"unknown episode_purpose: {purpose}")
```

In `ai_panel.generate_parallel()`, call `parallel_writer.parse_parallel_plan(planner_raw, episode_purpose=bundle.episode_purpose)`. This applies purpose exceptions at parse time and before any worker starts. Old callers that call `parse_parallel_plan(raw)` keep `serial` behavior.

Update planner prompt shape to include both keys:

```text
각 장면에는 title, purpose, objective, choice, cost, required_beats, characters, opening_state, closing_hook, ending_intent를 포함하라. serial은 closing_hook을 채우고, series_finale의 마지막 장면은 ending_intent를 채워라.
```

- [ ] **Step 13: Run focused tests and verify GREEN**

Run:

```powershell
cd C:\Users\wj941\Documents\jippeel
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:DATABASE_URL = "sqlite:///$env:TEMP/jippeel-ai-context-task2-green-$PID.db"
$env:JIPPEEL_ALLOW_TEMP_CREATE_ALL = "1"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_context_directives.py backend\tests\test_ai_context_bundle.py backend\tests\test_quality.py backend\tests\test_parallel_writer.py backend\tests\test_parallel_quality.py backend\tests\test_foreshadows_canon.py -q
```

Expected: all listed tests pass.

- [ ] **Step 14: Review gate for Task 2**

Reviewer checks:

- `serial` legacy brief behavior is preserved by validation.
- `volume_end` and `series_finale` do not receive unconditional hook/unresolved instructions.
- No foreshadow status/audience/chapter fields are mutated by generation or canon.
- No final-episode literary score exists.
- Parallel ordering, cancellation, and `[감수]`/`[수정본]` contracts remain intact.
- Existing JSON columns, not a migration, store canon/quality provenance.

---

### Task 3: Frontend request snapshot, minimal shared controls, and current-chapter result origin safety

**Files:**
- Modify: `frontend/src/stores/aiPanelStore.ts`
- Modify: `frontend/src/components/panels/AiPanel.tsx`
- Modify: `frontend/src/components/editor/CanonDialog.tsx`
- Modify: `frontend/src/components/editor/QualityDialog.tsx`
- Modify: `frontend/src/pages/EditorPage.tsx`
- Modify: `frontend/src/lib/aiStream.ts`
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Consumes backend Task 1/2 fields: `project_id`, `chapter_id`, `include_chapter_content`, `expected_revision`, `episode_purpose`, `approved_foreshadow_ids`, `include_relationships`, `context_metadata`.
- Produces `AiContextDirectives` in `aiPanelStore.ts`.
- Produces `AiResultOrigin` in `aiPanelStore.ts`.
- Produces `getDirectives(projectId: number | null, chapterId: number | null) -> AiContextDirectives`.
- Produces `setDirectives(projectId, chapterId, patch)`.
- Produces `beginResult(origin: AiResultOrigin)` or updates `startStream(origin)`.
- Produces safe insertion guard based on `resultOrigin` and `editorStore` identity.

- [ ] **Step 1: Extend the store with current identity, directive map, and result origin**

In `frontend/src/stores/aiPanelStore.ts`, add types:

```ts
export type EpisodePurpose = 'serial' | 'volume_end' | 'series_finale';

export interface AiContextDirectives {
  episodePurpose: EpisodePurpose;
  approvedForeshadowIds: number[];
  includeRelationships: boolean;
}

export interface AiResultOrigin {
  projectId: number | null;
  chapterId: number | null;
  expectedRevision: number | null;
  includeChapterContent: boolean;
  startedAt: number;
}
```

Extend `contextSelection`:

```ts
projectId: number | null;
chapterId: number | null;
includeChapterContent: boolean;
```

Keep `includeChapter` as a temporary alias only if it is needed to reduce churn. The visible label must use `includeChapterContent`.

Add store methods:

```ts
setCurrentIdentity: (projectId: number | null, chapterId: number | null) => void;
getDirectives: (projectId: number | null, chapterId: number | null) => AiContextDirectives;
setDirectives: (projectId: number | null, chapterId: number | null, patch: Partial<AiContextDirectives>) => void;
setResultOrigin: (origin: AiResultOrigin | null) => void;
reserveAiStart: (kind: 'generate' | 'canon') => string | null; // null refuses a duplicate pending start
isAiStartCurrent: (token: string) => boolean;
clearAiStart: (token?: string) => void;
```

Pending-start lifecycle (implement in Task 3, not merely in tests):

- `reserveAiStart(kind)` returns `null` when a pending start already owns that operation; it must not replace the first token on a double-click.
- `aiPanelStore.close()` and its toggle-off path call `clearAiStart()` for their pending generation token before the existing stream abort. AiPanel's cancel control does the same even while flush is pending.
- `setCurrentIdentity()` invalidates pending starts with `clearAiStart()` when project/chapter actually changes. EditorPage route change/unmount also invalidates pending starts so leaving the editor without mounting another chapter cannot start a request later.
- CanonDialog close/unmount/cancel clears its owned token. It must not clear a newer token belonging to a reopened dialog or another request.
- Every failed or abandoned start releases only its own token via `clearAiStart(token)`. Recheck token and current navigation immediately before provider start; late callbacks never clear a newer request. Preserve the existing active-stream abort behavior separately.
- All body fields come from the pre-await copies plus saved identity/revision. No mutable directive/form reads are allowed after flush. Add delayed-flush browser tests: double-click, close, cancel, navigate away/back, and change controls while pending. The request is either cancelled or uses the original complete form, never a mixture.

Frontend brief parity is part of Task 3: add `ending_intent` to `EpisodeBriefState`, its empty defaults/reset, and the existing brief controls. Use `parseEpisodeBrief(brief: EpisodeBriefState, episodePurpose: EpisodePurpose = 'serial')`; apply the SPEC §5.2 required fields for serial/volume_end/series_finale before deciding incomplete/invalid. A filled finale brief with `ending_intent` and no `next_hook` must be sent, not silently dropped. Do not force a finale hook input. Test its captured outgoing body and preserve serial legacy validation.

The map key is:

```ts
function directiveKey(projectId: number | null, chapterId: number | null) {
  return `${projectId ?? 'none'}:${chapterId ?? 'none'}`;
}
```

Default directives:

```ts
const DEFAULT_DIRECTIVES: AiContextDirectives = {
  episodePurpose: 'serial',
  approvedForeshadowIds: [],
  includeRelationships: false,
};
```

- [ ] **Step 2: Synchronize current identity from the editor page**

In `frontend/src/pages/EditorPage.tsx`, import `useAiPanelStore` already exists. Add an effect near the existing editor context effects:

```tsx
useEffect(() => {
  useAiPanelStore.getState().setCurrentIdentity(Number.isFinite(pid) ? pid : null, chapterId);
}, [pid, chapterId]);
```

When chapter detail loads and `detail.data.project_id !== pid`, keep the existing error. Do not set AI identity to the mismatched detail.

- [ ] **Step 3: Build a saved request snapshot before stream start**

In `AiPanel.generate`, make it async through an inner function or `void (async () => { ... })()`.

Before building the body, reserve a token before awaiting flush. This prevents double-click duplicate provider starts and lets close/cancel/navigation invalidate pending work:

```ts
const startToken = store.reserveAiStart('generate');
if (startToken === null) return; // A pending start already owns this operation.
const currentProjectId = useEditorStore.getState().projectId;
const currentChapterId = useEditorStore.getState().chapterId;
// Capture ALL plain request-form data before the first await. Never retain live arrays.
const c = structuredClone(store.contextSelection);
const directives = structuredClone(store.getDirectives(currentProjectId, currentChapterId));
const parsedBriefSnapshot = parseEpisodeBrief(structuredClone(store.episodeBrief), directives.episodePurpose);
// Keep the existing invalid-brief warning/validation behavior, using this captured value.
const brief = parsedBriefSnapshot.ok ? structuredClone(parsedBriefSnapshot.brief) : null;
const settingsSnapshot = {
  generationMode: store.generationMode,
  endpointId: activeEndpoint.id,
  endpointTemperature: activeEndpoint.temperature,
  presetId: store.presetId,
  promptOverride: store.promptOverride.trim(),
  model: store.model,
  maxTokens: store.maxTokens,
  temperature: store.temperature,
  reviewPass: store.reviewPass,
  reviewEffort: store.reviewEffort,
  workerLimit: store.workerLimit,
  reviewEndpointId: reviewEndpoint?.id ?? activeEndpoint.id,
  parallelReviewModel: store.parallelReviewModel,
  parallelReviewEffort: store.parallelReviewEffort,
};
let expectedRevision: number | null = null;
let boundProjectId = currentProjectId;
let boundChapterId = currentChapterId;

if (currentProjectId !== null && currentChapterId !== null) {
  let flushed;
  try {
    flushed = await flushManuscriptDraft(currentProjectId, currentChapterId);
  } catch (e) {
    toast((e as Error).message, 'error');
    store.clearAiStart(startToken);
    return;
  }
  const after = useEditorStore.getState();
  if (!store.isAiStartCurrent(startToken) || after.projectId !== currentProjectId || after.chapterId !== currentChapterId) {
    toast('회차가 바뀌어 AI 요청을 시작하지 않았습니다.', 'warning');
    return;
  }
  expectedRevision = flushed.detail.revision;
  boundProjectId = flushed.detail.project_id;
  boundChapterId = flushed.detail.id;
}
```

Then build body context from the same token's settings snapshot. Do not read mutable generation settings again after the flush:

```ts
// c, brief, directives, and settingsSnapshot are the pre-await copies above.
context: {
  project_id: boundProjectId,
  chapter_id: boundChapterId,
  include_chapter_content: c.includeChapterContent,
  expected_revision: expectedRevision,
  episode_purpose: directives.episodePurpose,
  approved_foreshadow_ids: directives.approvedForeshadowIds,
  include_relationships: directives.includeRelationships,
  character_ids: c.includeCharacters ? c.characterIds : [],
  lore_ids: c.includeLore ? c.loreIds : [],
  auto_lore: c.autoLore,
  auto_lore_semantic: c.autoLoreSemantic,
  auto_outline: c.autoOutline,
  auto_foreshadow: c.autoForeshadow,
  scene_id: c.sceneId,
  style_profile: c.styleProfile,
  ...(brief ? { brief } : {}),
}
```

Before `stream(...)`, call:

```ts
store.startStream({
  projectId: boundProjectId,
  chapterId: boundChapterId,
  expectedRevision,
  includeChapterContent: c.includeChapterContent,
  startedAt: Date.now(),
});
```

If `startStream` signature is not changed, call `store.setResultOrigin(...)` immediately before the old `store.startStream()`.

- [ ] **Step 4: Add minimal controls in AiPanel**

In `ContextSection`, use `ctx.projectId` and `ctx.chapterId` instead of only `useEditorStore().chapterId` where request identity matters.

Change the checkbox label:

```tsx
<Checkbox
  label={`현재 회차 본문 포함${chapter.data ? ` (${chapter.data.title.trim() || `${volumeLabel(chapter.data.volume)} ${chapter.data.id}화`})` : ''}`}
  checked={ctx.includeChapterContent && ctx.chapterId !== null}
  disabled={ctx.chapterId === null}
  onChange={(e) => setContext({ includeChapterContent: e.target.checked })}
/>
```

Add purpose select:

```tsx
<Label htmlFor="ai-episode-purpose">회차 목적</Label>
<Select
  id="ai-episode-purpose"
  value={directives.episodePurpose}
  onChange={(e) => setDirectives(ctx.projectId, ctx.chapterId, { episodePurpose: e.target.value as EpisodePurpose })}
>
  <option value="serial">연재화</option>
  <option value="volume_end">권말</option>
  <option value="series_finale">최종화</option>
</Select>
```

Add relationship checkbox:

```tsx
<Checkbox
  label="선택 인물 관계 포함"
  checked={directives.includeRelationships}
  disabled={ctx.characterIds.length < 2}
  onChange={(e) => setDirectives(ctx.projectId, ctx.chapterId, { includeRelationships: e.target.checked })}
/>
```

Add approved foreshadow checkboxes using existing project foreshadow API:

```tsx
const foreshadows = useQuery({
  queryKey: ['ai-foreshadows', ctx.projectId],
  queryFn: () => api.get<Array<{ id: number; title: string; status: string }>>(`/projects/${ctx.projectId}/foreshadows?status_filter=설치`),
  enabled: ctx.projectId !== null,
});
```

Render:

```tsx
{(foreshadows.data ?? []).map((f) => (
  <Checkbox
    key={f.id}
    label={`이번 요청에서 회수/공개 허용: ${f.title}`}
    checked={directives.approvedForeshadowIds.includes(f.id)}
    onChange={(e) => {
      const next = e.target.checked
        ? [...directives.approvedForeshadowIds, f.id]
        : directives.approvedForeshadowIds.filter((id) => id !== f.id);
      setDirectives(ctx.projectId, ctx.chapterId, { approvedForeshadowIds: next });
    }}
  />
))}
```

- [ ] **Step 5: Add result origin guard to insertion and replacement**

In `ResultSection`, read `resultOrigin` from the store.

Add helper:

```ts
function resultMatchesCurrentEditor(origin: AiResultOrigin | null) {
  if (!origin || origin.projectId === null || origin.chapterId === null) return false;
  const editor = useEditorStore.getState();
  return editor.projectId === origin.projectId && editor.chapterId === origin.chapterId && editor.view !== null && editor.saveState !== 'conflict';
}
```

At the start of `insertAtEnd` and `replaceSelection`:

```ts
if (!resultMatchesCurrentEditor(useAiPanelStore.getState().resultOrigin)) {
  toast('AI 결과가 다른 회차에서 생성되어 현재 원고에 자동 삽입하지 않았습니다. 복사 후 직접 확인하세요.', 'warning');
  return;
}
```

Button disabled state:

```tsx
const canInsertHere = resultMatchesCurrentEditor(resultOrigin);
<Button disabled={!hasText || busy || readOnlyTab || !canInsertHere} ...>
```

Copy button remains unchanged except it stays enabled when `hasText && !busy`.

- [ ] **Step 6: Add CanonDialog and QualityDialog shared controls**

In `CanonDialog`, reserve a canon start token and flush the same editor chapter before provider work. Do not rely on a cached query revision alone.

```tsx
const runCanon = async () => {
  const token = useAiPanelStore.getState().reserveAiStart('canon');
  if (token === null) return;
  const before = useEditorStore.getState();
  if (before.projectId === null || before.chapterId === null || before.chapterId !== chapterId) {
    toast('현재 회차를 확인한 뒤 다시 실행하세요.', 'warning');
    useAiPanelStore.getState().clearAiStart(token);
    return;
  }
  const directives = structuredClone(useAiPanelStore.getState().getDirectives(before.projectId, before.chapterId));
  let flushed;
  try {
    flushed = await flushManuscriptDraft(before.projectId, before.chapterId);
  } catch (e) {
    toast((e as Error).message, 'error');
    useAiPanelStore.getState().clearAiStart(token);
    return;
  }
  const after = useEditorStore.getState();
  if (!useAiPanelStore.getState().isAiStartCurrent(token) || after.projectId !== before.projectId || after.chapterId !== before.chapterId) {
    toast('회차가 바뀌어 canon 검사를 시작하지 않았습니다.', 'warning');
    return;
  }
  // Use the directives captured before flush, never current mutable controls.
  return api.post<CanonCheckResponse>('/canon-check', {
    chapter_id: flushed.detail.id,
    expected_revision: flushed.detail.revision,
    episode_purpose: directives.episodePurpose,
    approved_foreshadow_ids: directives.approvedForeshadowIds,
    include_relationships: directives.includeRelationships,
  });
};
```

In `QualityDialog`, call:

```ts
api.get<ChapterQuality>(`/chapters/${chapterId}/quality?episode_purpose=${directives.episodePurpose}`)
```

Show hook applicability:

```tsx
<div className="flex justify-between">
  <dt className="text-muted-foreground">후크(끝 300자)</dt>
  <dd>{q.metrics.hook_score_applicable === false ? '해당 없음' : q.metrics.hook_present ? '있음' : '없음'}</dd>
</div>
```

- [ ] **Step 7: Fix local status-change hook warning copy**

In `EditorHeader` status change handler, when status becomes `완료`, read directives:

```ts
const purpose = useAiPanelStore.getState().getDirectives(pid, chapterId).episodePurpose;
const q = await api.get<{ metrics: { hook_present: boolean; hook_score_applicable?: boolean }; suggested_preset_names: string[] }>(
  `/chapters/${chapterId}/quality?record=false&episode_purpose=${purpose}`,
);
if (q.metrics.hook_score_applicable !== false && !q.metrics.hook_present) {
  toast('연재화 목적에서 후크 없이 완료 처리됩니다 — 마지막 문장을 "장 끝 후크" 프리셋으로 다듬을지 확인하세요.', 'warning');
}
```

Do not show that warning for `series_finale`.

- [ ] **Step 8: Parse context metadata from SSE add-only fields**

In `frontend/src/lib/aiStream.ts`, add optional handler fields if needed:

```ts
contextMetadata?: Record<string, unknown>;
```

Parse `parsed.context_metadata` in both `start` and `parallel_start`. Existing callers that ignore it continue to work.

- [ ] **Step 9: Run frontend build on Windows Node and verify GREEN**

Run:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npm run build
```

Expected: TypeScript build and Vite build pass using Windows `node_modules`.

- [ ] **Step 10: Run backend compatibility gates after frontend wiring**

Run:

```powershell
cd C:\Users\wj941\Documents\jippeel
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:DATABASE_URL = "sqlite:///$env:TEMP/jippeel-ai-context-task3-backend-$PID.db"
$env:JIPPEEL_ALLOW_TEMP_CREATE_ALL = "1"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_context_bundle.py backend\tests\test_ai_context_directives.py -q
```

Expected: backend contracts still pass.

- [ ] **Step 11: Review gate for Task 3**

Reviewer checks:

- `AiPanel` sends current identity even when current body inclusion is false.
- `AiPanel` flushes before generation and aborts on conflict/recovery/navigation mismatch.
- Result insertion/replacement is blocked for another chapter and for recovery/conflict locked editors; copy remains enabled.
- Directive state is in memory only and keyed by project/chapter.
- `CanonDialog` and `QualityDialog` use the same directive state.
- No new dependencies and no redesign.

---

### Task 4: Dedicated QA integration, deterministic provider evidence, and validation docs

**Files:**
- Create: `scripts/ai_context_fake_llm_server.py`
- Create: `scripts/ai_context_backend_fixture.py`
- Create: `frontend/playwright.ai-context.config.ts`
- Create: `frontend/e2e/ai-context-consistency.spec.ts`
- Create: `docs/audits/ai-context-consistency-validation.md`
- Modify only if needed for test matching: `frontend/playwright.ai-context.config.ts`

**Interfaces:**
- Consumes production backend/frontend from Tasks 1-3.
- Produces JSONL prompt log at `.eval_tmp/ai-context/provider-prompts.jsonl`.
- Produces backend fixture report at `.eval_tmp/ai-context/backend-fixture.json`.
- Produces Playwright trace/screenshot only on failure.
- Produces validation doc with exact commands and output excerpts.

- [ ] **Step 1: Create deterministic provider script**

Create `scripts/ai_context_fake_llm_server.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RESPONSES = {
    "planner": {"scenes": [
        {"order": 1, "title": "장면 1", "purpose": "닫을 갈등을 확인한다", "objective": "문 앞에 선다", "choice": "문을 연다", "cost": "왕좌를 포기한다", "required_beats": ["문을 연다"], "characters": ["한서윤"], "opening_state": "결전 직후", "closing_hook": "마지막 선택으로 이어진다", "ending_intent": None},
        {"order": 2, "title": "장면 2", "purpose": "시리즈 갈등을 닫는다", "objective": "구출을 끝낸다", "choice": "복수보다 구출을 택한다", "cost": "왕좌를 포기한다", "required_beats": ["구출한다"], "characters": ["한서윤", "강무진"], "opening_state": "문이 열린 뒤", "closing_hook": None, "ending_intent": "두 인물이 선택의 대가를 받아들이고 끝낸다"},
    ]},
    "draft": "AI_CONTEXT_DRAFT\n한서윤은 강무진의 손을 놓지 않았다.",
    "review": "[감수]\n- AI_CONTEXT_REVIEW 목적과 관계 맥락을 확인했다.",
}

class Handler(BaseHTTPRequestHandler):
    prompt_log: Path

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._json(200, {"data": [{"id": "ai-context-fake"}]})
        else:
            self._json(404, {"detail": "not found"})

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        messages = payload.get("messages") or []
        user = messages[-1].get("content", "") if messages else ""
        if "[병렬 Planner" in user:
            content = json.dumps(RESPONSES["planner"], ensure_ascii=False)
            kind = "planner"
        elif "[초안 원고]" in user or "감수" in (messages[0].get("content", "") if messages else ""):
            content = RESPONSES["review"]
            kind = "review"
        else:
            content = RESPONSES["draft"]
            kind = "draft"
        self.prompt_log.parent.mkdir(parents=True, exist_ok=True)
        with self.prompt_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": kind, "payload": payload}, ensure_ascii=False) + "\n")
        if payload.get("stream"):
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.end_headers()
            chunk = {"choices": [{"delta": {"content": content}, "finish_reason": None}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            self._json(200, {"choices": [{"message": {"content": content}}]})

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--prompt-log", required=True)
    args = parser.parse_args()
    Handler.prompt_log = Path(args.prompt_log)
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
```

- [ ] **Step 2: Create isolated backend fixture**

Create `scripts/ai_context_backend_fixture.py`. Use the structure from `scripts/preservation_backend_fixture.py`, but keep only what is needed:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOST = "127.0.0.1"


def root() -> Path:
    return Path(__file__).resolve().parents[1]


def require_windows_python(project_root: Path) -> None:
    if os.name != "nt":
        raise SystemExit("Use native Windows backend .venv Python for this fixture")
    expected = (project_root / "backend" / ".venv" / "Scripts").resolve()
    Path(sys.executable).resolve().relative_to(expected)


def free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex((HOST, port)) == 0:
            raise SystemExit(f"Port {port} is occupied")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-port", type=int, required=True)
    parser.add_argument("--provider-port", type=int, required=True)
    parser.add_argument("--json-report", required=True)
    parser.add_argument("--hold-server", action="store_true")
    args = parser.parse_args()
    project = root()
    require_windows_python(project)
    free(args.backend_port)
    free(args.provider_port)
    work = Path(tempfile.mkdtemp(prefix="jippeel-ai-context-"))
    db = work / "ai-context.db"
    prompt_log = work / "provider-prompts.jsonl"
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["DATABASE_URL"] = "sqlite:///" + db.as_posix()
    env["JIPPEEL_ALLOW_TEMP_CREATE_ALL"] = "1"
    provider = subprocess.Popen([sys.executable, str(project / "scripts" / "ai_context_fake_llm_server.py"), "--port", str(args.provider_port), "--prompt-log", str(prompt_log)], cwd=str(project), env=env)
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(args.backend_port)], cwd=str(project / "backend"), env=env)
    report = {"backend_port": args.backend_port, "provider_port": args.provider_port, "db": str(db), "prompt_log": str(prompt_log), "work_dir": str(work)}
    Path(args.json_report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        if args.hold_server:
            while True:
                time.sleep(1)
    finally:
        backend.terminate()
        provider.terminate()

if __name__ == "__main__":
    main()
```

This script must seed data through the HTTP API before Playwright uses it. Add seeding code in the same file after the backend health check:

- Create one project.
- Create two chapters with deterministic `sort_order`.
- Create two characters and one relationship.
- Create one lore row.
- Create one installed foreshadow.
- Create one default AI endpoint pointing to `http://127.0.0.1:{provider_port}/v1`.
- Write the created IDs into the JSON report.

Use `http.client` or Python standard library only. Do not add dependencies.

- [ ] **Step 3: Create dedicated Playwright config**

Create `frontend/playwright.ai-context.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: /ai-context-consistency\.spec\.ts/,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:15212',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 900 },
    locale: 'ko-KR',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: '..\\backend\\.venv\\Scripts\\python.exe ..\\scripts\\ai_context_backend_fixture.py --backend-port 18112 --provider-port 18113 --hold-server --json-report ..\\.eval_tmp\\ai-context\\backend-fixture.json',
      url: 'http://127.0.0.1:18112/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npx vite --host 127.0.0.1 --port 15212 --strictPort',
      url: 'http://127.0.0.1:15212',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
```

- [ ] **Step 4: Create Playwright integration test with prompt-log assertions**

Create `frontend/e2e/ai-context-consistency.spec.ts`:

```ts
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

function readReport() {
  const p = path.resolve('..', '.eval_tmp', 'ai-context', 'backend-fixture.json');
  return JSON.parse(fs.readFileSync(p, 'utf-8')) as {
    project_id: number;
    chapter_id: number;
    second_chapter_id: number;
    foreshadow_id: number;
    prompt_log: string;
  };
}

function readPrompts(promptLog: string) {
  return fs.readFileSync(promptLog, 'utf-8').trim().split('\n').map((line) => JSON.parse(line));
}

test.describe.serial('AI context consistency', () => {
  test('body opt-out still sends identity, purpose, relationship, and approved payoff', async ({ page }) => {
    const report = readReport();
    await page.goto(`/projects/${report.project_id}/write`);
    await expect(page.locator('.cm-content')).toBeVisible();
    await page.getByRole('button', { name: 'AI 패널' }).click();
    await page.getByLabel('프롬프트 직접 입력').fill('AI_CONTEXT_TEST 요청');
    await page.getByLabel(/현재 회차 본문 포함/).uncheck();
    await page.getByLabel('회차 목적').selectOption('series_finale');
    await page.getByLabel('선택 인물 관계 포함').check();
    await page.getByLabel(/이번 요청에서 회수\/공개 허용/).first().check();
    await page.getByRole('button', { name: '✨ 생성 시작' }).click();
    await expect(page.locator('pre')).toContainText('AI_CONTEXT_DRAFT', { timeout: 20_000 });

    const prompts = readPrompts(report.prompt_log);
    const joined = JSON.stringify(prompts);
    expect(joined).toContain('최종화 목적');
    expect(joined).toContain('이번 요청에서 회수/공개 허용된 복선');
    expect(joined).toContain('인물 관계');
    expect(joined).not.toContain('초기 서버 본문은 프롬프트에 없어야 한다');
  });

  test('result from another chapter cannot be inserted silently, but copy remains possible', async ({ page }) => {
    const report = readReport();
    await page.goto(`/projects/${report.project_id}/write`);
    await page.getByRole('button', { name: 'AI 패널' }).click();
    await page.getByLabel('프롬프트 직접 입력').fill('AI_CONTEXT_ORIGIN 요청');
    await page.getByRole('button', { name: '✨ 생성 시작' }).click();
    await expect(page.locator('pre')).toContainText('AI_CONTEXT_DRAFT', { timeout: 20_000 });

    await page.goto(`/projects/${report.project_id}/write?chapter=${report.second_chapter_id}`);
    await expect(page.locator('.cm-content')).toBeVisible();
    await expect(page.getByRole('button', { name: '⧉ 복사' })).toBeEnabled();
    await expect(page.getByRole('button', { name: '↪ 끼워넣기' })).toBeDisabled();
  });

  test('quality and canon use shared purpose without forced finale hook warning', async ({ page }) => {
    const report = readReport();
    await page.goto(`/projects/${report.project_id}/write`);
    await page.getByRole('button', { name: 'AI 패널' }).click();
    await page.getByLabel('회차 목적').selectOption('series_finale');
    await page.getByRole('button', { name: '품질 진단' }).click();
    await expect(page.getByText('해당 없음')).toBeVisible();
    await page.getByRole('button', { name: '모순 검사' }).click();
    await page.getByRole('button', { name: /검사 실행/ }).click();
    await expect(page.getByText(/검사 대상/)).toBeVisible({ timeout: 20_000 });
  });
});
```

If the router does not support `?chapter=` navigation, use the existing chapter selection UI in the test. Keep the test on dedicated ports.

- [ ] **Step 5: Run backend focused tests**

Run:

```powershell
cd C:\Users\wj941\Documents\jippeel
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:DATABASE_URL = "sqlite:///$env:TEMP/jippeel-ai-context-task4-backend-$PID.db"
$env:JIPPEEL_ALLOW_TEMP_CREATE_ALL = "1"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_context_bundle.py backend\tests\test_ai_context_directives.py backend\tests\test_quality.py backend\tests\test_parallel_writer.py backend\tests\test_parallel_quality.py backend\tests\test_foreshadows_canon.py backend\tests\test_ai_generate_stream.py -q
```

Expected: all pass.

- [ ] **Step 6: Run frontend build**

Run:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 7: Run dedicated Playwright integration**

Run:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.ai-context.config.ts
```

Expected: all `ai-context-consistency.spec.ts` tests pass. The prompt log exists and contains exact outbound prompts from the deterministic provider.

- [ ] **Step 8: Write validation doc**

Create `docs/audits/ai-context-consistency-validation.md` with:

```markdown
# AI Context Consistency Validation

- Date:
- Branch:
- Commit:
- Temp DB path:
- Backend port: 18112
- Frontend port: 15212
- Provider port: 18113
- Prompt log: `.eval_tmp/ai-context/provider-prompts.jsonl`

## Commands

```powershell
cd C:\Users\wj941\Documents\jippeel
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:DATABASE_URL = "sqlite:///$env:TEMP/jippeel-ai-context-task4-backend-$PID.db"
$env:JIPPEEL_ALLOW_TEMP_CREATE_ALL = "1"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_context_bundle.py backend\tests\test_ai_context_directives.py backend\tests\test_quality.py backend\tests\test_parallel_writer.py backend\tests\test_parallel_quality.py backend\tests\test_foreshadows_canon.py backend\tests\test_ai_generate_stream.py -q
```

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npm run build
npx playwright test --config playwright.ai-context.config.ts
```

## Evidence

- Backend focused tests:
- Frontend build:
- Playwright:
- Prompt-log assertions:

## Prompt-log facts checked

- `series_finale` prompt contains `최종화 목적`.
- Body opt-out prompt does not contain the current manuscript body.
- Prompt contains selected relationship block when opted in.
- Prompt contains approved payoff block only for approved ID.
- No prompt forces a cliffhanger for finale.

## Non-goals verified

- No foreshadow status/audience flags changed automatically.
- No production DB/WAL/SHM used.
- No port 8000 or 5173 used.
```

Fill every bullet with the actual output or path from the run. Do not claim pass without command output.

- [ ] **Step 9: Review gate for Task 4**

Reviewer checks:

- QA did not edit production source.
- Integration used temp DB, dedicated ports, deterministic local provider, and prompt logs.
- Prompt assertions inspect actual outbound provider payloads.
- No fake success assertion is used as proof.
- Validation doc contains real command output and artifact paths.

---

## Cross-task test matrix

| Area | Test file | Cases |
|---|---|---|
| Identity/body split | `backend/tests/test_ai_context_bundle.py` | legacy body include; opt-out body exclude; metadata identity |
| Ownership | `backend/tests/test_ai_context_bundle.py` | project/chapter mismatch; scene/chapter mismatch; wrong character; wrong lore; wrong approved foreshadow |
| Revision | `backend/tests/test_ai_context_bundle.py`, `frontend/e2e/ai-context-consistency.spec.ts` | stale generation revision; stale canon revision; UI flush abort |
| Purpose | `backend/tests/test_ai_context_directives.py`, `backend/tests/test_quality.py` | serial; volume_end; series_finale |
| Foreshadow payoff | `backend/tests/test_ai_context_directives.py`, `backend/tests/test_foreshadows_canon.py` | approved; unapproved; wrong project; cross-project referenced chapter |
| Relationships | `backend/tests/test_ai_context_bundle.py`, `frontend/e2e/ai-context-consistency.spec.ts` | generation includes selected endpoints only; 0/1 selected gives metadata 0; canon opt-in includes all same-project; corrupted endpoint ownership rejected |
| Parallel | `backend/tests/test_parallel_writer.py`, `backend/tests/test_parallel_quality.py`, `backend/tests/test_ai_generate_stream.py` | serial closing_hook; finale ending_intent; ordering; cancellation; review marker |
| Local quality | `backend/tests/test_quality.py`, `frontend/e2e/ai-context-consistency.spec.ts` | serial hook penalty; finale no hook penalty; history dedup by hash+purpose |
| UI safety | `frontend/e2e/ai-context-consistency.spec.ts` | body opt-out request; result origin mismatch insertion blocked; copy enabled |
| Real boundary | `scripts/ai_context_fake_llm_server.py`, Playwright | exact outbound prompt JSONL inspected |
| Baseline negative corpus | `docs/audits/ai-context-baseline-probes.md`, `backend/tests/test_ai_context_bundle.py`, `backend/tests/test_ai_generate_stream.py` | A1 wrong selected IDs rejected; A2 mixed explicit project rejected; B relationships included only when opted in; C style profile present in all parallel phases |

## Deferred work

- Full context-size optimization and token-budget engine.
- Persistent chapter directive/goals database.
- Historical state reconstruction.
- Separate reveal and payoff permission lists.
- Foreshadow CRUD repair for cross-project referenced chapter IDs.
- Browser-reload persistence of directive settings.
