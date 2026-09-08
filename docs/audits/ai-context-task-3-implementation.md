# AI-context Task 3 Implementation

- Date: 2026-09-08
- Branch: `feat/ai-context-consistency`
- Base commit: `46b1ec2704e1d0bb4a3c2abef8f862bb56631937`
- Scope: frontend request ownership, shared in-memory controls, browser fixture tests only.
- Fixture port: `15227` strict, `reuseExistingServer=false`.
- Fixture Vite config: `frontend/vite.ai-context.fixture.config.ts` has no backend proxy.
- Evidence directory: `.eval_tmp/ai-context-task-3/`

## Changed files owned by Task 3

Production:
- `frontend/src/stores/aiPanelStore.ts`
- `frontend/src/components/panels/AiPanel.tsx`
- `frontend/src/components/editor/CanonDialog.tsx`
- `frontend/src/components/editor/QualityDialog.tsx`
- `frontend/src/pages/EditorPage.tsx`
- `frontend/src/lib/aiStream.ts`
- `frontend/src/components/editor/AiContextControls.tsx`

Tests/config:
- `frontend/e2e/ai-context-ui.spec.ts`
- `frontend/playwright.ai-context.fixture.config.ts`
- `frontend/vite.ai-context.fixture.config.ts`

Not changed by Task 3:
- backend production source
- `frontend/src/lib/api.ts`
- prior preservation tests/config
- `HANDOFF.md`

## TDD RED

Command:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.ai-context.fixture.config.ts --grep generation --timeout=20000
```

Evidence: `.eval_tmp/ai-context-task-3/red-generation-playwright.txt`

Result: RED. The first fixture test failed before production edits because the old UI did not expose `현재 회차 본문 포함` / Task3 request controls.

## GREEN verification

### Build

Command:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npm run build
```

Evidence: `.eval_tmp/ai-context-task-3/build-green.txt`

Result: PASS. Vite still prints the pre-existing duplicate `build` key warning in `vite.config.ts`.

### New AI-context fixture tests

Command:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.ai-context.fixture.config.ts
```

Evidence: `.eval_tmp/ai-context-task-3/ai-context-fixture-green.txt`

Result: `4 passed (8.6s)`.

Covered:
- generate waits for manuscript flush and sends one captured pre-await form snapshot with saved revision
- duplicate pending generate start rejected
- failed flush, panel close, and navigation away cancel pending provider starts
- changed controls during pending flush affect the next request only
- result from another chapter blocks insert/replace and leaves copy enabled
- shared purpose/payoff/relationship controls feed generate, canon, and quality
- finale brief sends `ending_intent` without forcing `next_hook`
- quality uses purpose-specific query key and displays hook applicability
- all `/api/v1/**` fixture requests are intercepted; unknown API requests fail; no real backend/provider/DB/default ports are used

### Preservation fixture regression

Command:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.preservation.config.ts
```

Evidence: `.eval_tmp/ai-context-task-3/preservation-fixture-green.txt`

Result: `17 passed (26.4s)`.

### Backend compatibility smoke

Command:

```powershell
cd C:\Users\wj941\Documents\jippeel
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set DATABASE_URL=sqlite:///%TEMP%/jippeel-ai-context-task3-backend-%RANDOM%.db
set JIPPEEL_ALLOW_TEMP_CREATE_ALL=1
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_context_bundle.py backend\tests\test_ai_context_directives.py -q
```

Evidence: `.eval_tmp/ai-context-task-3/backend-compat-green.txt`

Result: `35 passed, 1 warning in 3.09s`.

## Fixture-vs-real limits

- The new Task3 Playwright suite is a frontend browser fixture.
- It asserts outgoing request bodies and UI state.
- It does not use a real backend, SQLite DB, real provider, or production service.
- Task4 still owns real temporary API/SQLite/provider/browser integration.


## Fix round 1 — stale canon result lifecycle

Accepted review finding: a delayed canon result for chapter A could render after navigating to chapter B because `CanonDialog` stored unqualified mutation data.

Fix:
- Canon requests now capture an immutable token, dialog lifetime, project, chapter, and saved revision.
- The dialog checks the token/lifetime/current editor identity after flush and after the POST awaits.
- The result is accepted only if the response chapter matches the captured request origin.
- Closing or navigation cancels the request lifetime and clears pending display.
- Late success/failure cleanup is conditional on owning the same token, so old callbacks cannot clear or override newer runs.
- The current result renders a visible origin line: `검사 기준 — 작품 #... · 회차 #... · rev ... · hash ...`.
- History invalidation uses the captured response/request chapter, not the mutable prop at callback time.

### TDD RED for fix round 1

Command:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.ai-context.fixture.config.ts --grep delayed --timeout=30000
```

Evidence: `.eval_tmp/ai-context-task-3/round1-red-delayed-canon.txt`

Result: RED before the source fix. The delayed chapter A canon result rendered `OLD_STALE_QUOTE` after navigating to chapter B.

### Fix round 1 GREEN verification

Build command:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npm run build
```

Evidence: `.eval_tmp/ai-context-task-3/round1-build-green.txt`

Result: PASS, exit 0. Vite still reports the pre-existing duplicate `build` key warning.

New fixture command:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.ai-context.fixture.config.ts
```

Evidence: `.eval_tmp/ai-context-task-3/round1-ai-context-fixture-green.txt`

Result: `7 passed (12.6s)`.

Reviewer repro command:

```cmd
cmd.exe /C "set NODE_PATH=C:\Users\wj941\Documents\jippeel\frontend\node_modules&& cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config C:\Users\wj941\Documents\jippeel\.eval_tmp\ai-context-task-3-review\canon-stale-repro\playwright.config.ts"
```

Evidence: `.eval_tmp/ai-context-task-3/round1-reviewer-repro-green.txt`

Result: `2 passed (5.6s)`.

Preservation regression command:

```powershell
cd C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.preservation.config.ts
```

Evidence: `.eval_tmp/ai-context-task-3/round1-preservation-fixture-green.txt`

Result: `17 passed (26.2s)`.
