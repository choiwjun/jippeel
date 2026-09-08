# AI Context Consistency Specification

## 1. Goal

Make every AI-facing path use the same current project/chapter identity and the same request-scoped story directives before any provider call starts.

This phase fixes context consistency only. It does not add a new long-term story memory system, a chapter-goal database, a token-budget engine, or an automatic manuscript/canon mutator.

## 2. Approved scope

### Included

- Separate **current chapter/project identity** from the checkbox that includes the current chapter body in the prompt.
- Validate that explicitly supplied `project_id`, `chapter_id`, `scene_id`, selected `character_ids`, selected `lore_ids`, and approved `foreshadow_ids` belong to the same project before LLM/provider work.
- Share context, style profile, selected relationships, episode purpose, and approved foreshadow payoff/reveal permissions across:
  - single generation `/api/v1/ai/generate`
  - single generation review pass
  - parallel planner
  - parallel workers
  - parallel review
  - canon check `/api/v1/canon-check`
  - local quality check `/api/v1/chapters/{cid}/quality` where purpose affects hook applicability
- Add episode purpose values:
  - `serial` (default)
  - `volume_end`
  - `series_finale`
- Remove contradictory unconditional “must leave hook/unresolved conflict” directives from generation, review, parallel, canon, and local quality warning copy.
- Add request-scoped author-approved foreshadow payoff/reveal permission.
- Add opt-in relationship context in existing small controls in `AiPanel`, `CanonDialog`, and `QualityDialog`.
- Preserve existing manual result handling. AI output is not written into the manuscript unless the author clicks an insertion/replacement control.
- Record deterministic included-ID metadata for transparency and tests.
- Keep the completed manuscript preservation feature intact.

### Excluded

- Historical-memory extraction.
- Persistent chapter-goal storage.
- A planner directive database.
- A new database migration unless an implementer proves that no existing JSON field can store the needed metadata.
- A generic token-budget engine or global truncation refactor.
- Reordering or changing the parallel worker cancellation/review-marker contracts.
- Browser-reload persistence of request-scoped AI directives.
- Automatic manuscript edits.
- Automatic `Foreshadow.status`, `Foreshadow.audience_knows`, `planted_chapter_id`, or `resolved_chapter_id` changes.
- New package dependencies.
- Frontend redesign.

## 3. Current source facts

The implementation must preserve these facts from the current branch `feat/ai-context-consistency` at `70ec67e`:

- `backend/app/routers/ai_panel.py` builds generation context in `_build_context_blocks()` and `_build_messages()`.
- Current generation adds the chapter body whenever `context.chapter_id` is supplied.
- Current generation does not validate selected character/lore project ownership.
- Current generation does not include `Relationship` rows.
- Current parallel generation reuses the last user message from `_build_messages()` for planner, workers, and review.
- Current parallel worker assembly is order-based in `backend/app/services/parallel_writer.py` and must stay order-based.
- Current canon context is built separately in `backend/app/services/canon.py`.
- Current local quality hook check always scores a missing end hook as bad in `backend/app/services/quality.py`.
- Current editor preservation coordinator already owns `flushManuscriptDraft()`, `beginManuscriptReplacement()`, and result ownership checks in `frontend/src/lib/manuscriptDrafts.ts`.
- Existing frontend AI insertion controls live in `frontend/src/components/panels/AiPanel.tsx` and currently operate on the active editor view.

## 3.1 Baseline negative corpus

Implementation tests must reproduce the native intercepted-message negative corpus from `docs/audits/ai-context-baseline-probes.md` and `.json`:

- Probe A1: selected character/lore from another project entered a generation prompt.
- Probe A2: explicit `project_id` from project B mixed with chapter A body plus project B style/auto lore/foreshadow.
- Probe B: selected relationship data was omitted even when both endpoint characters were selected.
- Probe C: style profile reached single generation but not parallel planner/worker/reviewer phases.


## 4. Domain terms

Use these terms in code comments and tests when helpful:

- **ContextBundle**: one immutable request-level bundle of resolved identity, prompt blocks, style text, directive text, and metadata.
- **Current identity**: the current `project_id` and optional `chapter_id` that the request is bound to.
- **Body inclusion**: whether the current chapter body is included in the user prompt. This is controlled by `include_chapter_content`; it is not identity.
- **Episode purpose**: one of `serial`, `volume_end`, `series_finale`.
- **Approved payoff IDs**: `approved_foreshadow_ids` supplied by the author for this request only.
- **Future reference**: an existing foreshadow/plan row whose referenced chapter is after the current chapter by `(sort_order, id)`. It is not current fact or character knowledge.
- **Current record**: the value currently stored in the database. Unknown historical state must be labelled as unknown/current record instead of invented. Current style profile and lore rows are current records, not proof of historical truth at an earlier chapter. Historical memory is deferred.

