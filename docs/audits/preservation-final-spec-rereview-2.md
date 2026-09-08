# Preservation final SPEC re-review 2

Status: **CHANGES REQUESTED**

Scope: inspected actual fix diff `9f10107..e9bcf86` for the remaining recovery High from `docs/audits/preservation-final-spec-rereview-1.md`. Full fix diff saved to `.eval_tmp/preservation-final-spec-rereview-2/fix-diff.txt`.

## Remaining finding status

1. **High recovery mismatch lifecycle — PARTIAL / still blocking.** The editor lock is real: unresolved mismatch renders a lock panel instead of CodeMirror (`frontend/src/pages/EditorPage.tsx:566-580`), `edit()` rejects changes while unresolved (`frontend/src/lib/manuscriptDrafts.ts:221-227`), `pagehideFlush()` no-ops (`frontend/src/lib/manuscriptDrafts.ts:404-412`), and server detail refresh updates the displayed body/revision pair (`frontend/src/lib/manuscriptDrafts.ts:203-210`, `276-294`). Local choice also uses the latest observed `serverRevision` and keeps the draft while save is pending (`frontend/src/lib/manuscriptDrafts.ts:265-274`, `534-546`).

   **Still wrong:** the requested invariant says failed refresh must keep recovery usable. But `clearRecovery()` always proceeds after `await this.refreshRecoveryServerText()` (`frontend/src/lib/manuscriptDrafts.ts:243-259`). `refreshRecoveryServerText()` catches GET failure, sets `errorMessage`, leaves `recovery` unresolved, and returns no failure signal (`frontend/src/lib/manuscriptDrafts.ts:276-293`). The caller then reads the old `this.recovery`, sets editor text to that stale server pair, clears `recovery`, and removes the stored local draft. A failed “서버 원고로 계속” refresh can therefore discard the local recovery and unlock to stale server text.

2. **Medium refine `base_revision` response — remains RESOLVED.** This backend path was unchanged in `9f10107..e9bcf86`; previous re-review evidence still applies.

## Verdict

**CHANGES REQUESTED** — 1 blocking finding remains: 1 High. The lock/server-refresh/local-choice path is improved, but failed refresh on explicit server choice still violates the recovery preservation invariant.

## Verification appendix

Fresh native Windows commands:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.integration.config.ts
```

Results:
- Build: exit `0`; passed with pre-existing duplicate Vite `build` key warning.
- Fixture suite: exit `0`; **15 passed** on port `15214`. This is fixture/mocked API coverage. It covers lock, reload, local pending durability, server refresh success, and no stale server-body PUT; it does not cover refresh failure.
- Real integration suite: exit `0`; **1 passed** on frontend `15202` + temp backend `18080`. Backend responses were real except held/forwarded transport; external processing used deterministic stubs.
- Cleanup socket check: `{15214: 111, 15202: 111, 18080: 111, 5173: 111, 8000: 111}` (`111` = connection refused).

## Limitations

No production DB/WAL/SHM, default `5173`/`8000`, real LLM, dependency install, source edit, commit, child, or git index mutation was used. Backend base_revision was not re-reviewed beyond confirming it was unchanged and covered by integration.
