# Task 3 — Isolated real-surface verification

Backend Task1 reviewed PASS at836619b. Frontend Task2 reviewed PASS at84dcc4b; current scoped fixture13 tests + native build pass independently. See Task1/2 re-review reports.

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

## Current runtime and ownership
- Read docs/audits/preservation-integration-prep.md and docs/audits/manuscript-preservation-environment.md. Earlier environment launch snippets predate strict startup; USE scripts/preservation_backend_fixture.py instead, which explicitly Alembic-upgrades a fresh temp DB and unsets JIPPEEL_ALLOW_TEMP_CREATE_ALL before startup.
- Native Windows backend venv and Node required. No installs. No production DB/WAL/SHM/config/endpoints or existing services. Never use :8000/:5173. Dedicated backend18080; scoped fixture config now15201. Fail on occupied ports. Stop only processes this task created.
- scripts/preservation_* and docs/runbooks/manuscript-preservation.md now transfer from completed QA-prep worker to Task3 implementer; no other writer uses them. Also own new frontend/e2e preservation integration tests + dedicated config and docs/audits/preservation-final-validation.md. Do not modify feature source, existing fixture tests, parent ledger/HANDOFF or preexisting .eval_tmp artifacts.
- Existing backend fixture has synthetic character, relationship, lore, scene, foreshadow, volume-note records and full-row comparisons for11 tables. Parent independently reran PASS; evidence preservation-api-integration-expanded-result.json. Reuse instead of rebuilding.
- API integration must use real backend responses and DB writes; request interception may hold/forward/abort transport to create races, not substitute successful responses or revisions. Disable external calls with deterministic configured stubs. Verify browser outcomes against GET content/revision/snapshots.
- Cover rapid chapter switch, late typing during held real save, preview/reopen, project ownership, recovery/conflicts, stale refine accept after edits, scene merge, explicit snapshot restore. Include late replacement/edit race with real server response if practical; state which paths remain fixture-only.
- Full backend tests must set a fresh temp DATABASE_URL BEFORE pytest/app import; JIPPEEL_ALLOW_TEMP_CREATE_ALL=1 only for these explicitly temporary fixture tests. Historical populated migration tests include old nullable-volume chain with referring refine/relationship rows. Run through native backend interpreter.
- No merge/push/production deployment. Commit only assigned QA scripts/tests/config/runbook/report; preserve parent and preexisting untracked files. If feature defects are found, report concrete repro to parent for original implementer fix; do not hide failures or take over feature edits.
- No children. Explicit parent reply with commit, exact commands/results, isolation/cleanup evidence and limitations. Final branch review by independent worker follows.
