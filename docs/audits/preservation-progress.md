# SDD ledger — plan: docs/superpowers/plans/2026-09-07-manuscript-preservation.md

Base: b6a9ee6a4452f926a1933f23059d2f5bdb84f63e
Branch: feat/manuscript-preservation
Approved: user's 진행해 after explicit first-stage design.
Baseline: backend native Windows Python, temporary lifespan DATABASE_URL, 201 passed / 1 existing deprecation warning.

Ruling: Use a dedicated local branch in current checkout, not a new worktree — new worktree consent absent, preserve dirty files — cost if wrong: user may prefer later relocation.
Ruling: Use available openai-codex/gpt-5.5 for implementation/review — requested ox-alpha-free unavailable — cost if wrong: model cost/routing preference difference, no feature scope change.
Ruling: expected_revision is mandatory (422 when missing) — compatibility fallback would bypass safety — cost if wrong: old callers fail until updated; coordinated frontend/backend deployment required.

## Current result — source 42fad7c

**Approved preservation-only implementation complete; production deployment not performed.**

- Backend Task1 and frontend Task2 implemented; Task3 real-surface QA complete.
- Final Standards: PASS at fbdb796, backend fix re-review PASS at409c268. Minor optional duplication suggestions deferred; no blocking quality finding.
- Final Spec: PASS after recovery fix42fad7c, zero open required findings. See [final Spec re-review3](preservation-final-spec-rereview-3.md).
- Independent native verification: backend222 passed; frontend fixture17 passed; real backend browser integration1 passed; production build passed. See [validation](preservation-final-validation.md) for commands, evidence and coverage limits.
- SQLite API/backup probes compare full rows in11 selected creative/history tables. Populated old-schema migrations are separately covered. No production data or real model quality was tested.
- Remaining boundary: no merge/push/deployment; frontend/backend require coordinated update and explicit migration after backup/copy rehearsal. [Runbook](../runbooks/manuscript-preservation.md).
- Narrative memory, story planning and ending support remain future work. Snapshot history is not a database backup.
- Parent final native repeat at42fad7c also passed backend222, fixture17, real integration1 and build; raw outputs are preservation-final-root-backend.txt and preservation-final-root-frontend.txt.
- Reusable verification rules: [cycle lessons](preservation-lessons.md).

## Historical implementation and review log

The entries below record the state when written. Older pending/blocking states and test counts are superseded by the current result above.

## Preflight interface/self-consistency scan
| Tasks | Shared interface/files | Finding |
|---|---|---|
| 1/2 | ChapterDetail.revision; write payloads; refine accept response; snapshot API | Explicit contract; Task 2 begins after Task 1 review. |
| 1/3 | DB migrations/temporary app startup | Task 3 read/verify only; fixes return to Task 1. |
| 2/3 | frontend E2E config | Sequential, fixture tests distinct from API integration. |
| 1 self | mandatory revision vs existing callers | Update each test/script caller; regression for omission retained. |
| 2 self | draft coordinator vs Query cache | Local draft owns unsaved value; successful response cannot overwrite newer input. |
| 3 self | integration vs production safety | Dedicated ports/temporary DB; no live endpoints. |

- Task 1: implementation ff7b02b; implementer reports 215 passed. Independent review preservation-backend-reviewer running; not yet approved.
- Task 2: pending Task 1 review
- Task 3: pending integrated implementation
- QA environment: complete — native Windows Node v22.23.2/npm 10.9.8/Playwright 1.62.1; fresh TypeScript and build passed, existing Vite duplicate build warning. See manuscript-preservation-environment.md. Integration uses new temporary DB and dedicated port (suggested 18080); never reuse checked-in Playwright default :5173/:8000.

## Contract review disposition
Ruling: Require expected_revision at refine start too — closes stale input capture before expensive pipeline — cost if wrong: older refine clients must update.
Ruling: Clarify atomic no-op and permit guarded UPDATE before snapshot INSERT in one transaction — snapshot-first ordering is not mandatory and does not alone prove concurrency safety — cost if wrong: requires concurrency/rollback rework; must pass dedicated tests.
Ruling: Persist every edit before debounce, preserve structured ApiError and sequence-aware cleanup — recovery must cover pre-debounce and in-flight input — cost if wrong: synchronous browser storage may need measured performance tuning; failures remain visible.
Ruling: Guard normal startup before any schema bootstrap, including empty normal DB — prevents unmanaged partial upgrade — cost if wrong: first-run setup now requires explicit migration; documented runbook required.
- Spec/plan contract review findings integrated; Task 1 implementer notified. Task 2/3 remain pending.

- Task 1: fix round 1/5 started; review BLOCKED (ff7b02b). Open: stale current_revision in no-op/unique-failure conflicts; DB-backed rollback + no-op race + populated older FK-chain coverage; restore revision cases; engine-specific schema bypass hardening. Fix worker is original preservation-backend-implementer. Frontend remains pending Task1 review.
Ruling: Populate historical migration test with referencing refine rows, not only chapter — original audit FK failure requires referenced data — cost if wrong: broader test setup only, production DB remains untouched.

- Task 1: fix round 1/5 implementation complete at 836619b; implementer focused23/full221 passed. Scoped re-review of ff7b02b..836619b requested from preservation-backend-reviewer; waiting verdict before frontend.

- Task 1: complete (commits b6a9ee6..836619b, independent spec PASS and quality PASS). Reviewer independently reran focused23/full221 passed; no findings remain.
- Task 2: starting preservation-frontend-implementer at base 836619b. Interface now includes mandatory expected_revision at refine start as well as writes/merge/restore.

