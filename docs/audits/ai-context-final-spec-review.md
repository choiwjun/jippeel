# AI-context final SPEC review

Status: **PASS after rereview 2** for fixed range `70ec67eb3be02a89baefe01b3e798d033431983b..d2a5b3479969c0b13de3be00e1b1a3fbd6746063` plus frozen frontend fix snapshots.

Authority reviewed:

- `docs/superpowers/tasks/2026-09-08-ai-context-final-review.md`
- `docs/superpowers/specs/2026-09-08-ai-context-consistency.md`
- `docs/superpowers/plans/2026-09-08-ai-context-consistency.md`
- `docs/audits/ai-context-contract-rulings.md`
- `docs/audits/ai-context-task-4-rulings.md`
- `docs/audits/ai-context-final-rereview-1-snapshot.json`
- `docs/audits/ai-context-final-rereview-2-snapshot.json`

## Current verdict

**SPEC PASS.** No remaining blocking SPEC findings found in the reviewed source and fresh gates.

The prior final-review blockers S2 and S3 are resolved in the frozen combined frontend fix.

## Resolved findings

### S2 — RESOLVED — Canon relationship opt-in no longer uses generation selected-character gating

Original issue:

- `CanonDialog` passed generation selected-character count into shared controls.
- `AiContextControls` disabled relationship opt-in when selected characters were fewer than 2.
- This violated canon policy: canon relationship opt-in is project-level and includes all same-project relationships.

Current source evidence:

- `frontend/src/components/editor/AiContextControls.tsx:9-12` defines target-specific `AiContextRelationshipPolicy`.
- `frontend/src/components/editor/AiContextControls.tsx:36-47` disables generation relationship controls for fewer than 2 selected characters, but disables canon only when project/chapter is absent.
- `frontend/src/components/editor/AiContextControls.tsx:42-44` labels canon as `작품 인물 관계 포함` and generation as `선택 인물 관계 포함`.
- `frontend/src/components/editor/CanonDialog.tsx:233-237` passes `relationshipPolicy={{ kind: 'canon' }}`.
- `frontend/src/components/editor/QualityDialog.tsx:155-159` hides relationship controls for quality.
- `frontend/src/components/panels/AiPanel.tsx:765-769` keeps generation policy separate.

Runtime evidence:

- Corrected SPA fixture: `frontend/e2e/ai-context-ui.spec.ts:612-655` covers canon relationship opt-in with zero and one selected generation character. The request sends `include_relationships: true` and no `character_ids`.
- Corrected SPA fixture: `frontend/e2e/ai-context-ui.spec.ts:658-672` proves generation relationship control remains disabled for zero/one selected characters and generation sends `include_relationships: false`.

### S3 — RESOLVED — Standalone Character/Lore AI no longer inherits stale editor chapter identity

Original issue:

- `AiPanel.generate()` used `editorStore.projectId/chapterId` whenever those IDs were non-null.
- Character/Lore standalone AI entry points could run after leaving the editor while the old editor IDs still lived in memory.
- A standalone request could flush an unrelated old editor draft or send stale `chapter_id`/revision/body/scene.

Current source evidence:

- `frontend/src/stores/aiPanelStore.ts:97-124` adds internal `requestSource` and `activeEditorIdentity` state.
- `frontend/src/stores/aiPanelStore.ts:248-294` sets explicit standalone/editor source and lifecycle-owned active editor identity.
- `frontend/src/components/panels/AiPanel.tsx:222-248` permits editor-bound generation only when request source, AI context identity, active editor identity, and `editorStore` identity all match.
- `frontend/src/components/panels/AiPanel.tsx:272-300` flushes only the verified editor-bound chapter and rechecks token/navigation/active identity after await.
- `frontend/src/components/panels/AiPanel.tsx:309-323` sends standalone requests with `chapter_id: null`, `expected_revision: null`, `include_chapter_content: false`, and `scene_id: null`.
- `frontend/src/components/panels/AiPanel.tsx:250` reads directives by `(boundProjectId, boundChapterId)`, so standalone uses the project/null directive key rather than old chapter directives.
- `frontend/src/pages/CharactersPage.tsx:293-306` sends explicit page project, `chapterId: null`, `requestSource: 'standalone'`, selected character IDs, no body inclusion, and no scene.
- `frontend/src/pages/LorebookPage.tsx:275-288` sends explicit page project, `chapterId: null`, `requestSource: 'standalone'`, selected lore ID, no body inclusion, and no scene.

Corrected SPA runtime evidence:

