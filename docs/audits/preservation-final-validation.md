# Preservation final validation — independent SPEC review

Date: 2026-09-08
Reviewer scope: final whole-branch SPEC review of `git diff b6a9ee6...fbdb796` at `fbdb796`.

## Current verified result — source 42fad7c

- Final Spec review: PASS, zero open required findings. See [re-review3](preservation-final-spec-rereview-3.md).
- Standards review: PASS; backend contract fix independently re-reviewed at409c268. See [backend re-review](preservation-final-standards-rereview-1.md).
- Latest independent results: backend222 passed; frontend fixture17 passed; real-backend browser scenario1 passed; native production build passed.
- Real integration covers save/restore timing and the end-to-end workflow. Failed-refresh/overlapping recovery choices remain fixture-browser coverage, not separate real-backend failure scenarios.
- No production deployment, production migration, credential restore or real LLM-quality validation. Backup evidence covers exact full rows of11 selected tables in synthetic temporary DBs.
- The sections below preserve earlier runs and subsequent re-review evidence; earlier counts and blocked verdicts are historical, not the current result.

## Parent final native repeat — source 42fad7c

> Historical commands/results below describe 2026-09-08, not the current runner contract. Since 2026-09-12 use [the supported isolated runner](../runbooks/isolated-backend-tests.md); direct pytest/DB-only environment instructions below are superseded. This does not retroactively establish credential isolation for the historical run.

After final Spec approval, the parent reran the native commands without feature-source edits:
- Backend: `cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\backend && .venv\Scripts\python.exe ..\.eval_tmp\run_backend_pytest.py -q"` — exit0, 222 passed. The inspected runner creates a new Windows temp DB and sets DATABASE_URL and JIPPEEL_ALLOW_TEMP_CREATE_ALL before importing pytest. Full output: `preservation-final-root-backend.txt`. This helper is local evidence; the earlier cmd.exe environment commands remain the portable project run instructions.
- Frontend: `cmd.exe /C "cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build && npx playwright test --config playwright.preservation.config.ts --reporter=list && npx playwright test --config playwright.preservation.integration.config.ts --reporter=list"` — exit0, build passed, fixture17 passed, real integration1 passed. Full output: `preservation-final-root-frontend.txt`.
- These results confirm the independent reports on the final source. Coverage limitations above still apply.

## Isolation

- Used Windows `cmd.exe` for frontend Node/npm/Playwright.
- Did not run Linux Node.
- Did not use default ports `5173` or `8000`.
- Playwright fixture server used `127.0.0.1:15201`.
- Playwright integration used frontend `127.0.0.1:15202` and backend `127.0.0.1:18080`.
- Integration config starts `scripts/preservation_backend_fixture.py`, which runs Alembic against a fresh temp DB and unsets `JIPPEEL_ALLOW_TEMP_CREATE_ALL` before strict startup.
- External processing was deterministic stubs. Successful API responses in integration were real backend responses; route interception only held/forwarded transport.
- Cleanup socket check: `{15201: 111, 15202: 111, 18080: 111, 5173: 111, 8000: 111}` (`111` means connection refused).

## Results

### Build

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
```

Result: exit `0`.

```text
> jippeel-frontend@0.1.0 build
> tsc -b && vite build

