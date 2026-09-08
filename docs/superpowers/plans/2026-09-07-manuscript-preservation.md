# Manuscript Preservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task. Tasks require independent spec and quality review. Do not spawn child workers.

**Goal:** Preserve the latest chapter manuscript across saves, navigation, refine acceptance and scene assembly, and provide recoverable pre-change snapshots.

**Architecture:** One optimistic-revision write service owns all backend chapter mutations. A per-chapter frontend draft/save coordinator survives editor unmount. Existing UI components expose conflicts and explicit snapshot restoration.

**Tech Stack:** FastAPI, SQLAlchemy 2, SQLite/Alembic, React/TypeScript, Zustand, TanStack Query, CodeMirror, Playwright. Native Windows Python venv and Windows Node packages.

**Spec:** `docs/superpowers/specs/2026-09-07-manuscript-preservation.md` (approved chat design, recorded execution contract).

## Global Constraints
- Never read/write/migrate production jippeel.db/WAL/SHM or call configured real model endpoints. All tests, including app lifespan, use temporary DATABASE_URL and dedicated ports.
- Work on feat/manuscript-preservation in the current checkout; preserve all pre-existing dirty/untracked files. No merge/push or automatic production upgrade/stamp.
- No new dependency, model calls or visual redesign. Use existing frontend components.
- Chapter revision starts at 0. expected_revision is required on content PUT/POST, scene merge and snapshot restore. Stale writes return 409 without mutation.
- Scope excludes AI context/ending feature work, timeline, trash and scheduled backup. Snapshot history has no automatic pruning in this slice.
- Write failing regression tests first; use project-native interpreters. Each worker records actual commands, failures before fix, passes after fix, limitations and files in its report. No worker self-approval substitutes for review.
- Commit only explicitly assigned source/test files, never broad git add. Parent owns specs/plan/ledger/HANDOFF updates.

## File and interface map
- Backend Task 1: models/schemas, `services/manuscripts.py`, chapter/refine/scene routes, migrations, startup schema check and backend tests; manuscript-writing scripts if they need expected_revision.
- Frontend Task 2: `lib/manuscriptDrafts.ts` or focused equivalent, editor store/page/navigation, API types, refine and scene panels, existing-component snapshot/conflict dialog, browser regression tests.
- QA Task 3: isolated integration tests/runbook only, no feature edits. Final defects return to original implementer.

### Task 1: Atomic revision writes and pre-change snapshots

**Files:** Modify backend/app/models.py, schemas.py, routers/projects.py, routers/refine.py, routers/scenes.py, database.py/main.py only as needed for safe schema failure, affected tests and manuscript write callers under scripts/. Create backend/app/services/manuscripts.py; next Alembic revision after f9a1b2c3d4e5; backend/tests/test_manuscript_preservation.py. Existing historical migrations may change only with populated DB regression evidence.

**Consumes:** Existing Chapter/RefineRun/Scene models, create_db_engine and Count utility. Existing old clients omit revision and will need explicit test/caller updates.
**Produces:** ChapterDetail includes revision; content service `replace_manuscript(db, chapter_id, content_md, expected_revision, reason)` returns Chapter without independently committing (caller owns transaction). API exact names and error shape follow spec §1–3. Snapshot list/detail routes and restore are under chapters/{cid}. Refine accept now returns ChapterDetail; run captures base_revision before pipeline execution.

