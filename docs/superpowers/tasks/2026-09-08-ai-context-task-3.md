# AI-context Task 3 — frontend request ownership and small shared controls

Status: authorized. T1+T2 backend independent Spec/Quality PASS, parent backend269 PASS. Review base `46b1ec2704e1d0bb4a3c2abef8f862bb56631937` on `feat/ai-context-consistency`.

## Requirements and scope
Read canonical SPEC `../specs/2026-09-08-ai-context-consistency.md` and **Task 3** in PLAN `../plans/2026-09-08-ai-context-consistency.md`, including parent A3 full-form snapshot/cancellation addendum. This is behavior wiring using existing UI controls, **not a frontend redesign**. Existing native Windows toolchain only; no dependencies.

Owned production files:
- `frontend/src/stores/aiPanelStore.ts`
- `frontend/src/components/panels/AiPanel.tsx`
- `frontend/src/components/editor/CanonDialog.tsx`
- `frontend/src/components/editor/QualityDialog.tsx`
- `frontend/src/pages/EditorPage.tsx`
- `frontend/src/lib/aiStream.ts`
- `frontend/src/lib/api.ts`

Bounded parent ruling: if needed to avoid duplicated context/request lifecycle code in large components, you may create `frontend/src/lib/aiContextRequest.ts` and/or `frontend/src/components/editor/AiContextControls.tsx` using existing components/styles only. Do not split unrelated modules or redesign layout. Existing manuscript coordinator/internal save/recovery behavior is out of scope; call its public functions.

TDD fixture ownership (Task 4 remains real HTTP integration):
- Create `frontend/e2e/ai-context-ui.spec.ts`, `frontend/playwright.ai-context.fixture.config.ts`, and `frontend/vite.ai-context.fixture.config.ts`.
- Fixture UI tests use dedicated port **15227**, strict port, reuseExistingServer=false, Windows Playwright. Vite fixture config must disable/remove backend proxy so no accidental request reaches default port8000. All browser `/api/v1/**` requests must be intercepted or explicitly fail; never `continue` unknown API requests. Do not use unmocked APIRequestContext to seed anything. No real backend/LLM/production DB for these fixture tests.
- Do not edit prior preservation tests/config; rerun relevant existing browser fixture suite as regression using its documented isolated surface.
- Own report `docs/audits/ai-context-task-3-implementation.md` and new `.eval_tmp/ai-context-task-3/` evidence. No other docs/HANDOFF/branch/index/commits/children.

## Required connected lifecycle
1. Shared in-memory directives keyed by `(projectId, chapterId)`: serial default, approvedForeshadowIds empty, relationships false. No browser reload persistence or DB persistence. Old project/chapter selections must not leak into another project. Keep explicit source identity separate from current-body checkbox; opt-out still sends project_id/chapter_id and include_chapter_content=false.
2. Before first await reserve start token (duplicate pending start rejected), capture full form/IDs/arrays/brief/purpose/payoffs/relationship/generation+review settings. Flush existing manuscript coordinator; on recovery/conflict/network failure do not call generate/canon. Recheck active identity+token after flush, use captured form plus saved identity/revision only. Controls changed mid-flush affect next request, not this one.
3. Close/cancel/navigation/unmount invalidate pending starts, including leave-editor and navigate-away-then-back. Preserve existing stream abort ownership. Late failure or completion cannot clear a newer token. Check before provider start, not only on arrival. Both gen and canon follow the same ownership rule.
4. Results retain request origin and revision; no auto manuscript mutation. Insert/replace requires current editor identity match and existing recovery/edit lock allows it. Copy remains available if insertion blocked. Canon result/history cannot silently appear bound to a newer chapter; show captured origin/revision or ignore stale display appropriately.
5. Small existing controls for serial/volume_end/series_finale, approved same-project foreshadow rows, relationship opt-in. Share choices across AiPanel/CanonDialog/QualityDialog; do not expose public relationship_scope. Quality sends purpose and shows hook applicability, refreshes cache under purpose-specific query key; editor completion warning must honor closure purposes.
6. Add ending_intent to existing brief form/state/default/reset and purpose-aware parser. A complete finale brief with ending_intent/no next_hook must be sent, not silently dropped; serial keeps required hook and prior validation behavior.
7. Parse additive SSE context_metadata without breaking older fixtures/events/markers. Use server contract types from actual schemas; no backend edits. Preserve current selection/include semantics outside approved identity repair.

## Verification
Write failing browser boundary tests BEFORE feature edits. Exercise actual UI and captured requests, not only store metadata. Cover editor-opened current identity, body optout, saved revision after pending save, generation/canon rejection on failed flush/recovery, doubleclick, close/cancel/nav while flush pending, changed controls during pending flush, cross-chapter result insertion blocked+copy retained, shared purpose/payoff/relationship controls, finale brief serialization, quality purpose query/cache. Include auto-endpoint settle behavior without duplicate starts.

Use native commands from `C:\Users\wj941\Documents\jippeel\frontend`: `npm run build`; `npx playwright test --config playwright.ai-context.fixture.config.ts`; existing preservation fixture config if needed (port15225, no real backend). Use new fixture Vite config with no backend proxy. No real provider, default8000/5173, production DB/WAL/SHM/services, installs, Linux Node, migration, merge/push/deploy. Use nonblocking command handles; end turn for slow runs, no sleep/poll loops.

Report RED/GREEN/build/regression commands, actual counts, owned file changes, screenshots when useful, and explicit fixture-only limits. Separate reviewer reruns real UI/test surface; Task4 owns actual temporary API/SQLite/provider/browser integration after Task3 passes.
