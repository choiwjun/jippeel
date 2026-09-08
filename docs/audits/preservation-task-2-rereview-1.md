# Preservation Task 2 Re-review 1 — Fix round 1

## Verdict
- **Spec:** PASS
- **Quality:** PASS

The original blocker from `docs/audits/preservation-task-2-review.md` is addressed in the fix diff `28a6c90..84dcc4b`. I found no new blocking issue in the reviewed frontend diff.

## Scope reviewed
- Branch: `feat/manuscript-preservation`
- Fix diff: `28a6c90..84dcc4b`
- Reviewed files changed in fix round 1: `frontend/src/lib/manuscriptDrafts.ts`, `frontend/src/components/panels/RefineReport.tsx`, `frontend/src/components/panels/SceneManager.tsx`, `frontend/src/pages/EditorPage.tsx`, `frontend/e2e/manuscript-preservation.spec.ts`, `frontend/playwright.preservation.config.ts`, and the updated Task 2 report.
- Source mode: read-only. I did not fix source, stage, commit, run backend integration, touch production DB/WAL/SHM, call LLM services, or install dependencies.
- Backend remains out of scope for this Task 2 re-review.
- Current preservation Playwright config uses `http://127.0.0.1:15201`, `reuseExistingServer: false`.

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
Running 13 tests using 1 worker
13 passed (16.1s)
```

### Reviewer adversarial probes
I created temporary Playwright probes under `frontend/e2e/reviewer-rereview`, ran them with the same preservation config, then removed that temporary source-tree directory. Copies are saved under `.eval_tmp/task2-rereview-1/` for audit.

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test e2e/reviewer-rereview/manuscript-preservation.spec.ts --config playwright.preservation.config.ts --reporter=list
```

Result: **PASS** (`exit 0`).

```text
Running 2 tests using 1 worker
✓ late refine accept then manual retry saves latest local text on accepted revision
✓ late refine accept after closing and chapter switch keeps result on original chapter
2 passed (4.7s)
```

Additional restore ownership probe:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test e2e/reviewer-rereview/manuscript-preservation.spec.ts --config playwright.preservation.config.ts --reporter=list
```

Result: **PASS** (`exit 0`).

```text
Running 1 test using 1 worker
✓ late snapshot restore after chapter switch keeps result on original chapter
1 passed (3.5s)
```

## Review findings

No blocking findings.

The fix adds a `ManuscriptReplacementToken` and sequence-aware completion path:
- `frontend/src/lib/manuscriptDrafts.ts:241-296` captures chapter-owned edit sequence/text/revision and treats response completion as `applied`, `late_edit`, or `ignored`.
- Late replacement responses update server revision/server text, keep the newer local text in browser storage, and surface a conflict instead of overwriting the editor.
- The manual retry path then saves the local text with the accepted server revision. The reviewer probe verified retry sends the late local text with `expected_revision: 2` after the held accept response resolves at revision 2.

Replacement callers now capture a token after flush and before the replacement request:
- Refine accept: `frontend/src/components/panels/RefineReport.tsx:61-83`
- Scene merge: `frontend/src/components/panels/SceneManager.tsx:93-113`
- Snapshot restore: `frontend/src/pages/EditorPage.tsx:346-368`

The checked-in tests plus reviewer probes cover the original blocker and the requested adversarial points:
- newest local storage is not removed by a late replacement response,
- late response after chapter switch stays owned by the original chapter,
- subsequent retry saves the preserved local text instead of silently losing it,
- negative lost-ack GET does not acknowledge a different server text,
- pagehide uses the revision contract and beforeunload leaves recoverable text.

## Notes
- I did not re-review unchanged backend behavior.
- I did not run default Playwright config, `:5173`, `:8000`, live backend, production DB, or LLM services.
