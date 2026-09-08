# AI-context final frontend fix 2 — standalone identity guard

- Date: 2026-09-08
- Branch: `feat/ai-context-consistency`
- Base HEAD: `d2a5b3479969c0b13de3be00e1b1a3fbd6746063`
- Finding: `docs/audits/ai-context-final-spec-review.md` S3.
- Evidence dir: `.eval_tmp/ai-context-final-frontend-fix-2/`
- Prior S2 snapshot preserved: `docs/audits/ai-context-final-frontend-fix-1-snapshot.json`

## Current status

S3 app source is frozen.
After parent found a test-validity gap, only `frontend/e2e/ai-context-ui.spec.ts` and this report/evidence were edited.
No app source file changed during the SPA-helper correction.

## Original S3 source fix summary

Changed app source files in the original S3 fix:

- `frontend/src/stores/aiPanelStore.ts`
- `frontend/src/components/panels/AiPanel.tsx`
- `frontend/src/pages/CharactersPage.tsx`
- `frontend/src/pages/LorebookPage.tsx`

No backend, editorStore, manuscriptCoordinator, dependencies, HANDOFF, index, commit, or T4 QA changes.

The source fix:

- Adds internal `requestSource: 'editor' | 'standalone'` to AI panel context.
- Adds `activeEditorIdentity` owned by `EditorPage` lifecycle through existing `setCurrentIdentity`.
- Uses editor-bound flow only when request source, AI context identity, active editor identity, and `editorStore` all match.
- Rejects editor-intent identity mismatch. It does not fall back to sending a non-null chapter without flush.
- Uses no-flush flow only for explicit standalone/project-only intent.
- Makes Character/Lore standalone buttons pass explicit page project, `chapterId: null`, selected IDs, and standalone intent.
- Forces standalone request fields to `chapter_id: null`, `expected_revision: null`, `include_chapter_content: false`, and `scene_id: null`.
- Reads standalone directives from project/null, so old chapter purpose and approved foreshadow/payoff choices are not reused.
- Keeps preview tab editor-bound because the active editor identity is page-lifecycle owned, not CodeMirror-view owned.

## Test-validity correction

Parent found that the first standalone helpers used `page.goto(...)`.
That reloaded the document and cleared runtime stores, so it did **not** prove a stale-identity SPA transition.
The earlier RED was useful only for explicit page-project coverage: Character standalone sent `project_id: null` before the source fix.
It was not a valid old-chapter-path repro.

The helpers now use same-document navigation:

- Same-project Character/Lore: click the real React Router sidebar links (`캐릭터`, `로어북`).
- Cross-project Lore: use router-native `history.pushState` + `PopStateEvent` to `/projects/2/lore` without page reload or store identity injection.
- Runtime proof: a `window.__aiContextRuntimeId` is installed before navigation and asserted unchanged after navigation.
- Stale editor proof: `window.__editorStore.getState()` is asserted to still hold old editor `projectId=1`, `chapterId=10` after leaving the editor page.
- Old draft proof: the unresolved recovery localStorage draft remains after leaving the editor and after standalone AI start.

## Final SPA-helper fixture evidence

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.ai-context.fixture.config.ts
```

Evidence: `.eval_tmp/ai-context-final-frontend-fix-2/ai-context-fixture-green-spa-helper-correction.txt`

Result: `15 passed (17.3s)`.

Final persisted regressions prove:

- Character standalone after unresolved old editor recovery uses same runtime, retains old editorStore IDs, keeps the old recovery draft, sends explicit project 1, and sends no stale chapter/revision/body/scene.
- Same-project Lore standalone after editor visit uses same runtime, retains old editorStore IDs, and does not reuse old editor purpose or approved foreshadow choices.
- Cross-project Lore standalone uses same runtime, retains stale project-1 editorStore IDs, but sends explicit project 2 with `chapter_id: null`.
- Active preview tab remains editor-bound and respects body opt-out.
- Existing Task3/S2 protections still pass in the same full fixture run.

## No-PUT note

The standalone regressions assert no **new AI-triggered flush PUT** for the old editor chapter during standalone Character/Lore starts.
They do not clear pending drafts and do not suppress the normal preservation lifecycle for already queued old drafts.

## Prior S3 validation evidence retained

These files remain as historical evidence from before the helper correction:

- `.eval_tmp/ai-context-final-frontend-fix-2/red-standalone-identity.txt` — RED for missing explicit page project, not valid as old-chapter SPA proof.
- `.eval_tmp/ai-context-final-frontend-fix-2/green-standalone-identity-focus.txt` — focused standalone run with old helper shape.
- `.eval_tmp/ai-context-final-frontend-fix-2/preservation-fixture-green.txt` — preservation fixture from original S3 source fix: `17 passed (21.9s)`.
- `.eval_tmp/ai-context-final-frontend-fix-2/build-green.txt` — native build from original S3 source fix, exit 0.

Per parent instruction during the helper correction, build, preservation, and real integration were not rerun because other reviewers owned those surfaces.

## Whitespace check

Command:

```bash
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check -- frontend/e2e/ai-context-ui.spec.ts docs/audits/ai-context-final-frontend-fix-2.md
```

Evidence: `.eval_tmp/ai-context-final-frontend-fix-2/diff-check-spa-helper-correction.txt`

Result: PASS, exit 0.

## Port note

- Fixture port `15227` was released by Spec reviewer before the final rerun.
- Before rerun, `15227` had no listener and only `TIME_WAIT` rows.
- After rerun, `15227` again had no listener and only `TIME_WAIT` rows.
- No `15225`, `15212`, `18112`, or `18113` work was run during the helper correction.

## Current frozen hashes

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

## Current line ending counts

```json
{
  "frontend/src/components/editor/AiContextControls.tsx": {
    "crlf": 0,
    "lf": 110
  },
  "frontend/src/components/editor/CanonDialog.tsx": {
    "crlf": 0,
    "lf": 296
  },
  "frontend/src/components/editor/QualityDialog.tsx": {
    "crlf": 0,
    "lf": 237
  },
  "frontend/src/components/panels/AiPanel.tsx": {
    "crlf": 1134,
    "lf": 1134
  },
  "frontend/src/pages/CharactersPage.tsx": {
    "crlf": 457,
    "lf": 457
  },
  "frontend/src/pages/LorebookPage.tsx": {
    "crlf": 296,
    "lf": 296
  },
  "frontend/src/stores/aiPanelStore.ts": {
    "crlf": 0,
    "lf": 405
  },
  "frontend/e2e/ai-context-ui.spec.ts": {
    "crlf": 0,
    "lf": 874
  }
}
```
