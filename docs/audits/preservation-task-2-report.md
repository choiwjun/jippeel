# Preservation Task 2 Report — Frontend manuscript preservation

## Status
Implemented frontend Task 2 on `feat/manuscript-preservation`.

Scope kept to frontend source/tests plus this report. No backend source, production DB, live backend, real LLM endpoint, dependency install, push, or merge was used.

## Implemented
- Added a per-project/per-chapter manuscript draft coordinator in `frontend/src/lib/manuscriptDrafts.ts`.
- Sends all chapter content writes with required `expected_revision`.
- Serializes per-chapter saves and rebases newer local edits after an older in-flight acknowledgement.
- Stores recoverable local drafts under `jippeel:manuscript-draft:v1:{projectId}:{chapterId}`.
- Preserves local text on save failure, network failure, storage failure, and 409 conflict.
- Keeps `ApiError.detail` structured, including `code` and `current_revision`.
- Uses sequence-aware lost-ack reconciliation by GET, accepting only when `content_md === sentText`.
- Shows local/server comparison for recovery mismatch and revision conflicts.
- Keeps preview on the local draft when it is newer than cache data.
- Clears stale selected chapter state on project switch before showing editor content.
- Flushes manuscript draft before refine start, refine accept, scene merge, and snapshot restore.
- Sends `POST /refine` with required `expected_revision`.
- Adds snapshot list/detail/restore UI using existing dialog/button/alert components.
- Moves the scene manager trigger outside the closed dialog and sends scene merge `expected_revision`.
- Updates the existing XSS browser fixture write to include `expected_revision`.

## TDD evidence

### Red
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Initial result before implementation:

```text
Running 7 tests using 1 worker
✘ serializes delayed per-chapter saves and preserves newer typing
Expected: 0
Received: undefined
expect(firstWrite.expected_revision).toBe(0)
1 failed, 6 did not run
```

This proved the existing UI did not send `expected_revision`.

### Green: isolated frontend browser fixture
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result:

```text
Running 8 tests using 1 worker
✓ serializes delayed per-chapter saves and preserves newer typing
✓ project switch rejects stale selected chapters and never writes under the new project context
✓ keeps ApiError detail for 409 and shows local/server conflict recovery
✓ recovers reload drafts, survives storage failure, and preserves text after network error
✓ preserves local text on network failure and reconciles lost save acknowledgements
✓ flushes before refine start, sends expected_revision, and blocks stale accept safely
✓ scene trigger is accessible and merge flushes with expected_revision
✓ shows snapshot text before explicit restore and restore uses current revision
8 passed (11.9s)
```

The fixture config uses `127.0.0.1:15193`, `reuseExistingServer: false`, all API requests mocked, and aborts unexpected `/api/v1/*` requests. It does not reuse the checked-in `:5173/:8000` Playwright config.

### Green: frontend build
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
```

Result:

```text
> jippeel-frontend@0.1.0 build
> tsc -b && vite build

▲ [WARNING] Duplicate key "build" in object literal [duplicate-object-key]
    vite.config.ts:38:2
    The original key "build" is here: vite.config.ts:11:2
vite v5.4.21 building for production...
✓ 229 modules transformed.
✓ built in 2.92s
```

The duplicate `build` key warning is pre-existing and recorded in the environment note.

## Files changed
- `frontend/src/lib/manuscriptDrafts.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/stores/editorStore.ts`
- `frontend/src/pages/EditorPage.tsx`
- `frontend/src/components/editor/SaveIndicator.tsx`
- `frontend/src/components/panels/RefineReport.tsx`
- `frontend/src/components/panels/SceneManager.tsx`
- `frontend/e2e/manuscript-preservation.spec.ts`
- `frontend/playwright.preservation.config.ts`
- `frontend/e2e/app-flow.spec.ts`
- `docs/audits/preservation-task-2-report.md`

## Limitations and handoff
- Browser preservation tests are frontend fixture tests, not backend integration tests.
- I did not run the unsafe default Playwright config because it can reuse `:5173` and proxy to `:8000`.
- I did not run live DB, app lifespan, Alembic, or real LLM calls.
- Parent/QA can use the new backend fixture prep for final real API browser QA.
- I did not request child review because the task explicitly said no children.

## Fix round 1 — sequence-aware replacement responses

Review source: `docs/audits/preservation-task-2-review.md`.

Changes made after commit `28a6c90`:
- Added sequence-aware replacement tokens in `frontend/src/lib/manuscriptDrafts.ts`.
- Refine accept, scene merge, and snapshot restore now capture a baseline after successful flush and before the replacement request.
- If local text changes while the replacement response is pending, the response updates server revision/cache but does not overwrite editor text or remove the recovery draft.
- Late replacement responses now leave an explicit conflict/comparison state with the local text preserved.
- Expanded fixture coverage for held refine accept, held scene merge, held snapshot restore, negative lost-ack GET, and pagehide/beforeunload revision-contract behavior.

### Fix red evidence
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result before production fix:

```text
Running 13 tests using 1 worker
5 passed
✘ does not let a pending refine accept response overwrite a late local edit
Expected substring: "late local edit"
Received string:    "before refinerefined"
1 failed, 7 did not run
```

### Fix green evidence
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result:

```text
Running 13 tests using 1 worker
13 passed (16.1s)
```

The preservation fixture now uses dedicated `127.0.0.1:15201`, `reuseExistingServer: false`, with all `/api/v1/*` requests mocked/guarded.

### Fix build evidence
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
```

Result:

```text
> jippeel-frontend@0.1.0 build
> tsc -b && vite build

▲ [WARNING] Duplicate key "build" in object literal [duplicate-object-key]
vite v5.4.21 building for production...
✓ 229 modules transformed.
✓ built in 2.79s
```

The duplicate `build` key warning is pre-existing.

### Fix round 1 limitations
- Still fixture/browser QA only, not final backend integration.
- No production DB, live backend, real LLM, dependency install, push, merge, or child review was used.
