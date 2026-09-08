# Preservation Task 2 Review — Frontend manuscript preservation

## Verdict
- **Spec:** BLOCKED
- **Quality:** CHANGES REQUESTED

The checked-in fixture suite and build pass, but an adversarial race loses a user edit after a refine-accept response. This violates the Task 2 requirement that late edits during flush/replacement must not be discarded.

## Scope reviewed
- Branch: `feat/manuscript-preservation`
- Diff: `836619b..28a6c90`
- Source mode: read-only. I did not fix source, stage, commit, run backend integration, touch production DB/WAL/SHM, call LLM services, or install dependencies.
- Backend at `836619b` was treated as already approved and was not re-reviewed.
- Frontend fixture config used only `frontend/playwright.preservation.config.ts` on `127.0.0.1:15193` with `reuseExistingServer: false`.

## Fresh verification

### Build
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
```

Result: **PASS** (`exit 0`). Vite emitted the existing duplicate `build` key warning in `vite.config.ts`, then built 229 modules.

### Checked-in preservation fixture suite
Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts --reporter=list
```

Result: **PASS** (`exit 0`).

```text
Running 8 tests using 1 worker
8 passed (12.1s)
```

### Reviewer adversarial probe
I added a temporary probe file, ran it through the same preservation config, then removed the temporary copy from `frontend/e2e/reviewer-probes`. A copy remains under `.eval_tmp/task2-review/manuscript-preservation.spec.ts` for audit.

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test e2e/reviewer-probes/manuscript-preservation.spec.ts --config playwright.preservation.config.ts --reporter=list
```

Result: **FAIL** (`exit 1`).

Reproduction:
1. Open project 1, chapter 10.
2. Type `before refine`.
3. Open the refine report and run refine.
4. Click `수락`, but hold the `/refine/runs/900/accept` response.
5. Close the right panel and type `late local edit` while the accept response is still pending.
6. Release the accept response with content `before refine\nrefined`.

Observed failure:

```text
Expected substring: "late local edit"
Received string:    "before refinerefined"
frontend\e2e\reviewer-probes\manuscript-preservation.spec.ts:243:47
```

## Findings

### 1. BLOCKER — Refine accept can discard a later local edit
- Source: `frontend/src/components/panels/RefineReport.tsx:61-76`
- Source: `frontend/src/lib/manuscriptDrafts.ts:149-164`, `233-235`, `540-541`

`accept.mutationFn` flushes the current draft, then sends `/refine/runs/{id}/accept`. While that accept response is pending, a user can close the panel and continue editing. On success, `onSuccess` calls `applyManuscriptServerDetail(...)`, which calls `initFromServer(detail, true)`. The `force` branch unconditionally sets `this.text = detail.content_md`, increments `editSequence`, marks saved, and removes the local draft.

That path does not compare the replacement start sequence with the current edit sequence. It also does not preserve the later local draft as dirty/conflict. The pending accept response can therefore replace a newer local edit with the refined server text.

This is not only missing test coverage. The probe reproduced the data loss in the browser fixture.

The same unconditional replacement helper is also used by scene merge and snapshot restore:
- `frontend/src/components/panels/SceneManager.tsx:101-106`
- `frontend/src/pages/EditorPage.tsx:346-361`

Those paths need the same sequence-aware protection, even though I reproduced the bug through refine accept.

## Coverage notes
- Existing tests cover the happy delayed-save race, project switch, structured 409, storage failure, positive lost-ack reconciliation, refine stale accept, scene trigger/merge, and snapshot preview/restore.
- Existing tests do **not** cover a negative lost-ack reconciliation where GET returns different text.
- Existing tests do **not** exercise `beforeunload` or `pagehide` behavior.
- Existing tests do **not** cover late edits made after replacement actions are requested and before their responses arrive. The reviewer probe covers refine accept and fails.

## Recommendation
Request changes before Task 3. Make replacement actions sequence-aware. If the local edit sequence advances after the replacement action starts, do not clear or overwrite the local draft. Show a conflict/recovery state or keep the late text dirty and usable.
