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

## Fix round 2 — unresolved recovery mismatch preservation

Review source: `docs/audits/preservation-final-spec-review.md` Finding 1.

Changes made after commit `84dcc4b`:
- Unresolved mismatched recovery drafts now remain unresolved until the user explicitly chooses local recovery or server text.
- Ctrl+S and pre-action flush now block on unresolved recovery mismatch instead of treating `text === serverText` as saved and deleting browser storage.
- Editing while an unresolved mismatch exists does not overwrite/delete the stored local recovery text.
- `pagehide` does not send a best-effort write for unresolved recovery mismatches.
- Replacement actions are blocked by the flush guard until the user resolves the recovery decision.
- `RefineResult.base_revision` is now required in `frontend/src/lib/api.ts` and fixture refine responses include the captured base revision.

### Fix round 2 red evidence
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result before production fix:

```text
Running 14 tests using 1 worker
✓ serializes delayed per-chapter saves and preserves newer typing
✓ project switch rejects stale selected chapters and never writes under the new project context
✘ unresolved mismatched recovery survives Ctrl+S, reload, and pre-action flush
Matcher error: received value must be a non-null object
Received has value: null
1 failed, 11 did not run
```

This reproduced the final review issue: Ctrl+S removed the mismatched recovery draft without a matching save acknowledgement.

### Fix round 2 green evidence
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result:

```text
Running 14 tests using 1 worker
14 passed (19.6s)
```

The fixture run used dedicated `127.0.0.1:15210`, `reuseExistingServer: false`, with all `/api/v1/*` requests mocked/guarded.

### Fix round 2 build evidence
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
✓ built in 3.42s
```

The duplicate `build` key warning is pre-existing.

### Fix round 2 limitations
- Still fixture/browser QA only, not final backend integration.
- No production DB, live backend, real LLM, dependency install, push, merge, or child review was used.

## Fix round 3 — coherent unresolved mismatch state

Review source: `docs/audits/preservation-final-spec-rereview-1.md`.

Changes made after commit `9f10107`:
- Chose the minimal safe design: unresolved mismatched recovery locks the editor until the user chooses local recovery or server text.
- `edit()` no longer accepts or drops typing while unresolved recovery is active. The original local recovery draft remains in browser storage.
- Server detail refreshes now update the unresolved recovery server body and revision as one visible pair.
- Added an explicit `서버 원고 새로고침` action for the recovery panel.
- Choosing `서버 원고로 계속` refreshes the server pair, shows that latest paired server body in the editor, removes the browser draft, and does not issue a PUT.
- Choosing `로컬 복구본 불러오기` keeps the local recovery text recoverable while its save is pending and sends the latest observed `expected_revision`.

### Fix round 3 red evidence
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result before production fix, with the new unresolved-recovery lock probe:

```text
Running 15 tests using 1 worker
✓ serializes delayed per-chapter saves and preserves newer typing
✓ project switch rejects stale selected chapters and never writes under the new project context
✘ unresolved mismatched recovery locks editing, survives reload, and local choice remains recoverable while saving
Error: expect(locator).toBeVisible() failed
Locator: getByText('복구 선택 전에는 편집이 잠겨 있습니다.')
Expected: visible
1 failed, 12 did not run, 2 passed
```

This reproduced the re-review issue: the old unresolved mismatch state still left the editor active and had no clear lock/choice model for later typing.

### Fix round 3 green evidence
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result:

```text
Running 15 tests using 1 worker
15 passed (19.8s)
```

The expanded fixture includes:
- typing/reload while a mismatch is open, then local recovery choice while save is held;
- backend revision/body advancement plus server refresh, then server choice with no stale server-body PUT.

The fixture run used dedicated `127.0.0.1:15214`, `reuseExistingServer: false`, with all `/api/v1/*` requests mocked/guarded.

### Fix round 3 build evidence
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

### Fix round 3 limitations
- Still frontend fixture/browser QA only, not final real integration.
- No backend, QA script, `HANDOFF.md`, production DB, live LLM, dependency install, push, merge, or child review was used.

## Fix round 4 — recovery refresh failure and pending choice lifecycle

Review source: `docs/audits/preservation-final-spec-rereview-2.md`.

Changes made after commit `e9bcf86`:
- `refreshRecoveryServerText()` now returns an explicit success/failure boolean.
- Failed server refresh/server-choice GETs keep the unresolved recovery state, editor lock, and original browser draft intact.
- Refresh failures show the backend/API error in the recovery panel and leave retry/local-choice available.
- `clearRecovery()` only clears recovery and browser storage after a successful latest server-body refresh.
- Added a `recoveryActionPending` snapshot flag and a recovery action id.
- While a recovery server refresh/server-choice request is pending, local/server choice controls are visibly disabled and a Korean pending message is shown.
- Stale delayed recovery action responses are ignored if another recovery decision invalidates that action.

### Fix round 4 red evidence
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result before production fix, with the new failed-server-choice probe:

```text
Running 17 tests using 1 worker
✓ serializes delayed per-chapter saves and preserves newer typing
✓ project switch rejects stale selected chapters and never writes under the new project context
✓ unresolved mismatched recovery locks editing, survives reload, and local choice remains recoverable while saving
✓ server choice refreshes to latest paired server body and never PUTs stale displayed text
✘ failed server recovery choice keeps original draft locked until successful retry
Error: expect(locator).toBeVisible() failed
Locator: getByText('서버 원고를 새로고침하지 못했습니다.')
Expected: visible
1 failed, 12 did not run, 4 passed
```

This reproduced the re-review issue: failed server-choice refresh did not keep a visible failed-unresolved recovery state.

### Fix round 4 green evidence
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result:

```text
Running 17 tests using 1 worker
17 passed (21.0s)
```

The expanded fixture includes:
- failed server-choice GET leaves the exact original localStorage draft, lock, recovery UI, and no PUT;
- retry after the failure resolves to the latest paired server body/revision with no PUT;
- delayed server-choice latest-body GET disables competing local/server choice controls while pending, then resolves with no PUT.

The fixture run used dedicated `127.0.0.1:15224`, `reuseExistingServer: false`, with all `/api/v1/*` requests mocked/guarded.

### Fix round 4 build evidence
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
✓ built in 2.88s
```

The duplicate `build` key warning is pre-existing.

### Fix round 4 limitations
- Still frontend fixture/browser QA only, not final real integration.
- No backend, QA script, `HANDOFF.md`, production DB, live LLM, dependency install, push, merge, or child review was used.
