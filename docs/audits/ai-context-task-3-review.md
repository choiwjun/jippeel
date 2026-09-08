# AI-context Task 3 independent review

Date: 2026-09-08
Branch/base: `feat/ai-context-consistency` reviewed against `46b1ec2704e1d0bb4a3c2abef8f862bb56631937`.
Scope: Task3 owned frontend source/test/config only. Existing dirty `HANDOFF.md`, progress docs, and unrelated untracked files were not attributed to the implementer.

## Verdict

- **Spec:** PASS after fix round 1 rereview.
- **Quality:** PASS after fix round 1 rereview.

Initial High finding is retained below as historical evidence. It was accepted and fixed in Fix round 1.

## Findings

### 1. High — stale canon provider result is displayed on a later chapter

- Source: `frontend/src/components/editor/CanonDialog.tsx:62-109`, `frontend/src/components/editor/CanonDialog.tsx:125-184`
- Spec/plan requirement: canon result/history must retain source origin/revision across later navigation and overlapping requests, or ignore stale display. Late completion must not clear/overwrite newer token/results.
- Problem: `useMutation` stores `run.data` without a request origin guard. After a canon request starts for chapter 10, closing the dialog and navigating to chapter 11 does not stop the in-flight POST. When the old POST resolves, `run.data` remains on the same `CanonDialog` instance. Reopening the dialog for chapter 11 renders the old issue text because render only checks `run.data`, not `run.data.chapter_id` or captured origin/revision.
- Repro evidence: `.eval_tmp/ai-context-task-3-review/canon-stale-repro/canon-stale.spec.ts:15` and log `.eval_tmp/ai-context-task-3-review/canon-stale-repro-run.txt`.
- Repro command:

```cmd
cmd.exe /C "set NODE_PATH=C:\Users\wj941\Documents\jippeel\frontend\node_modules&& cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config C:\Users\wj941\Documents\jippeel\.eval_tmp\ai-context-task-3-review\canon-stale-repro\playwright.config.ts"
```

- Result: `1 failed, 1 passed`. The failing assertion found `OLD_STALE_QUOTE` visible after navigation to chapter 2:

```text
expect(locator).not.toBeVisible() failed
Locator: getByText('OLD_STALE_QUOTE')
Received: visible
```

This is an actual request-lifecycle defect, not only missing test coverage. The repro captures the outgoing canon request body and the visible stale UI result.

## Required native verification

All required project gates were rerun with native Windows commands and dedicated fixture ports.

### Build

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build"
```

Evidence: `.eval_tmp/ai-context-task-3-review/build-windows.txt`

Result: PASS, exit 0. Vite emitted the pre-existing duplicate `build` key warning. Build output ended with `✓ built in 2.84s`.

### New Task3 browser fixture

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.ai-context.fixture.config.ts"
```

Evidence: `.eval_tmp/ai-context-task-3-review/ai-context-fixture.txt`

Result: PASS, `4 passed (8.7s)`. Config uses port `15227`, `reuseExistingServer=false`, one worker. `vite.ai-context.fixture.config.ts` has no backend proxy. The fixture route explicitly fails unknown `/api/v1/**` requests with 599 and does not use `APIRequestContext`.