- QA integration preparation runs independently of Task2: preservation-integration-prep owns new scripts/preservation_* and its report/runbook only. No shared frontend/backend edits or git commits. Final browser QA still waits for reviewed Task2.

- QA prep: backend-only API fixture PASS on fresh Alembic-migrated temporary DB at :18080, temp-create bypass unset. Stale write/refine blocked; accept+restore worked; exact selected columns of 5 fixture tables matched SQLite backup. Raw synthetic result preserved in preservation-api-integration-result.json. No browser claim; fixture process stopped.

- QA backup hardening: worker reports PASS for full-row equality of 11 tables (including creative records), source URI mode=ro, new destination only. Runbook now provides manual SQLite backup/verification code. Parent independent repeat started; separate result will be preservation-api-integration-expanded-result.json. Not a production/credential restore or browser verification.

- Parent independent native API/backup repeat: exit0 PASS; fresh temp DB, strict Alembic startup, same stale write/refine/restore checks and 11-table full-row comparison passed. Evidence: preservation-api-integration-expanded-result.json.

- Task 2: implemented at 28a6c90. Implementer reports8 fixture browser tests and native build PASS. Independent spec+quality review dispatched to preservation-frontend-reviewer. Real-backend browser Task3 remains pending review approval.

- Task 2 review BLOCKED at28a6c90: independent adversarial browser probe reproduced late local edit lost when pending refine accept completes (unconditional replacement helper also used by merge/restore). Existing8 tests/build pass but insufficient. Original implementer assigned fix round1/5: sequence-aware replacement acknowledgements across all3 paths, regression tests, negative lost-ack and unload coverage. Task3 still held.

- Task 2 fix round1 implemented at84dcc4b: sequence-aware replacement tokens for accept/merge/restore, late text/storage preserved. Implementer reports13 fixture tests/native build PASS (dedicated15201). Independent scoped re-review requested from preservation-frontend-reviewer; Task3 still pending verdict.

- Task 2 complete: independent spec PASS/quality PASS at84dcc4b. Fresh13 fixture tests/build pass; reviewer additional late-edit retry and chapter-switch ownership probes pass.
- Task 3 started: preservation-integration-implementer owns QA artifacts/scripts/new integration tests; brief preservation-task-3-brief.md. Real temp backend browser integration and final native suites, followed by independent final branch review.

- Task3 QA committed fbdb796: real browser integration1 PASS, fixture13 PASS, backend221 PASS, build PASS, API11-table backup and populated migration probes PASS. Scope limitations in preservation-final-validation.md.
- Final branch review started for b6a9ee6...fbdb796 on two independent axes: Standards owns temp backend tests/no ports; Spec owns frontend build+fixture+real browser ports18080/15201/15202. Await both verdicts before completion.

- Final review atfbdb796: Standards PASS (0hard/0blockers/2optional duplication smells; fresh backend221 + migration PASS). Spec CHANGES REQUESTED (High unresolved recovery draft can be removed by no-op flush; Medium refine response/report captured base_revision missing). Fresh13 fixture/1 real browser/build pass but do not cover High.
- Fixes assigned original backend/frontend workers in disjoint source scopes. Backend owns current commit slot; frontend must hold staging/commit pending parent authorization. No optional refactor scope. Final review will repeat on fixes.

- Backend final fix409c268: required captured base_revision response/report, input_content_md report; concurrent pipeline revision regression. Implementer full222 PASS. Standards scoped backend re-review requested. Frontend commit slot released; recovery preservation fix remains active.

- Backend final fix409c268 independently PASS: Standards re-review0hard/0blockers, required response/report base capture verified, native full222 passed. Evidence preservation-final-standards-rereview-1.md. Frontend recovery fix and final Spec re-review/integration still pending.

- Frontend final fix9f10107: unresolved mismatched recovery blocks flush/pre-actions and survives Ctrl+S/reload until explicit choice; required frontend base_revision. Implementer fixture14/build PASS (port15210). Final Spec re-review requested of fbdb796..9f10107 with fresh14 fixture + actual integration + build. Backend independently passed222; overall completion still pending Spec verdict.

- Final Spec re-review1 CHANGES REQUESTED at9f10107: backend base_revision RESOLVED; recovery High PARTIAL (new input during unresolved recovery not persisted; cache/server-choice stale body risk). Fresh14 fixture/1 real integration/build pass but miss these paths. Original frontend assigned fix round3/5 for coherent unresolved state, accepted-edit durability and latest server body/revision pair on explicit choice; expanded regression probes required.

- Frontend fix round3 e9bcf86 implemented: explicit editing lock until recovery choice, refreshed server body/revision pair, server choice GET/no PUT, local choice persisted while pending save. Implementer15 fixture/build PASS (15214). Final Spec re-review2 requested with actual15 fixture + real integration1 + build; overall completion still pending verdict.

- Final Spec re-review2 CHANGES REQUESTED at e9bcf86: remaining High failed GET in refreshRecoveryServerText is swallowed; clearRecovery continues and may delete local recovery/unlock stale text. Lock/success refresh/local pending durability pass, base_revision remains resolved. Fresh15 fixture/1 integration/build PASS omit failed refresh path. Original frontend assigned fix round4/5 with failure+retry and overlapping-choice regressions; final approval pending.

- Frontend fix round4 at42fad7c: explicit refresh success/failure, failed server-choice preserves recovery+storage+lock/error/retry; pending action id and disabled choices reject overlap. Implementer17 fixture/build PASS (15225). Final Spec re-review3 requested with fresh17 fixture +1 real integration +build; no completion claim before verdict.