- [ ] Step 1: Write API regression tests; run before changing production code. At minimum use this exact behavioral sequence (test client fixture and helpers already exist):
```python
def test_stale_write_preserves_manuscript_and_history(client):
    project = client.post('/api/v1/projects', json={'title': 'safe'}).json()
    chapter = client.post(f"/api/v1/projects/{project['id']}/chapters", json={'title': 'one'}).json()
    cid = chapter['id']
    first = client.put(f'/api/v1/chapters/{cid}/content', json={'content_md': 'newest', 'expected_revision': 0})
    assert first.status_code == 200
    assert first.json()['revision'] == 1
    stale = client.put(f'/api/v1/chapters/{cid}/content', json={'content_md': 'old', 'expected_revision': 0})
    assert stale.status_code == 409
    assert client.get(f'/api/v1/chapters/{cid}').json()['content_md'] == 'newest'
    snapshots = client.get(f'/api/v1/chapters/{cid}/snapshots').json()
    assert len(snapshots) == 1
    old = client.get(f"/api/v1/chapters/{cid}/snapshots/{snapshots[0]['id']}").json()
    assert old['content_md'] == ''
```
Add actual tests for every spec §5 API case, including separate-session concurrency with one winner, rollback/snapshot atomicity, legacy/stale refine, no-op, same-chapter restore enforcement and populated migrations. Test real DB predicates, not just stubbed comparisons.
- [ ] Step 2: Execute native pytest through a launcher that sets a fresh tempfile DATABASE_URL before importing pytest/app. Record expected missing revision/routes/incorrect stale acceptance failures; never leave default lifespan DB active.
- [ ] Step 3: Add schema/model/migration/service. Core update must be a conditional DB write rather than a SELECT-only guard:
```python
stmt = update(Chapter).where(Chapter.id == chapter_id, Chapter.revision == expected_revision).values(
    content_md=content_md, revision=expected_revision + 1,
    word_count_cache=count_novelpia_chars(content_md),
)
result = db.execute(stmt)
# A non-unit rowcount is a conflict; roll back the transaction including snapshots.
```
Complete the service with a captured pre-write value, same-revision no-op, domain conflict mapping, unique snapshot, correct ORM refresh/expiration and caller-owned commit. Every successful route and run.accepted flag must commit atomically. Handle no-op concurrency without claiming a stale payload was current. Store reason autosave/refine/scene_merge/restore verbatim.
- [ ] Step 4: Route all replacements through the service, with captured refine input/base revision; enforce required request revisions and prevent empty scene merge. Add retrieval/restore APIs. Update existing tests and offline scripts to read/send revision explicitly; do not weaken the guard for compatibility. For conftest, preserve isolation while updating shared test helpers only if tests still explicitly exercise missing/stale revision rejection.
- [ ] Step 5: Run all backend tests and populated migration probes in temporary files. Missing-column startup must fail with an actionable upgrade instruction, never auto-stamp. Document which old migration was fixed if required. Deliver report `docs/audits/preservation-task-1-report.md`, interface details and native command output; commit only Task 1 files. Parent requests review before Task 2.

### Task 2: Per-chapter save coordinator and recovery UI

**Files:** frontend/src/lib/manuscriptDrafts.ts (or focused same-purpose module), frontend/src/stores/editorStore.ts, pages/EditorPage.tsx, navigation paths in HomePage/LeftSidebar if needed, lib/api.ts, components/panels/RefineReport.tsx and SceneManager.tsx, existing-component snapshot/conflict dialog, e2e/manuscript-preservation.spec.ts and dedicated test config if needed. Update existing frontend tests/fixtures for revision contract.

**Consumes:** Reviewed Task 1 API, revision integer, snapshots endpoints, refine accept ChapterDetail. Use backend report's response fields, not guessed types.
**Produces:** Per-chapter draft source for editor/preview/save state, serial writes and explicit conflict recovery; no fresh AI generation feature.