## 5. Backend request contracts

### 5.1 `GenerateContext`

Extend `backend/app/schemas.py` `GenerateContext` additively:

```python
EpisodePurpose = Literal["serial", "volume_end", "series_finale"]

class GenerateContext(BaseModel):
    chapter_id: int | None = None
    project_id: int | None = Field(default=None, description="현재 요청이 속한 작품 ID")
    include_chapter_content: bool = True
    expected_revision: int | None = Field(default=None, ge=0)
    episode_purpose: EpisodePurpose = "serial"
    approved_foreshadow_ids: list[int] = Field(default_factory=list, max_length=20)
    include_relationships: bool = False
    character_ids: list[int] | None = None
    lore_ids: list[int] | None = None
    auto_lore: bool = False
    auto_lore_limit: int = Field(default=6, ge=1, le=20)
    auto_lore_semantic: bool = False
    previous_chapter: bool = False
    auto_outline: bool = False
    scene_id: int | None = None
    auto_foreshadow: bool = False
    auto_foreshadow_limit: int = Field(default=5, ge=1, le=10)
    style_profile: bool = False
    brief: EpisodeBrief | None = None
```

Rules:

- Legacy clients that send `chapter_id` and omit `include_chapter_content` keep old behavior because the default is `True`.
- The frontend always sends `project_id` and `chapter_id` when an editor chapter is open.
- The frontend sends `include_chapter_content: false` when the author turns off current-body inclusion. The backend still validates the current chapter identity and revision.
- `expected_revision` is optional. Legacy clients may omit it. If supplied with `chapter_id`, the backend checks the current database `Chapter.revision` before an LLM/provider call.
- If `expected_revision` does not match, return `409` with:

```json
{
  "detail": {
    "code": "revision_conflict",
    "message": "회차가 바뀌었습니다. 저장 상태를 확인한 뒤 다시 실행하세요.",
    "current_revision": 7
  }
}
```

- If `expected_revision` is supplied without `chapter_id`, return `422`.

### 5.2 `EpisodeBrief`

Change `EpisodeBrief.next_hook` from required to optional and add `ending_intent`:

```python
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

Purpose validation happens in `GenerateContext` because the purpose is outside the brief:

- `serial`: if `brief` exists, `brief.next_hook` is required. This preserves old serial behavior.
- `volume_end`: if `brief` exists, at least one of `brief.next_hook` or `brief.ending_intent` is required.
- `series_finale`: if `brief` exists, `brief.ending_intent` is required. `next_hook` may be present as an epilogue/afterword setup, but system prompts must not force a cliffhanger.

### 5.3 `ParallelScenePlan`

Keep existing fields and add `ending_intent` additively:

```python
class ParallelScenePlan(BaseModel):
    order: int = Field(ge=1, le=4)
    title: BriefText
    purpose: BriefText
    objective: BriefText
    choice: BriefText
    cost: BriefText
    required_beats: list[BriefText] = Field(min_length=1, max_length=5)
    characters: list[BriefText] = Field(min_length=1, max_length=8)
    opening_state: BriefText
    closing_hook: BriefText | None = None
    ending_intent: BriefText | None = None
```

Parsing and validation interface:

```python
def parse_parallel_plan(raw: str, episode_purpose: EpisodePurpose = "serial") -> ParallelPlan: ...
```

Old helper callers default to `serial`. Purpose exceptions apply to planner instructions and parse-time validation. Do not claim legacy hook-only planner JSON is valid for `series_finale`; the final scene must provide `ending_intent`.

Validation must not change order, cancellation, or review-marker behavior:

- For `serial`, each scene must have `closing_hook`.
- For `volume_end`, each scene must have either `closing_hook` or `ending_intent`; the final scene should prefer `ending_intent`.
- For `series_finale`, each scene must have either `closing_hook` or `ending_intent`; the final scene must have `ending_intent`.
- Existing planner JSON with `closing_hook` remains valid for default `serial` calls. For `series_finale`, the final scene needs `ending_intent`.

### 5.4 `CanonCheckRequest`

Extend `CanonCheckRequest` additively:

```python
class CanonCheckRequest(BaseModel):
    chapter_id: int
    expected_revision: int | None = Field(default=None, ge=0)
    episode_purpose: EpisodePurpose = "serial"
    approved_foreshadow_ids: list[int] = Field(default_factory=list, max_length=20)
    include_relationships: bool = False
