# Independent M01–M05 behavioral review

**REVIEW_GATE PASS**

## Review

**No issues found.**

- **Correct — M01 route and screen-instance isolation.** `frontend/src/pages/MemoryPage.tsx:79–108` keys the inner screen by route pid and gives each instance its own mounted guard, form/filter state, confirmation and mutations. Requests and invalidations use the submitted `originPid` (`:125–160,205–215,492–499`); obsolete instances cannot clear inputs, confirmations or emit mutation toasts. Returning A is a fresh instance, not the original A. The eight POST/PATCH × success/failure × A→B/A→B→A cases in `frontend/e2e/memory-governance.spec.ts:255–323` inspect request URL/body, current input/enabled/focus state, confirmation, absent toasts and origin-only query reads. Pending-create cases (`:189–240`) preserve all input values on failure and retain the selected kind after success. The latest current-screen PATCH failure case (`:440–458`) checks the actual failure toast, retained confirmation/body, pending release and successful retry.

- **Correct — M02 acknowledgement lifetime and preservation.** `frontend/src/App.tsx:12–21` uses the same exported QueryClient as `frontend/src/lib/queryClient.ts`. `manuscriptDrafts.ts:342–389,499–524` performs origin-project memory refresh after identity validation at both replacement completion and save acknowledgement. The coordinator outlives the UI subscription (`:639–671,712–718`), so editor unmount does not remove this cache effect. The production diff adds only the import and two refresh calls to the coordinator; serialized writes, expected revision, lost-ack reconciliation, recovery and late-edit handling remain intact. The helper (`queryClient.ts:14–20`) skips unchanged/undefined revisions and catches notification exceptions without converting successful writes into failures. Tests at `manuscript-preservation.spec.ts:1202–1284` verify held saves after unmount in origin/other-project screens, live success/failure and restore success/late-edit/failure, including exact request bodies, revisions, retained content and query reads. The latest fault-injection test (`:1305–1352`) throws from the actual origin memory invalidation subscriber during a UI save, verifies saved state and exact revision/body, removes the subscriber, then verifies a second normal save and stale-memory recovery. It does not manually invalidate the cache to manufacture success.

- **Correct — M03 independent query recovery.** `MemoryPage.tsx:110–124,241–252,398–404` exposes independent project/chapter/memory error alerts and retry buttons without replacing the form. Memory loading, query error and successful empty results are distinct. The six initial/refetch failure cases (`memory-governance.spec.ts:332–371`) exercise each resource separately, existing automatic retry, keyboard Enter retry, retained cached data and retained input. The held-query/empty-list case (`:374–391`) covers the remaining state distinction.

- **Correct — M04 focus restoration.** `MemoryPage.tsx:151–156,176–187,406–411,473–479` waits for mutation invalidation/refetch, resolves the surviving action within the current list, and falls back to its focusable named region. Unmounted instances are guarded before scheduling focus. Eight keyboard approval/retirement × cancel/complete × filtered/all cases (`memory-governance.spec.ts:397–417`) verify trigger or fallback focus. The held-refetch regression (`:419–437`) covers the trigger disappearing after the response; the M01 matrix also asserts another screen's input keeps focus.

- **Correct — M05 wording and exact record preservation.** The only `backend/app/routers/projects.py` production change is the DELETE 409 detail at line 299. The surrounding writer reservation, all-visibility memory-reference lookup, rollback and deletion semantics remain unchanged. `backend/tests/test_memories_api.py:136–163` parametrizes draft/approved/retired, checks the exact provenance-preservation wording, and compares the complete chapter and memory JSON records before and after rejected deletion.

- **Correct — delivered behavioral evidence.** Directly read the fresh `memory-recovery-full.log` (31 passed), `manuscript-recovery-full.log` (26 passed), and `ai-context-recovery-full.log` (15 passed): **72 passing fixture tests**, each positive suite reporting no escapes. The command index records exit 0 for these runs. Axe serious/critical-zero assertions are present in the initial memory flow (`memory-governance.spec.ts:124–130`) and all eight keyboard matrix cases (`:412–413`), whose executions passed. There is no claim of a standalone retained axe JSON report. `backend-recovery-full.log:146–147` records 421 passed, 1 skipped, 70 subtests, 19 warnings, violations=[] and subprocess_attempts=0. Production build output records success; app/helper TypeScript logs are empty and their command records report exit 0.

- **Fixed:** None; this was entirely read-only.
- **Merge verdict:** **OK for the assigned behavioral review.** Final acceptance remains with the parent and the separate coverage/isolation review.

## Evidence boundaries and disposition

Evidence root: `/home/hunter8891/.pi/agent/sessions/--mnt-c-Users-wj941-Documents-jippeel--/recovery/memory-m01-m05-restart-szd8peci/verification-0fe42cf5`.

Reviewed the required plans and fixture audit, original-baseline manifest, final production diff, relevant manifest/protection records, current source, actual regression assertions and fresh logs. No execution, edits, Git changes, provider/DB/credential access or agent launches occurred.

**Valid blockers:** None identified in this angle.

**Nonblocking limitations:** This review inspected evidence rather than rerunning tests or recomputing hashes. The parent independently records 356 artifact, 29 source and 5 protected hash matches. Active LSP diagnostics=0 means clean1/inconclusive4, not all-files clean. Held-save-after-unmount has direct regression coverage; restore-after-unmount additionally relies on inspection of the persistent coordinator and hook-level completion path, rather than a dedicated held-restore/navigation test. Axe proves the tested states and serious/critical threshold, not exhaustive accessibility compliance.

**Stale concerns:** The earlier proxy-escape run is explicitly rejected, not counted in the 72. Earlier writer timeout and the later optional-field serialization failure are execution/orchestration history, not current product failures. No claim is made that historical precrash raw evidence survived.

**Out of scope:** Deep coverage-merging/fixture-isolation audit, completed C13/B01/B02/B04/P1, whole-frontend V01, aesthetics redesign and real-resource gates are not reopened. The approved Python literal299→executed Raise297 mapping is understood as statement mapping with branch N/A, not proof that raw line299 was instrumented.
