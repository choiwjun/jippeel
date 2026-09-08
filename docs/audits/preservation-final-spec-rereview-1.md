# Preservation final SPEC re-review 1

Status: **CHANGES REQUESTED**

Scope: re-reviewed original findings in `docs/audits/preservation-final-spec-review.md` against fix diff `fbdb796..9f10107` (`409c268`, `9f10107`). Full fix diff saved to `.eval_tmp/preservation-final-spec-rereview-1/fix-diff.txt`.

## Original finding statuses

1. **High recovery draft deletion — PARTIAL / still blocking.** The direct Ctrl+S/pre-action path is fixed: `flush()` now throws before `removeStoredDraft()` when `recovery.kind === 'mismatch'` (`frontend/src/lib/manuscriptDrafts.ts:332-342`), and `pagehideFlush()` no-ops (`frontend/src/lib/manuscriptDrafts.ts:370-378`). However the unresolved state still mishandles later edits/cache. Spec requires “모든 사용자 입력에서…최신 draft 기록” and says mismatched reconnect must preserve local/server text and forbid automatic overwrite (`docs/superpowers/specs/2026-09-07-manuscript-preservation.md:43-44`). In `edit()`, typing while mismatch changes `this.text` but returns before `persistDraft()` (`frontend/src/lib/manuscriptDrafts.ts:214-230`), so that new input is not recoverable on reload. Also, a cache refetch during mismatch updates `serverText/serverRevision` without updating the recovery choice text (`frontend/src/lib/manuscriptDrafts.ts:203-211`). Then “서버 원고로 계속” only clears when `text === serverText` (`frontend/src/lib/manuscriptDrafts.ts:244-252`); if the server changed, the next flush can save the stale server-view text over the newer server revision (`frontend/src/lib/manuscriptDrafts.ts:353-360`). This is still a preservation risk.

2. **Medium refine `base_revision` response — RESOLVED.** `RefineResult.base_revision` is required (`backend/app/schemas.py:466-475`, `frontend/src/lib/api.ts:324-333`), and `POST /refine` records and returns the captured `input_content_md`/`base_revision` (`backend/app/routers/refine.py:65-95`). Regression coverage advances the chapter during pipeline and verifies response/report stay on the captured base (`backend/tests/test_manuscript_preservation.py:463-513`).

## New breakage check

No additional backend schema/revision issue found in the inspected fix diff. The remaining blocker is the frontend unresolved-recovery edit/cache behavior above.

## Verdict

**CHANGES REQUESTED** — 1 blocking finding remains: 1 High. Original Medium is fixed.

## Verification appendix

Fresh native Windows commands:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.integration.config.ts
```

Results:
- Build: exit `0`; passed with pre-existing duplicate Vite `build` key warning.
- Fixture suite: exit `0`; **14 passed** on port `15210`. This is fixture/mocked API coverage.
- Real integration suite: exit `0`; **1 passed** on frontend `15202` + temp backend `18080`. Integration uses real backend responses with held/forwarded transport and deterministic external stubs.
- Cleanup socket check: `{15210: 111, 15202: 111, 18080: 111, 5173: 111, 8000: 111}` (`111` = connection refused).