- `frontend/e2e/ai-context-ui.spec.ts:107-146` installs runtime/store handles and checks same `window.__aiContextRuntimeId`, retained old `editorStore` IDs, and old draft localStorage after navigation.
- `frontend/e2e/ai-context-ui.spec.ts:416-443` uses React Router sidebar links and router-native navigation, not `page.goto`, for standalone transitions.
- `frontend/e2e/ai-context-ui.spec.ts:690-731` covers Character standalone after unresolved old editor recovery. It proves same runtime, old `editorStore` still `1/10`, old recovery draft still exists, no writes/flushes, explicit project 1, `chapter_id: null`, `expected_revision: null`, `include_chapter_content: false`, serial default directives, no approved foreshadows, no scene, and no old draft text in the request context.
- `frontend/e2e/ai-context-ui.spec.ts:733-764` covers same-project Lore standalone after old chapter directives were set. It proves no stale flush, `chapter_id: null`, serial/default standalone directives, and selected lore only.
- `frontend/e2e/ai-context-ui.spec.ts:766-792` covers cross-project Lore standalone with stale project-1 editor IDs still retained. It sends explicit project 2 with `chapter_id: null` and the project-2 lore ID.
- `frontend/e2e/ai-context-ui.spec.ts:555-575` covers active preview tab as editor-bound and still body-opt-out capable.

## Fresh verification evidence

### Backend focused SPEC gate from initial final review

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py tests/test_ai_context_directives.py tests/test_ai_generate_stream.py tests/test_ai_context_bundle.py tests/test_quality.py tests/test_parallel_writer.py tests/test_parallel_quality.py tests/test_foreshadows_canon.py -q > ..\.eval_tmp\ai-context-final-spec\backend-focused-output.txt 2>&1"
```

Result: exit `0`, `91 passed, 1 warning in 4.89s`.

### Real browser/FastAPI/Alembic/temp SQLite/fake-provider integration

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && set NODE_PATH=C:\Users\wj941\Documents\jippeel\frontend\node_modules&& npx playwright test --config ..\.eval_tmp\ai-context-final-spec\playwright.final.config.ts > ..\.eval_tmp\ai-context-final-spec\rereview1-integration-output.txt 2>&1"
```

Result: exit `0`, `3 passed (24.8s)`.

Evidence:

- `.eval_tmp/ai-context-final-spec/rereview1-integration-output.txt`
- `.eval_tmp/ai-context-final-spec/rereview1-playwright-evidence.json`
- `.eval_tmp/ai-context-final-spec/rereview1-provider-prompts.jsonl`
- `.eval_tmp/ai-context-final-spec/rereview1-provider-summary.json`
- `.eval_tmp/ai-context-final-spec/rereview1-backend-fixture-result.json`
- `.eval_tmp/ai-context-final-spec/rereview1-ai-context-task4.db*`

Provider kind counts from preserved JSONL:

```json
{
  "draft": 2,
  "single_review": 1,
  "planner": 1,
  "worker": 2,
  "parallel_review": 1,
  "canon": 1
}
```

Provider payload facts checked from raw messages:

- Single draft/review contained finale purpose, style sentinel, relationship sentinel, approved payoff sentinel, and omitted the body sentinel for body opt-out.
- Parallel planner, both workers, and parallel review contained finale purpose, style sentinel, relationship sentinel, and approved payoff sentinel.
- Canon contained finale purpose, relationship sentinel, approved payoff sentinel, future-planted label, and future-resolution warning.
- Negative API matrix kept provider prompt count unchanged.

This gate was not rerun after rereview 2 because parent confirmed all 7 app-source hashes were unchanged. Only `frontend/e2e/ai-context-ui.spec.ts` and the fix-2 report changed.