- [ ] Step 1: Add failing browser regressions for rapid chapter switch and delayed save plus newer typing. For the delay, intercept only the first save, assert outgoing expected_revision, type newer text while it is pending, release response, and assert a second save containing newer text with incremented revision. Inspect real outgoing requests and editor/preview values. Independently test project switch never writes the previous chapter under new project context.
```ts
expect(firstWrite.expected_revision).toBe(0);
expect(firstWrite.content_md).toBe('first draft');
expect(secondWrite.expected_revision).toBe(1);
expect(secondWrite.content_md).toBe('latest draft');
// After server acknowledgement, preview and re-open must show latest draft.
```
Use existing Playwright and native Windows Node. Do not add timers that merely mask the race; explicitly hold/release mocked requests. Fail before implementation and record output.
- [ ] Step 2: Introduce small save coordinator with chapter-owned `serverRevision`, `text`, `editSequence`, in-flight capture, saving/error/conflict flags. Coalesce writes; commit server acknowledgement only to the sent sequence. Update caches from response without overwriting newer local text. A pure coordinator test may be run with existing Playwright test runner; no new unit-test framework required.
- [ ] Step 3: Persist recoverable drafts under jippeel:manuscript-draft:v1: storage keys with project/chapter/version and recover safely after GET. Storage failure must not prevent typing/server saves. 409 freezes automatic replacement and offers local/server comparison+copy instead of force-retry. Lost-response GET reconciliation must match text before acknowledging. Preserve local recovery data on failed saves. pagehide is best effort, with beforeunload warning for unsaved data.
- [ ] Step 4: Wire editor/preview/navigation, correct project membership, detail/list caches and flush actions. Flush before refine start/accept and scene merge/restore; abort action on failure or conflict. A new edit during flush must not be discarded by a completion response. Put scene manager trigger outside closed Dialog. Snapshot UI shows source text before explicit restore, and restored result becomes current revision. Keep existing design and Korean copy.
- [ ] Step 5: Expand browser tests for all spec §5 frontend cases including reload/storage error/network error/409, stale refine, actual scene trigger and snapshot restore. Build with project-native Node. Record commands/red-green evidence/limitations to docs/audits/preservation-task-2-report.md and commit only frontend files. Parent performs separate review.

### Task 3: Isolated real-surface verification and handoff

**Files:** tests under frontend/e2e or scripts/ dedicated to preservation, docs/audits/preservation-final-validation.md and docs/runbooks/manuscript-preservation.md. No production feature edits.

**Consumes:** Reviewed Task 1 + Task 2, QA environment notes, isolated backend temp DB and stub refine pipeline.
**Produces:** Reproducible native test commands/logs, populated DB upgrade/restore evidence and deployment constraints.

- [ ] Step 1: Start backend with DATABASE_URL pointing to newly created temp path and dedicated port, frontend on a different dedicated port. Do not reuse 8000/5173 servers. Use fake/stub external processing, never real endpoints or production configuration.
- [ ] Step 2: In Chromium create project/chapter, type and switch before debounce, edit while a real save is in flight, re-open and preview. Assert API GET exact content/revision. Generate stub refine then edit/save, assert accept 409 and unchanged content; assemble nonempty scenes and restore prior snapshot, assert original preserved. Distinguish fixture-only races from native API integration evidence.
- [ ] Step 3: Run full backend suite, frontend build and scoped browser suites. Upgrade a populated temporary old-schema DB; compare exact manuscripts and relationship rows before/after. Perform SQLite consistent backup to a second temporary file and reopen/compare relevant table contents, not row counts alone.
- [ ] Step 4: Write runbook for explicit backup/copy-upgrade checks and coordinated frontend/backend deployment. No automatic production migration or service replacement. Report unresolved failures honestly. Parent dispatches final source diff reviewer, then updates HANDOFF and reports completion or blockers.

## Contract review rulings (binding clarifications)
- Task 1: POST /refine requires expected_revision; mismatch returns structured 409 before pipeline execution. Capture input text+base revision before pipeline; preserve that exact input in report/response.
- Task 1: No-op must atomically validate revision without creating a revision/snapshot. Conditional no-op UPDATE is acceptable. For changing writes, pre-image capture then guarded UPDATE then snapshot INSERT in the same transaction is acceptable; any failure rolls back all changes. Do not convert arbitrary integrity bugs to conflicts. Tests must prove rollback, concurrent writers and no-op racing a changing write.
- Task 1: Normal startup guards schema/Alembic state BEFORE create_all/seed/FTS and performs no partial upgrade. Empty normal DB needs explicit migration. Only explicitly marked temporary test initialization may use create_all.
- Task 2: ApiError retains structured detail (code/current_revision); lost-ack GET reconciliation matches sentText exactly before acknowledging its sequence. Local persistence is attempted on every edit before scheduling debounce. Only matching-sequence acknowledgement may remove the recovery draft; newer text remains and rebases on known ack revision.