```

Rules:

- Existing `{ "chapter_id": 1 }` calls remain valid.
- If `expected_revision` is supplied and stale, return the same `409` shape as generation.
- Canon never mutates manuscript, foreshadows, characters, lore, or relationships.
- Canon flushes and receives a saved revision from the frontend when run from the editor. Legacy backend calls may omit it.
- Canon captures immutable input body, `Chapter.revision`, and SHA256 before awaiting the provider.
- Canon stores `checked_input_revision` and `checked_input_hash` in existing `CanonRun.context_json` and returns them in `checked_context`.
- The stored run stays bound to the captured origin even if the chapter changes while the provider runs.

### 5.5 Local quality query

Extend `GET /api/v1/chapters/{cid}/quality`:

- Existing query: `record: bool = True`
- New query: `episode_purpose: serial|volume_end|series_finale = serial`

Rules:

- `serial` keeps the existing local hook penalty and suggestion.
- `volume_end` makes the hook metric informational. It may suggest a closing intention instead of a cliffhanger.
- `series_finale` disables the missing-hook penalty and must not invent a final-episode literary score.
- `metrics_json` stored in `QualityCheck` includes:

```json
{
  "episode_purpose": "series_finale",
  "hook_score_applicable": false,
  "hook_present": false
}
```

- Do not change `content_hash`. It remains the hash of true chapter text only.
- History dedup compares both `content_hash` and stored `metrics_json.episode_purpose`. Same text checked as `serial` and then `series_finale` may create two rows. Same text checked twice as the same purpose creates one row.

## 6. ContextBundle backend interface

Create `backend/app/services/ai_context.py` as the deep module for context assembly.

### 6.1 Public types

```python
from dataclasses import dataclass, field
from typing import Literal

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

### 6.2 Public functions

```python
def request_from_generate(payload: GenerateRequest) -> ContextBundleRequest: ...

def request_from_canon(payload: CanonCheckRequest, chapter: Chapter) -> ContextBundleRequest: ...

def build_context_bundle(db: Session, request: ContextBundleRequest) -> ContextBundle: ...

def purpose_directive(purpose: EpisodePurpose) -> str: ...
```

### 6.3 Metadata output

`ContextBundle.metadata` must be deterministic and JSON-safe:

```json
{
  "project_id": 1,
  "chapter_id": 10,
  "chapter_revision": 3,
  "include_chapter_content": false,
  "episode_purpose": "series_finale",
  "included_character_ids": [2, 5],
  "included_lore_ids": [7],
  "injected_lore": [{"id": 7, "title": "흑요 검"}],
  "included_relationship_ids": [4],
  "included_foreshadow_ids": [11],
  "approved_foreshadow_ids": [11],
  "future_reference_foreshadow_ids": [12],
  "outline": {"current": true, "next_chapter_id": 13, "next_title": "후일담"},
  "unknown_labels": ["foreshadow_history_is_current_record_only"]
}
```

Ordering rules:

- Character IDs: preserve caller order, but output only IDs that were found and valid.
- Lore IDs: preserve caller order, but output only IDs that were found and valid.
- Relationship IDs: ascending `Relationship.id`.
- Auto lore: keep existing scoring order from `injection.select_lore_for_text*`; skip explicit duplicates.
- Auto foreshadow: deterministic by story position where possible, then ID. Do not use arbitrary provider output.
- Future references: labelled separately. They may guide generation but must not be presented as current facts or character knowledge.

### 6.4 Ownership validation

`build_context_bundle()` must raise `HTTPException` before any provider call:

- `404`: a referenced `chapter_id`, `scene_id`, selected `character_id`, selected `lore_id`, or approved `foreshadow_id` does not exist.
- `422`: explicit IDs exist but are not in the resolved project.
- `422`: more than one explicit project source is supplied and they disagree.
- `409`: `expected_revision` is supplied and does not equal current `Chapter.revision`.
- `422`: `expected_revision` is supplied without `chapter_id`.
- `422`: any consumed foreshadow has `planted_chapter_id` or `resolved_chapter_id` pointing to a chapter in another project. This includes approved foreshadows and auto-included foreshadows. Do not fix that unrelated CRUD data here.
- `include_relationships` with fewer than two selected same-project characters produces an empty generation relationship list and `included_relationship_ids: []`; it is not a 422.