### Preservation fixture

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && set NODE_PATH=C:\Users\wj941\Documents\jippeel\frontend\node_modules&& npx playwright test --config ..\.eval_tmp\ai-context-final-spec\playwright.preservation-final.config.ts > ..\.eval_tmp\ai-context-final-spec\rereview1-preservation-output.txt 2>&1"
```

Result: exit `0`, `17 passed (35.3s)`.

Evidence: `.eval_tmp/ai-context-final-spec/rereview1-preservation-output.txt`.

This gate was not rerun after rereview 2 because app-source hashes were unchanged.

### Corrected SPA Task3/S2 fixture

Command:

```cmd
cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && set NODE_PATH=C:\Users\wj941\Documents\jippeel\frontend\node_modules&& npx playwright test --config ..\.eval_tmp\ai-context-final-spec\playwright.t3-fixture.config.ts > ..\.eval_tmp\ai-context-final-spec\rereview2-t3-fixture-output.txt 2>&1"
```

Result: exit `0`, `15 passed (20.5s)`.

Evidence: `.eval_tmp/ai-context-final-spec/rereview2-t3-fixture-output.txt`.

Important distinction:

- The earlier old helper `15 passed` evidence used `page.goto` in standalone helpers and did **not** prove stale SPA editor-store retention.
- The earlier interrupted reviewer run `pid=36518` was killed and is **not** counted as a completed gate.
- The corrected SPA fixture above is the accepted runtime proof for S2/S3 after helper correction.

## Static whole-branch SPEC map

No remaining blocking issue found in these areas after reading the actual diff and surrounding source:

- One resolved project is enforced for generation, parallel generation, canon, selected characters, selected lore, scenes, approved foreshadows, relationships, and foreshadow referenced chapters.
- Generation, parallel generation, and canon validate context/revision before provider client/endpoint/provider work.
- Body opt-out keeps current identity/revision metadata and omits current body from the prompt.
- Legacy chapter-only generation still includes body by default.
- Single review and parallel planner/worker/review reuse the same context and purpose/style/payoff directives.
- Canon captures immutable input revision and SHA256 before endpoint resolution/provider work and stores/returns them.
- Future planted vs future resolved semantics match binding R6.
- Approved payoff permission is request-scoped and does not mutate foreshadow state.
- Local quality stores purpose in metrics and dedupes history by body hash plus purpose.
- UI generation and canon retain request ownership through token, navigation, close/cancel, newer requests, and late callback guards.
- AI result insertion remains manual, origin-gated, and blocked for wrong chapter/conflict/recovery paths; copy remains available.
- Active preview remains editor-bound; standalone Character/Lore intent is explicit project/no-chapter/no-flush.
- Manuscript preservation regression fixture passed.

## Hash evidence

Current frozen snapshot: `docs/audits/ai-context-final-rereview-2-snapshot.json`.

Before/after hash map: `.eval_tmp/ai-context-final-spec/rereview2-hash-before-after.json`.

Key current hashes:

```json
{
  "frontend/src/components/editor/AiContextControls.tsx": "7a397447cc2bd994b35cfcffcc8693348dbe0d8201e6a7037bf9e3c9975f12a5",
  "frontend/src/components/editor/CanonDialog.tsx": "56eeafd1f67b3b991b4b25f3676c8cc1968b66b6b8ef15f2bfd480a3dfbb4a52",
  "frontend/src/components/editor/QualityDialog.tsx": "29f74546e5b7f948ccee93911aa38107ee6d45f8f7b73267ca23214142a55906",
  "frontend/src/components/panels/AiPanel.tsx": "bc13577bb82916ec17c6a96adf36a1e0dd1eabacfc2b76cdbe8c64f3c167b1f4",
  "frontend/src/pages/CharactersPage.tsx": "98ae8b4763493906391ca176e5f3e3363bfbb147718e72deb98365c7ac1655b3",
  "frontend/src/pages/LorebookPage.tsx": "706ff2c49268724c3c8e3f8c45e6dc2e6de052264f241fe2bc7a5db0f0d41fa5",
  "frontend/src/stores/aiPanelStore.ts": "a0b466708987665edc3517cb026851d9f9b292af949f4209e68b32fbb7cc55a4",
  "frontend/e2e/ai-context-ui.spec.ts": "3a17c6b41a43d6f50b2af8da1b9a4d1a20477d57fa6bfecf05928426db85a210"
}
```

## Port and safety evidence

Pre-rereview2 fixture port check:

- `.eval_tmp/ai-context-final-spec/rereview2-pre-15227-check.txt`: `15227=False`.

Post-rereview2 port check:

- `.eval_tmp/ai-context-final-spec/rereview2-post-port-check.txt`: `15212=False`, `18112=False`, `18113=False`, `15227=False`, `15225=False`.

Safety limits:

- I edited only `docs/audits/ai-context-final-spec-review.md` and files under `.eval_tmp/ai-context-final-spec/`.
- No source, QA implementation, branch, index, commit, `HANDOFF.md`, or production DB files were edited by this review.
- No real LLMs, secrets, dependency installation, Linux Node, production DB/WAL/SHM, or default `8000`/`5173` services were used.
- Real integration uses a deterministic fake provider. It proves contract/payload behavior, not literary quality.
- Standards/build/full-backend review remains a separate reviewer surface.

## Final SPEC verdict

**PASS.** S2 and S3 are resolved. No remaining required SPEC fixes found.
