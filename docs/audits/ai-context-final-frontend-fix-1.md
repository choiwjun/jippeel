# AI-context final frontend fix 1 — relationship policy controls

- Date: 2026-09-08
- Branch: `feat/ai-context-consistency`
- Base HEAD before fix: `d2a5b3479969c0b13de3be00e1b1a3fbd6746063`
- Finding: final standards S2 — shared `AiContextControls` applied generation-only selected-character gating to canon.
- Scope: frontend internal control policy and fixture regression only.
- Evidence dir: `.eval_tmp/ai-context-final-frontend-fix-1/`

## Files changed

- `frontend/src/components/editor/AiContextControls.tsx`
- `frontend/src/components/panels/AiPanel.tsx`
- `frontend/src/components/editor/CanonDialog.tsx`
- `frontend/src/components/editor/QualityDialog.tsx`
- `frontend/e2e/ai-context-ui.spec.ts`

No backend, API schema, public `relationship_scope`, dependency, T4 QA, HANDOFF, index, or commit changes.

## Fix summary

- Added typed internal `AiContextRelationshipPolicy`:
  - `generation`: show `선택 인물 관계 포함`; disabled until at least two selected characters.
  - `canon`: show `작품 인물 관계 포함`; enabled for the current project/chapter and independent of generation selected characters.
  - `hidden`: no relationship checkbox.
- `AiPanel` passes generation policy and only sends `include_relationships: true` when the directive is true and at least two characters are selected.
- `CanonDialog` passes canon policy and still sends only canon fields. It does not send `character_ids`.
- `QualityDialog` passes hidden policy, so quality remains purpose-only.

## TDD RED

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.ai-context.fixture.config.ts --grep canon --timeout=30000
```

Evidence: `.eval_tmp/ai-context-final-frontend-fix-1/red-canon-relationship-policy.txt`

Result: RED. The new canon zero-selected regression failed because `작품 인물 관계 포함` did not exist; the old shared control only exposed the generation label and disabled it by selected-character count.

## GREEN verification

### Native frontend build

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npm run build
```

Evidence: `.eval_tmp/ai-context-final-frontend-fix-1/build-green.txt`

Result: PASS, exit 0. The pre-existing duplicate `build` key warning in `vite.config.ts` remains.

### Full Task3 fixture

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.ai-context.fixture.config.ts
```

Evidence: `.eval_tmp/ai-context-final-frontend-fix-1/ai-context-fixture-green.txt`

Result: `11 passed (13.4s)`.

Covered new cases:
- canon relationship opt-in works with zero selected generation characters
- canon relationship opt-in works with one selected generation character
- canon requests send `include_relationships: true` and no `character_ids`
- generation relationship control stays disabled with zero/one selected characters
- existing two-selected generation relationship request remains covered
- quality dialog shows purpose controls but no relationship option

### Preservation fixture regression

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.preservation.config.ts
```

Evidence: `.eval_tmp/ai-context-final-frontend-fix-1/preservation-fixture-green.txt`

Result: `17 passed (22.2s)`.

### Whitespace check

Command:

```bash
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check -- frontend/src/components/editor/AiContextControls.tsx frontend/src/components/panels/AiPanel.tsx frontend/src/components/editor/CanonDialog.tsx frontend/src/components/editor/QualityDialog.tsx frontend/e2e/ai-context-ui.spec.ts
```

Evidence: `.eval_tmp/ai-context-final-frontend-fix-1/diff-check.txt`

Result: PASS, exit 0.

## Fixture limits

- Tests used browser fixtures only.
- Fixture port `15227` and preservation port `15225` were checked before use and were free.
- No real backend, real provider, production DB, secrets, or default frontend port `5173` were used.
- Port `8000` was already listening before this fix, so it was not used or touched.
- Final real integration remains owned by the final reviewer / T4 path.

## Source hashes after fix

```json
{
  "frontend/src/components/editor/AiContextControls.tsx": "7a397447cc2bd994b35cfcffcc8693348dbe0d8201e6a7037bf9e3c9975f12a5",
  "frontend/src/components/panels/AiPanel.tsx": "7ff5f0cc5eadc6ca53685dea91d1db41c56e72306c00fa66d6722244aab0f2d0",
  "frontend/src/components/editor/CanonDialog.tsx": "56eeafd1f67b3b991b4b25f3676c8cc1968b66b6b8ef15f2bfd480a3dfbb4a52",
  "frontend/src/components/editor/QualityDialog.tsx": "29f74546e5b7f948ccee93911aa38107ee6d45f8f7b73267ca23214142a55906",
  "frontend/e2e/ai-context-ui.spec.ts": "fe5b6d8c4e428f761f8cbe83840083c43c8fba87f70f4d0deb0f5f46ea7ebb79"
}
```

## Line ending counts after fix

```json
{
  "frontend/src/components/editor/AiContextControls.tsx": {
    "crlf": 0,
    "lf": 110
  },
  "frontend/src/components/panels/AiPanel.tsx": {
    "crlf": 1110,
    "lf": 1110
  },
  "frontend/src/components/editor/CanonDialog.tsx": {
    "crlf": 0,
    "lf": 296
  },
  "frontend/src/components/editor/QualityDialog.tsx": {
    "crlf": 0,
    "lf": 237
  },
  "frontend/e2e/ai-context-ui.spec.ts": {
    "crlf": 0,
    "lf": 591
  }
}
```