### 6.5 Relationship context

Relationship inclusion is opt-in. Do not add a public scope field or public scope type in this phase.

Generation policy:

- `include_relationships: false`: no relationships in generation context.
- `include_relationships: true`: include only relationships where both endpoints are in the validated selected `character_ids`.
- If zero or one selected same-project character is present, include no relationships and set `included_relationship_ids: []`. Do not return 422 for this case.

Canon policy:

- `include_relationships: false`: no relationships in canon context.
- `include_relationships: true`: include all relationships whose two endpoint characters both belong to the chapter's project.

Validation:

- For every consumed relationship row, load both endpoint characters and verify both belong to the resolved project.
- If a relationship endpoint is missing or points outside the resolved project, reject before provider work.
- Do not fabricate endpoint names.

Relationship block format:

```text
[인물 관계 — 관계가 본문 행동·호칭·거리감과 모순되면 지적]
- 한서윤 ↔ 강무진: 사제 관계. 스승은 제자를 공개적으로 감싸지 못한다.
```

### 6.6 Provider-before-validation ordering

All AI-facing routes must validate context ownership and revision before provider path work:

- `/api/v1/ai/generate`: build and validate the generation `ContextBundle` before `llm.make_client()` or any provider await.
- `/api/v1/ai/generate-parallel`: build and validate the same generation `ContextBundle` before planner provider client creation or planner await.
- `/api/v1/canon-check`: build and validate the canon `ContextBundle`, capture immutable input body/revision/hash, and only then call `resolve_endpoint(db)` and create the provider client.
- For 409/422 validation failures, tests must monkeypatch provider client creation or endpoint resolution to fail if touched and must assert it was not touched.

## 7. Foreshadow permission semantics

`approved_foreshadow_ids` means exactly this:

- The author allows payoff/reveal for the listed foreshadows in this request.
- The author does not permit unrelated canon inconsistency.
- The backend must not change `Foreshadow.status`.
- The backend must not change `Foreshadow.audience_knows`.
- The backend must not set `resolved_chapter_id`.
- The frontend must not persist this approval across browser reload.

Block labels:

```text
[미회수 복선: 검의 진짜 주인 — 현재 기록]
상태: 설치. 독자 인지: false. 설치 회차: unknown/current record.
→ 작가 승인 없이 결론·정체·회수를 공개하지 마라.
```

```text
[이번 요청에서 회수/공개 허용된 복선: 검의 진짜 주인]
상태: 설치. 독자 인지: false. 설치 회차: 3화(현재 기록).
→ 이번 원고에서 자연스럽게 공개하거나 회수할 수 있다. 단, 원고 밖 상태값은 자동 변경하지 마라.
```

```text
[미래 계획 복선: 황궁 지하 문 — 현재 사실 아님]
참조 회차가 현재 회차보다 뒤에 있다. 이 정보는 작가 계획일 수 있으나 현재 인물 지식·세계 사실로 단정하지 마라.
```

Future reference detection is coarse and field-specific:

- Compare referenced chapters by `(sort_order, id)` within the same project.
- A future `planted_chapter_id` means the clue is not yet a current fact at the target chapter.
- A future `resolved_chapter_id` does not make an already planted clue nonexistent. Keep the planted clue as current record and label only the planned resolution as future plan.
- Do not use a future planned resolution as evidence of a canon violation.
- If no current chapter is known, do not label a row as future. Label it as current record with unknown timing.
- Explicit approval is always included, even when `auto_foreshadow=false` or `auto_foreshadow_limit` is exhausted.
- Approval is scoped only to the listed IDs.
- Approved future plans may be realized by author permission, but they must not be asserted as preexisting fact.
- Validate same-project chapter references for all consumed foreshadow rows, not only the approved list.
- Future plans may guide generation, but must not be treated as current facts, character knowledge, or a reason to claim a continuity violation.

## 8. Purpose-aware directives

### 8.1 Generation system prompt

The generation prompt must include a purpose block derived from `episode_purpose`.

`serial`:

- Continue the story.
- Use unresolved pressure only when it matches the brief, outline, or scene contract.
- If a `next_hook` is supplied, steer the ending toward it.
- Do not require every conflict to remain unresolved.

`volume_end`:

- Close the volume's main emotional or plot movement.
- Leave only deliberate next-volume questions.
- Do not force a cliffhanger if `ending_intent` asks for closure.

`series_finale`:

