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


## Contract review rulings (binding clarifications)
- Task 1: POST /refine requires expected_revision; mismatch returns structured 409 before pipeline execution. Capture input text+base revision before pipeline; preserve that exact input in report/response.
- Task 1: No-op must atomically validate revision without creating a revision/snapshot. Conditional no-op UPDATE is acceptable. For changing writes, pre-image capture then guarded UPDATE then snapshot INSERT in the same transaction is acceptable; any failure rolls back all changes. Do not convert arbitrary integrity bugs to conflicts. Tests must prove rollback, concurrent writers and no-op racing a changing write.
- Task 1: Normal startup guards schema/Alembic state BEFORE create_all/seed/FTS and performs no partial upgrade. Empty normal DB needs explicit migration. Only explicitly marked temporary test initialization may use create_all.
- Task 2: ApiError retains structured detail (code/current_revision); lost-ack GET reconciliation matches sentText exactly before acknowledging its sequence. Local persistence is attempted on every edit before scheduling debounce. Only matching-sequence acknowledgement may remove the recovery draft; newer text remains and rebases on known ack revision.

Runtime: read docs/audits/manuscript-preservation-environment.md. Use Windows cmd.exe node/npm, not Linux Node with Windows node_modules. Do not run old E2E config against :5173/:8000. Native review requires dedicated fixture/static or isolated backend ports.