### Preservation regression fixture

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts"
```

Evidence: `.eval_tmp/ai-context-task-3-review/preservation-fixture.txt`

Result: PASS, `17 passed (25.9s)`. Config uses port `15225`, `reuseExistingServer=false`, one worker.

## Fixture-vs-real limits

- These checks are frontend browser fixtures plus a bounded repro.
- They inspect outgoing requests and visible editor/dialog behavior.
- They do not use a real backend, SQLite database, real provider, production DB/WAL/SHM, services, secrets, or default ports `8000`/`5173`.
- Task4 real API/SQLite/provider integration remains explicitly deferred.
- No model quality or literary quality claim is made.

## Source hashes before/after review

No Task3 source/test/config files were changed by this review. Hashes before and after match.

```json
{
  "frontend/src/stores/aiPanelStore.ts": "f2e07de46db9ee549f7edff45840c7f664f7ac22dd4c8249cba913cf8a64bfc0",
  "frontend/src/components/panels/AiPanel.tsx": "193a27c66bc1d041d812e0b06c7b2eb074c1cfb0c79be0c9de2070fbf788fb31",
  "frontend/src/components/editor/CanonDialog.tsx": "a765a981779a5dec4a6c13e0c139eb5312e2232c49996d5a98775815ce77cf3c",
  "frontend/src/components/editor/QualityDialog.tsx": "1ac11a793afd69e231f818f56a8ca3a381934677e7534e6dffffc0391b1210ca",
  "frontend/src/pages/EditorPage.tsx": "578948a3ae1d2dc3ab3734e96a6bb375f2a4f6e2138e80097befefe768969d3d",
  "frontend/src/lib/aiStream.ts": "84ffb6c258528b939330314ff992b434b2b550d8fadeffd78680fcb71d64f768",
  "frontend/src/components/editor/AiContextControls.tsx": "2765f4cc0453f891c975551ba463ee51dda30da00bf21bb85f9c0eb4314659d9",
  "frontend/e2e/ai-context-ui.spec.ts": "d706756408498f5daf3211d0bf74c442eed2ccaf4241e38ec58a2681b4b30523",
  "frontend/playwright.ai-context.fixture.config.ts": "b0b41da073b8a59ec22fee654c8b6b1e7419f051b543ee1afb45028b2bad09b6",
  "frontend/vite.ai-context.fixture.config.ts": "a17af72251710c2dc9c6efc1aa9eddfa9369f9f42a0e2bfa1a47ebfb7d012a91"
}
```


---

# AI-context Task 3 rereview 1 — stale canon lifecycle fix

Date: 2026-09-08
Scope: only Fix round 1 changes to `frontend/src/components/editor/CanonDialog.tsx` and `frontend/e2e/ai-context-ui.spec.ts` since the initial review. Source frozen during this rereview.

## Verdict

- **Spec:** PASS for the scoped stale-canon/lifecycle fix.
- **Quality:** PASS for the scoped stale-canon/lifecycle fix.

## Result

The accepted High finding from the initial review is fixed.

Verified in source:

- `frontend/src/components/editor/CanonDialog.tsx:92-103` checks same active token, dialog lifetime, request project/chapter, store token, and current editor identity before accepting work.
- `frontend/src/components/editor/CanonDialog.tsx:145-156` rejects failed/abandoned flushes and stale pre-provider starts.
- `frontend/src/components/editor/CanonDialog.tsx:164-180` accepts a provider response only while the same request is still active and `response.chapter_id` matches the captured origin. The `finally` cleanup only clears the owned token.
- `frontend/src/components/editor/CanonDialog.tsx:184-195` increments dialog lifetime and clears active request/display on close.
- `frontend/src/components/editor/CanonDialog.tsx:203-205` renders only display data whose origin still matches the current project/chapter.
- `frontend/src/components/editor/CanonDialog.tsx:251-252` shows captured origin plus backend checked revision/hash.
- `frontend/src/components/editor/CanonDialog.tsx:174` invalidates canon history for the captured origin chapter.

Verified in tests:

- `frontend/e2e/ai-context-ui.spec.ts:427-445` covers delayed chapter A canon result ignored after navigation to chapter B.
- `frontend/e2e/ai-context-ui.spec.ts:447-465` covers close, visit B, return A, and no cancelled-result resurrection.
- `frontend/e2e/ai-context-ui.spec.ts:467-504` covers older delayed success/failure not overriding a newer completed result.

No new findings in this scoped rereview.

## Fresh evidence

### Prior delayed-canon reviewer repro

Command:

```cmd
cmd.exe /C "set NODE_PATH=C:\Users\wj941\Documents\jippeel\frontend\node_modules&& cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config C:\Users\wj941\Documents\jippeel\.eval_tmp\ai-context-task-3-review\canon-stale-repro\playwright.config.ts"
```

Evidence: `.eval_tmp/ai-context-task-3-review/rereview-1-canon-stale-repro.txt`

Result: PASS, `2 passed (4.7s)`. This reran the original failing delayed-canon repro plus the pending-generate navigation guard repro.

### New Task3 fixture suite

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.ai-context.fixture.config.ts"
```

Evidence: `.eval_tmp/ai-context-task-3-review/rereview-1-ai-context-fixture.txt`

Result: PASS, `7 passed (12.3s)`. Config uses port `15227`, `reuseExistingServer=false`, one worker. Unknown `/api/v1/**` requests explicitly fail in the fixture.

### Preservation regression fixture

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts"
```

Evidence: `.eval_tmp/ai-context-task-3-review/rereview-1-preservation-fixture.txt`

Result: PASS, `17 passed (26.4s)`. Config uses port `15225`, `reuseExistingServer=false`, one worker.

### Native frontend build

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build"
```

Evidence: `.eval_tmp/ai-context-task-3-review/rereview-1-build-windows.txt`

Result: PASS, exit 0. Vite emitted the pre-existing duplicate `build` key warning. Build output ended with `✓ built in 2.82s`.

## Source hashes before/after rereview

Before hashes matched `docs/audits/ai-context-task-3-rereview-1-snapshot.json`. After hashes matched before. No Task3 source/test/config file changed during rereview.

```json
{
  "frontend/src/stores/aiPanelStore.ts": "f2e07de46db9ee549f7edff45840c7f664f7ac22dd4c8249cba913cf8a64bfc0",
  "frontend/src/components/panels/AiPanel.tsx": "193a27c66bc1d041d812e0b06c7b2eb074c1cfb0c79be0c9de2070fbf788fb31",
  "frontend/src/components/editor/CanonDialog.tsx": "7eb3d5ce04903b6cdaaf3f35327abcbaa1041aa061ae12c8eaa2136058e273eb",
  "frontend/src/components/editor/QualityDialog.tsx": "1ac11a793afd69e231f818f56a8ca3a381934677e7534e6dffffc0391b1210ca",
  "frontend/src/pages/EditorPage.tsx": "578948a3ae1d2dc3ab3734e96a6bb375f2a4f6e2138e80097befefe768969d3d",
  "frontend/src/lib/aiStream.ts": "84ffb6c258528b939330314ff992b434b2b550d8fadeffd78680fcb71d64f768",
  "frontend/src/components/editor/AiContextControls.tsx": "2765f4cc0453f891c975551ba463ee51dda30da00bf21bb85f9c0eb4314659d9",
  "frontend/e2e/ai-context-ui.spec.ts": "de806660725cc41ae4162b20bb25a91163f253617ff355fbc0342e44332d5d2f",
  "frontend/playwright.ai-context.fixture.config.ts": "b0b41da073b8a59ec22fee654c8b6b1e7419f051b543ee1afb45028b2bad09b6",
  "frontend/vite.ai-context.fixture.config.ts": "a17af72251710c2dc9c6efc1aa9eddfa9369f9f42a0e2bfa1a47ebfb7d012a91"
}
```

## Limits

- This was a scoped frontend fixture rereview.
- It did not use real backend services, SQLite, providers, production DB/WAL/SHM, default ports `8000`/`5173`, or unmocked APIRequestContext.
- Task4 real API/SQLite/provider integration remains deferred.
- No model output quality or literary quality claim is made.