- Close the series-level emotional and conflict arc stated in the brief or outline.
- Do not invent a new sequel hook unless the author explicitly supplied one.
- Do not penalize a resolved ending.
- Do not invent a final-episode literary score.

### 8.2 Review prompts

Single review and parallel review must receive the same context bundle and purpose directive used by generation.

Reviewers should check purpose fit:

- `serial`: did the draft keep enough forward pressure without contradicting context?
- `volume_end`: did the draft close the volume movement and avoid accidental unresolved residue?
- `series_finale`: did the draft honor closure and avoid forced cliffhanger wording?

### 8.3 Canon prompts

Canon should not flag an approved payoff as premature solely because it reveals an approved foreshadow ID.

Canon still flags:

- revealing an unapproved installed/held foreshadow as fact,
- contradicting character/lore/relationship data,
- treating a future reference as current fact,
- using cross-project context.

### 8.4 Local quality

The local quality checker must remove unconditional hook warnings:

- The UI status change warning in `EditorHeader` must not say every completed chapter needs a next-episode hook when the shared purpose is `volume_end` or `series_finale`.
- The metrics object must expose whether hook scoring applied.
- The quality dialog may show `후크(끝 300자): 해당 없음` for `series_finale`.

## 9. Frontend contracts

### 9.1 Session-scoped directive state

Extend `frontend/src/stores/aiPanelStore.ts` with a browser-session map keyed by project/chapter:

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

Defaults after browser reload:

```ts
{
  episodePurpose: 'serial',
  approvedForeshadowIds: [],
  includeRelationships: false,
}
```

No localStorage/sessionStorage persistence is promised for this directive map.

### 9.2 Request snapshot before generation

When the editor has a current chapter:

0. Reserve an in-flight start token before awaiting flush. Disable duplicate starts for that token. Invalidate pending starts on close, cancel, and navigation.
1. Read `editorStore.projectId` and `editorStore.chapterId`. Before the first await, deep-copy the entire request form: context selection and its arrays, purpose-aware parsed brief, directives for that starting identity, endpoint/model/temperature/token settings, generation mode, worker limit, and all review settings. Canon deep-copies its shared directives at the same point. Changes to controls while flush is pending affect the next request only.
2. Call existing `flushManuscriptDraft(projectId, chapterId)`.
3. Abort and show the existing error if flush fails because of recovery, conflict, network failure, or revision conflict.
4. After flush returns, re-read `editorStore.projectId` and `editorStore.chapterId`.
5. If navigation changed, abort with `회차가 바뀌어 AI 요청을 시작하지 않았습니다.`
6. Build request body from the flushed identity, `flushed.detail.revision`, and the directive/settings snapshot captured for the same token.
7. Before provider start, verify the in-flight token is still current. If not, do not start a stale request.
8. Start the stream with `AiResultOrigin` equal to that snapshot.

If no editor chapter is open, standalone/project-only calls remain valid only when unambiguous. The backend rejects ambiguous cross-project explicit IDs before LLM work.

### 9.3 Request body from AiPanel

`AiPanel` sends:

```json
{
  "context": {
    "project_id": 1,
    "chapter_id": 10,
    "include_chapter_content": false,
    "expected_revision": 3,
    "episode_purpose": "series_finale",
    "approved_foreshadow_ids": [11],
    "include_relationships": true,
    "character_ids": [2, 5],
    "lore_ids": [],
    "auto_lore": true,
    "auto_outline": true,
    "auto_foreshadow": true,
    "style_profile": true
  }
}
```

The old visible checkbox label “현재 회차” becomes “현재 회차 본문 포함”. Turning it off sends `include_chapter_content: false`; it does not remove current identity.

### 9.4 Result origin safety

Insertion/replacement is allowed only when:

```ts
resultOrigin.projectId === useEditorStore.getState().projectId &&
resultOrigin.chapterId === useEditorStore.getState().chapterId &&
useEditorStore.getState().view !== null &&
useEditorStore.getState().saveState !== "conflict"
```

The insertion code must also respect the existing manuscript recovery/edit lock. If recovery is unresolved, do not mutate the editor document.

If this check fails:

- Do not change the editor document.
- Keep the result visible.
- Keep copy enabled.
- Show `AI 결과가 다른 회차에서 생성되어 현재 원고에 자동 삽입하지 않았습니다. 복사 후 직접 확인하세요.`

Manual copy remains available for all result origins.

### 9.5 CanonDialog and QualityDialog controls

Add small controls, no redesign:

- `CanonDialog`:
  - episode purpose select
  - relationship context checkbox
  - approved foreshadow checkboxes using the shared map
  - before running from an editor chapter, reserve an in-flight token, flush the same chapter through `flushManuscriptDraft(projectId, chapterId)`, then re-read current navigation
  - abort on recovery, conflict, network error, or navigation mismatch
  - send the flushed `detail.revision` as `expected_revision`
  - label returned canon results with the captured origin and revision
- `QualityDialog`:
  - episode purpose select using the same shared map
  - calls `/chapters/{cid}/quality?episode_purpose=${purpose}`
  - displays hook applicability from metrics
- `AiPanel`:
  - episode purpose select
  - relationship context checkbox
  - approved foreshadow checkboxes

The controls share state by `(project_id, chapter_id)` inside `aiPanelStore` only.

## 10. Error matrix

| Case | Request | Expected response before provider call |
|---|---|---|
| Legacy chapter generation | `chapter_id`, no `include_chapter_content`, no revision | 200; includes chapter body |
| Body opt-out generation | `chapter_id`, `include_chapter_content=false` | 200; does not include chapter body; metadata has identity |
| Project/chapter mismatch | `project_id=A`, `chapter_id` belongs to B | 422 |
| Scene/chapter mismatch | `scene_id` belongs to chapter B while `chapter_id` is A | 422 |
| Selected character wrong project | `character_ids` contains B while project A resolved | 422 |
| Selected lore wrong project | `lore_ids` contains B while project A resolved | 422 |
| Approved foreshadow wrong project | approved ID belongs to B while project A resolved | 422 |
| Approved foreshadow has cross-project referenced chapter | foreshadow project A, `resolved_chapter_id` belongs to B | 422 |
| Stale generation revision | `expected_revision=2`, DB has 3 | 409 |
| Stale canon revision | `expected_revision=2`, DB has 3 | 409 |
| Serial brief without `next_hook` | `episode_purpose=serial`, brief present | 422 |
| Volume end brief with neither hook nor ending | `episode_purpose=volume_end`, brief present | 422 |
| Series finale brief without `ending_intent` | `episode_purpose=series_finale`, brief present | 422 |
| Series finale quality no hook | `episode_purpose=series_finale` | 200; no missing-hook penalty |
| Generation relationships with one character | `include_relationships=true`, one selected character | 200; no relationship block; metadata relationship count 0 |
| Canon relationships all | `include_relationships=true` | 200; same-project relationships only |

## 11. Acceptance criteria

- Single generation start event keeps existing fields and adds deterministic `context_metadata`.
- Parallel generation start event keeps existing fields and adds deterministic `context_metadata`.
- Single review user message includes the same context bundle and purpose/payoff directives as generation.
- Parallel planner, workers, and review receive the same context bundle and purpose/payoff directives.
- Canon context uses the same ownership and relationship/payoff semantics as generation where applicable, captures immutable input body/revision/hash before provider work, and stores `checked_input_revision` plus `checked_input_hash`.
- Generation, parallel generation, and canon return 409/422 validation failures without creating provider clients, resolving provider endpoints, or awaiting provider calls.
- Local quality hook score is purpose-aware.
- UI generation and canon runs reserve an in-flight start token, snapshot current identity/revision after flush, and abort on conflict/recovery/navigation mismatch or stale token.
- UI does not silently insert a result into a different chapter or an editor locked by recovery/conflict.
- Copy remains available even when insertion is blocked by origin mismatch.
- Tests use temp DBs, dedicated ports, and deterministic local provider evidence only.
- No production DB, WAL, SHM, port 8000, port 5173, real LLM, or secret is touched.
- For this drafting worker only, `HANDOFF.md`, branch state, commits, source files, and tests are not changed. Implementation workers will change only files authorized by the ratified plan.

## 12. Explicit rulings

- One list, `approved_foreshadow_ids`, is enough for this phase. It permits payoff/reveal for listed IDs for this request. Separate `approved_payoff_ids` and `approved_reveal_ids` are deferred until an actual implementation blocker appears.
- Unknown historical facts are labelled as unknown/current record. They are not reconstructed.
- Future references are coarse labels based on existing chapter `(sort_order, id)` only. They are not current facts.
- Existing JSON columns are enough for provenance: `CanonRun.context_json` and `QualityCheck.metrics_json`. No migration is planned.
- Full context-size optimization is deferred. Existing caps stay in place.
- No real contradiction requiring parent intervention was found during this specification pass.
