# M01–M05 final validation evidence — ready for parent verification/reviews

Evidence root: `/home/hunter8891/.pi/agent/sessions/--mnt-c-Users-wj941-Documents-jippeel--/recovery/memory-m01-m05-restart-szd8peci/verification-0fe42cf5`

## Scope and preservation

- Retained same-protocol continuation after workflow `0fe42cf5` timed out (`Subagent timed out after 1800000ms`), **after** completed exit-0 coverage conversion. Parent preservation: `../timeout-e73246d9/preservation.json`; continuation observation: `retained-continuation-check.json` and final exact-port check. No matching owned test/server processes; dedicated ports 15225/15228/15227 have no listeners. No 8000 connection.
- **No production or test edits since restart.** Only parent-approved Python mapping decision changed `docs/superpowers/plans/2026-09-12-memory-scoped-coverage.md`. This worker wrote owned evidence/tools only. Existing latest PATCH-retry and save-notification-fault tests were already present, not newly added here.
- Main HEAD `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`; index, retained backend `.coverage`, crypto/canon/bootstrap hashes unchanged; staged empty; short status matches restart. `final-protection.json`, `final-source/`, `final-status.txt`, `final-staged.txt` prove this. No stage/commit/push/reset/stash/cleanup, application imports outside guarded runner, real provider/DB/key/credential operations, or canonical status edits.

## Original M baseline (not restart/HEAD substitution)

`checkpoint-report.md`, `original-baseline-manifest.json`, `scope-reproduction-proof.json`, and `final-original-M-production.diff` retain provenance. MemoryPage recovered exact original SHA `2e09129dd5fd314cf68c362ac45cbda687ed7cce6c6ff64261686c659e84c143`; App/drafts are durable full reads independently verified against inverse acknowledged changes. projects.py is exact historical literal inverse; queryClient absent baseline is explicit. Original whole bounded snapshot is lost; not falsely reconstructed. Parent confirmed the recovered five-production-file scope before validation. All frozen changed/executable arrays exactly match original durable output; executable denominators 60/2/11/0/1 unchanged.

## Actual completed validation

All exact commands/cwd/exits/log hashes: `commands.jsonl`, `command-exit-summary.json` (no prior lost-run PASS substituted).

| Gate | Fresh result / artifact |
| --- | --- |
| Official native backend preflight | PASS, app/pytest not imported, violations=[]; `backend-recovery-preflight.log` |
| Official native backend full isolation coverage | **421 passed, 1 skipped, 70 subtests, 19 warnings**; subprocess_attempts=0, violations=[], fake keyring; `backend-recovery-full.log` |
| Memory full fixtures | **31 passed**, no escapes; `memory-recovery-full.log` |
| Preservation full fixtures | **26 passed**, no escapes; `manuscript-recovery-full.log` |
| AI fixture-only full | **15 passed**, no escapes; `ai-context-recovery-full.log` |
| Focused final memory / preservation | **25 / 9 passed**; `memory-recovery-focused-confirmed.log`, `manuscript-recovery-focused.log` |
| Lifecycle | Existing reload/page-close keepalive body/origin/revision shared-state regression passed in focused and full preservation; context close → in-flight drain → unregister unchanged |
| Unknown API negative | Expected suite **exit 1**, persistent GET `/api/v1/unregistered-tripwire-negative` latch, disposable owner/server; `fixture-recovery-negative.log`, `fixture-isolation/fixture-recovery-negative.violations.jsonl`. Never positive/coverage evidence |
| App TS / fixture helper TS / production build | All exit 0; `recovery-typescript-app.log`, `recovery-typescript-fixtures.log`, `recovery-production-build.log`; independent owned tsconfig and pinned Node types |
| Axe | Memory initial full-flow plus 8 keyboard focus matrix cases assert serious/critical zero (`memory-governance.spec.ts:124–130,412–413`); all passed in full31. Assertions/source and test log retained; no fabricated standalone scan JSON |
| Measurement checks | Standard V8 nested-range/uncovered/different-source-generated-map identity checks PASS; catch-filter RED→GREEN; Python direct-literal mapping **8 tests PASS**; sample identities duplicates/missing/external/hash negatives PASS |

Positive fixture isolation is documented in `fixture-isolation.json`: resolved no-proxy fail-closed guard, exact emitted latches, context owner and drain semantics. No browser unload/keepalive, queue/CAS, mocks' expected API meaning, or production server settings changed.

## Scoped source-mapped coverage

`mapped-recovery-full/summary.json`, `coverage-final.json`, eight raw-merged V8/actual JS/map/Istanbul groups, `source-transform-groups.json`, `samples-to-tests.json`, source snapshots and hashes retained.