▲ [WARNING] Duplicate key "build" in object literal [duplicate-object-key]

    vite.config.ts:38:2:
      38 │   build: {
         ╵   ~~~~~

  The original key "build" is here:

    vite.config.ts:11:2:
      11 │   build: {
         ╵   ~~~~~

vite v5.4.21 building for production...
transforming...
✓ 229 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                         0.66 kB │ gzip:   0.39 kB
dist/assets/index-Ct_pw3J8.css         24.26 kB │ gzip:   5.66 kB
dist/assets/markdown-Bx13qlMl.js      130.22 kB │ gzip:  60.70 kB
dist/assets/react-vendor-D_J2dLiK.js  161.78 kB │ gzip:  52.80 kB
dist/assets/index-LS8qaeM4.js         203.93 kB │ gzip:  59.92 kB
dist/assets/editor-dbPoz2N-.js        475.11 kB │ gzip: 165.91 kB
✓ built in 3.99s
```

### Scoped frontend fixture suite

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts
```

Result: exit `0`.

```text
[WebServer] ▲ [WARNING] Duplicate key "build" in object literal [duplicate-object-key]
[WebServer]
[WebServer]     vite.config.ts:38:2:
[WebServer]       38 │   build: {
[WebServer]          ╵   ~~~~~
[WebServer]
[WebServer]   The original key "build" is here:
[WebServer]
[WebServer]     vite.config.ts:11:2:
[WebServer]       11 │   [WebServer] build: {
[WebServer]          ╵   ~~~~~
[WebServer]

Running 13 tests using 1 worker

  ✓   1 [chromium] › e2e\manuscript-preservation.spec.ts:255:3 › manuscript preservation frontend fixture › serializes delayed per-chapter saves and preserves newer typing (4.1s)
  ✓   2 [chromium] › e2e\manuscript-preservation.spec.ts:280:3 › manuscript preservation frontend fixture › project switch rejects stale selected chapters and never writes under the new project context (1.3s)
  ✓   3 [chromium] › e2e\manuscript-preservation.spec.ts:291:3 › manuscript preservation frontend fixture › keeps ApiError detail for 409 and shows local/server conflict recovery (1.6s)
  ✓   4 [chromium] › e2e\manuscript-preservation.spec.ts:311:3 › manuscript preservation frontend fixture › recovers reload drafts, survives storage failure, and preserves text after network error (1.7s)
  ✓   5 [chromium] › e2e\manuscript-preservation.spec.ts:331:3 › manuscript preservation frontend fixture › preserves local text on network failure and reconciles lost save acknowledgements (1.1s)
  ✓   6 [chromium] › e2e\manuscript-preservation.spec.ts:351:3 › manuscript preservation frontend fixture › does not let a pending refine accept response overwrite a late local edit (1.2s)
  ✓   7 [chromium] › e2e\manuscript-preservation.spec.ts:376:3 › manuscript preservation frontend fixture › does not let a pending scene merge response overwrite a late edit or transfer to another chapter (1.4s)
  ✓   8 [chromium] › e2e\manuscript-preservation.spec.ts:406:3 › manuscript preservation frontend fixture › does not let a pending snapshot restore response overwrite a late local edit (1.2s)
  ✓   9 [chromium] › e2e\manuscript-preservation.spec.ts:429:3 › manuscript preservation frontend fixture › does not acknowledge lost save responses when GET returns different text (896ms)
  ✓  10 [chromium] › e2e\manuscript-preservation.spec.ts:443:3 › manuscript preservation frontend fixture › pagehide uses revision contract and beforeunload leaves recoverable text (861ms)
  ✓  11 [chromium] › e2e\manuscript-preservation.spec.ts:461:3 › manuscript preservation frontend fixture › flushes before refine start, sends expected_revision, and blocks stale accept safely (1.1s)
  ✓  12 [chromium] › e2e\manuscript-preservation.spec.ts:485:3 › manuscript preservation frontend fixture › scene trigger is accessible and merge flushes with expected_revision (1.1s)
  ✓  13 [chromium] › e2e\manuscript-preservation.spec.ts:500:3 › manuscript preservation frontend fixture › shows snapshot text before explicit restore and restore uses current revision (1.1s)

  13 passed (21.2s)
```

### Real backend browser integration suite

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.integration.config.ts
```

Result: exit `0`.

```text
Running 1 test using 1 worker

  ✓  1 [chromium] › e2e\manuscript-preservation.integration.spec.ts:111:3 › manuscript preservation real backend integration › uses real temp backend for browser saves, stale refine accept, scene merge, and restore race (9.3s)

  1 passed (14.9s)
```

## Review result

See `docs/audits/preservation-final-spec-review.md`.

Status: **CHANGES REQUESTED**.


---

## Re-review 1 evidence — final SPEC reviewer

Status: **CHANGES REQUESTED**. See `docs/audits/preservation-final-spec-rereview-1.md`.

Scope: fix diff `fbdb796..9f10107` for original final SPEC findings.

Isolation:
- Used native Windows `cmd.exe` for Node/npm/Playwright.
- Fixture frontend port: `127.0.0.1:15210`.
- Real integration ports: frontend `127.0.0.1:15202`, backend `127.0.0.1:18080`.
- Did not use default `5173`/`8000`, production DB/WAL/SHM, real LLM, dependencies, source edits, commits, children, or git index.
- Post-run socket cleanup check: `{15210: 111, 15202: 111, 18080: 111, 5173: 111, 8000: 111}` (`111` means refused/not listening).

Commands and results:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
```

Result: exit `0`. Passed with the known duplicate Vite `build` key warning.

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts
```

Result: exit `0`. Fixture coverage: `14 passed` on port `15210`; API success responses are fixture/mocked.

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.integration.config.ts
```

Result: exit `0`. Real integration coverage: `1 passed` on frontend `15202` + temp backend `18080`; backend API responses were real except held/forwarded transport; external processing used deterministic stubs.


---

## Re-review 2 evidence — final SPEC reviewer

Status: **CHANGES REQUESTED**. See `docs/audits/preservation-final-spec-rereview-2.md`.

Scope: actual fix diff `9f10107..e9bcf86` for unresolved recovery mismatch lifecycle.

Isolation:
- Used native Windows `cmd.exe` for Node/npm/Playwright.
- Fixture frontend port: `127.0.0.1:15214`.
- Real integration ports: frontend `127.0.0.1:15202`, backend `127.0.0.1:18080`.
- Did not use default `5173`/`8000`, production DB/WAL/SHM, real LLM, dependencies, source edits, commits, children, or git index.
- Post-run socket cleanup check: `{15214: 111, 15202: 111, 18080: 111, 5173: 111, 8000: 111}` (`111` means refused/not listening).

Commands and results:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
```

Result: exit `0`. Passed with the known duplicate Vite `build` key warning.

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts
```

Result: exit `0`. Fixture coverage: `15 passed` on port `15214`; API success responses are fixture/mocked.

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.integration.config.ts
```

Result: exit `0`. Real integration coverage: `1 passed` on frontend `15202` + temp backend `18080`; backend API responses were real except held/forwarded transport; external processing used deterministic stubs.


---

## Re-review 3 evidence — final SPEC reviewer

Status: **PASS**. See `docs/audits/preservation-final-spec-rereview-3.md`.

Scope: actual fix diff `e9bcf86..42fad7c` for failed recovery refresh handling.

Isolation:
- Used native Windows `cmd.exe` for Node/npm/Playwright.
- Fixture frontend port: `127.0.0.1:15225`.
- Real integration ports: frontend `127.0.0.1:15202`, backend `127.0.0.1:18080`.
- Did not use default `5173`/`8000`, production DB/WAL/SHM, real LLM, dependencies, source edits, commits, children, or git index.
- Post-run socket cleanup check: `{15225: 111, 15202: 111, 18080: 111, 5173: 111, 8000: 111}` (`111` means refused/not listening).

Commands and results:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npm run build
```

Result: exit `0`. Passed with the known duplicate Vite `build` key warning.

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.config.ts
```

Result: exit `0`. Fixture coverage: `17 passed` on port `15225`; API success responses are fixture/mocked. It covers failed server choice, retry, pending action lockout, local choice durability, storage retention, and no stale PUT.

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend && npx playwright test --config playwright.preservation.integration.config.ts
```

Result: exit `0`. Real integration coverage: `1 passed` on frontend `15202` + temp backend `18080`; backend API responses were real except held/forwarded transport; external processing used deterministic stubs.