| Production module | Changed executable lines | Branches on ALL changed source lines |
| --- | ---: | ---: |
| MemoryPage.tsx | **60/60 (100%)** | **33/33 (100%)** |
| manuscriptDrafts.ts | **2/2 (100%)** | 0/0 N/A |
| queryClient.ts | **11/11 (100%)** | **5/5 (100%)**, includes catch |
| App.tsx | 0/0 N/A (imports) | 0/0 N/A |
| projects.py | **1/1 mapped statement (100%)** | 0/0 N/A |

No executable-line filter is applied to branches: instrumented branch starts on any frozen changed source line are included. App is loaded and preserved even though changed denominator is zero. Missing/unmapped lines were not discarded. Whole-module reference coverage is separate: drafts whole-module branches **75%**, not a whole-module/V01 completion claim.

### 56 samples, 72 tests, 228 runtime entries, 8 groups

- Memory31 →31 samples; preservation26 →25 (explicit lifecycle page.close means existing collector skips closed page); AI15 →0 (imports base Playwright test, not optional coverage fixture). AI remains positive regression/isolation evidence, not coverage sample evidence.
- `samples-to-tests.json` links **every** sample to exact safe log hash, ordinal, source-named test/line/title and actual Playwright output-directory algorithm. Each sample has exact four expected unique source identities; **all 228 raw runtime entries** retain raw entry index, scriptId, function count and source/JS/map group.
- Duplicate drafts scriptIds50/295 in one sample are distinct runtime instances with **identical** source/JS/map hashes/group, NOT separate transforms. No instance dropped. Same identity groups standard raw V8 merge first; genuinely different transforms map separately, then standard Istanbul merge. Synthetic shape and identity checks are retained.

### Helper 3/4 → 5/5 denominator explanation

Historical 3/3 wrongly omitted catch; conservative **3/4=75%** was the correct previous gap. `helper-shape-comparison.json` is a fresh-run counterfactual, explicitly not recovered old raw data: excluding only fault-regression sample yields four branches with catch L18:2–20:3 count0; including it yields catch count1 plus newly represented V8 normal post-await range **L17:77–18:10 count19**, giving five. Counts reflect actual nested V8 range shape under synchronous notification fault, not a fixed arbitrary denominator or deleted branch. Final includes every test and all changed-line branches. `helper-branch-provenance.json` preserves exact locations/counts; restored incorrect historical converters remain inert evidence.

### Backend direct literal mapping

Raw coverage JSON SHA **2c0d379678e4427b4a3563b250a30a8db6429c9ced3eaaad59620556ab5cb5c9** unchanged. Literal L299 is **not raw instrumented** (absent executed/missing/excluded), and is not mislabeled raw covered. Parent-approved exact AST `Raise297–300 → Call(HTTPException) → keyword(detail) → Constant(str)L299` maps the single changed source line to executed Raise297. `backend-scoped-summary.json`, `map_backend_run.py`, `python_literal_mapping.py`, 8-test RED/GREEN evidence verify source hash, exact shape/range/literal, executed statement and draft/approved/retired exact-response regression. Wrong hash/missing statement/non-Raise/other function/conditional/lambda/wrong literal fail closed. No arbitrary descendant or general function mapping; no branch added by text-only literal.

## Failures preserved, not hidden

1. Original crash/timeout and parent's snapshots retained; old pre-crash suite launches are not final delivered results.
2. Initial backend-reader assertion incorrectly expected raw L299; compound shell continued to focused25 before noticing. `measurement-assertion-failure.txt`, failure diff/ref retained. Parent approved exact mapping; focused25 rerun separately as confirmed evidence. New commands fail-fast.
3. Packaging assertion incorrectly assumed four raw entries instead of four unique expected identities. `provenance-assertion-failure.json` and failed log retained; parent's correction distinguishes duplicate runtime instance from transform. Corrected exact-set/hash verification + synthetic negatives and successful package log retained.
4. Intentional catch-filter RED, Python missing-implementation RED, and dedicated tripwire negative are separate from positive evidence.

## Residual limits / next step

- Existing backend external metrics comparison skip remains unverified; 19 existing warnings and Vite outDir informational warning retained. No real provider, production DB, credentials, designated device, migration/deployment or later B03/D/V/G gate exercised.
- No live LSP tool was available to this worker; **no clean-LSP claim**. Actual app/helper `tsc` and build are the static evidence.
- Original entire bounded baseline and historical raw coverage lost; selected original production baseline is proven as described, not generalized.
- Tool dependencies are pinned owned validation-only installs with empty owned npm configs/public registry/scripts-audit-fund disabled; project package/lock unchanged. Evidence manifest excludes dependencies/cache/DB/key/private env contents.
- Parent readiness verification and **two fresh independent reviews remain pending**. This report does not mark M complete or change canonical ledgers. Recommended next step: verify manifest/report, then independent state/accessibility/regression and data/isolation/preservation reviews.

Primary manifest: `final-evidence-manifest.json`; final source identity: `final-protection.json`; command index: `command-exit-summary.json`. Ready means validation evidence prepared for those parent gates, not final product acceptance.
