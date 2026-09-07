# Manuscript preservation final validation — Task 3

Date: 2026-09-07
Branch: `feat/manuscript-preservation`
Scope: isolated real-surface QA only. I did not edit production feature source, use real endpoints, touch `backend/jippeel.db`, merge, or push.

## Isolation

- Backend integration port: `127.0.0.1:18080`.
- Frontend integration port: `127.0.0.1:15202`.
- Existing scoped frontend fixture port: `127.0.0.1:15201`.
- Prohibited ports `:8000` and `:5173` were not used.
- Real API integration used `scripts/preservation_backend_fixture.py` with a fresh temp SQLite DB and Alembic `upgrade head` before startup.
- `JIPPEEL_ALLOW_TEMP_CREATE_ALL` was unset for strict backend startup in fixture runs.
- External processing used deterministic stubs from `scripts/preservation_im_not_ai_stub.py` and `scripts/preservation_refine_stub.py`.
- Browser API requests were not mocked as successful. Playwright route handling only held and forwarded real transport for save/restore races.

Latest integration backend fixture:

```json
{
  "work_dir": "C:\\Users\\wj941\\AppData\\Local\\Temp\\jippeel-preservation-qa-5pecpsju",
  "database_url": "sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-preservation-qa-5pecpsju/fixture.db",
  "jippeel_allow_temp_create_all": null,
  "hold_server": true,
  "health": "ok"
}
```

Port cleanup check after verification: connect results were `{18080: 111, 15201: 111, 15202: 111, 8000: 111, 5173: 111}`. `111` means connection refused from WSL to localhost.

## Commands and results

### Real browser + temp backend integration

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.preservation.integration.config.ts
```

Result: exit `0`.

```text
Running 1 test using 1 worker

  ✓  1 [chromium] › e2e\manuscript-preservation.integration.spec.ts:111:3 › manuscript preservation real backend integration › uses real temp backend for browser saves, stale refine accept, scene merge, and restore race (7.6s)

  1 passed (13.0s)
```

Covered in Chromium against real temporary backend:

- UI-created project and two chapters.
- Typed chapter 1 and switched chapters before debounce; real API stored chapter 1 as exact text at revision `1`; chapter 2 stayed empty at revision `0`.
- Held a real `PUT /api/v1/chapters/id/content`, typed a later local edit while the first save was in flight, forwarded the real request, and verified the backend ended with the later text at revision `3`.
- Reloaded and previewed the exact real API content.
- Created a second project/chapter and verified project context did not inherit chapter 1 text.
- Ran real stub-backed `POST /api/v1/refine`; response preserved `original` and returned `[QA 윤문 stub]` text.
- Made a human edit after refine and verified `POST /api/v1/refine/runs/run_id/accept` returned `409`; content stayed unchanged at the human edit.
- Created two nonempty scenes through the browser, merged them through real `PUT /content_from_scenes`, and verified exact merged content.
- Opened a pre-merge snapshot, viewed its text, held and forwarded a real restore request, typed during the in-flight restore, and verified server restored the original while the browser preserved the late local edit with conflict UI.

### Scoped frontend preservation fixture suite

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.preservation.config.ts
```

Result: exit `0`.

```text
[WebServer] ▲ [WARNING] Duplicate key "build" in object literal [duplicate-object-key]
[WebServer]
[WebServer]     vite.config.ts:38:2:
[WebServer]       38 │   build: {
[WebServer]          ╵   [WebServer] ~~~~~
[WebServer]
[WebServer]   The original key "build" is here:
[WebServer]
[WebServer]     vite.config.ts:11:2:
[WebServer]       11 │   build: {
[WebServer]          ╵   ~~~~~
[WebServer]

Running 13 tests using 1 worker

  ✓   1 [chromium] › e2e\manuscript-preservation.spec.ts:255:3 › manuscript preservation frontend fixture › serializes delayed per-chapter saves and preserves newer typing (3.3s)
  ✓   2 [chromium] › e2e\manuscript-preservation.spec.ts:280:3 › manuscript preservation frontend fixture › project switch rejects stale selected chapters and never writes under the new project context (852ms)
  ✓   3 [chromium] › e2e\manuscript-preservation.spec.ts:291:3 › manuscript preservation frontend fixture › keeps ApiError detail for 409 and shows local/server conflict recovery (998ms)
  ✓   4 [chromium] › e2e\manuscript-preservation.spec.ts:311:3 › manuscript preservation frontend fixture › recovers reload drafts, survives storage failure, and preserves text after network error (1.2s)
  ✓   5 [chromium] › e2e\manuscript-preservation.spec.ts:331:3 › manuscript preservation frontend fixture › preserves local text on network failure and reconciles lost save acknowledgements (783ms)
  ✓   6 [chromium] › e2e\manuscript-preservation.spec.ts:351:3 › manuscript preservation frontend fixture › does not let a pending refine accept response overwrite a late local edit (971ms)
  ✓   7 [chromium] › e2e\manuscript-preservation.spec.ts:376:3 › manuscript preservation frontend fixture › does not let a pending scene merge response overwrite a late edit or transfer to another chapter (1.1s)
  ✓   8 [chromium] › e2e\manuscript-preservation.spec.ts:406:3 › manuscript preservation frontend fixture › does not let a pending snapshot restore response overwrite a late local edit (968ms)
  ✓   9 [chromium] › e2e\manuscript-preservation.spec.ts:429:3 › manuscript preservation frontend fixture › does not acknowledge lost save responses when GET returns different text (664ms)
  ✓  10 [chromium] › e2e\manuscript-preservation.spec.ts:443:3 › manuscript preservation frontend fixture › pagehide uses revision contract and beforeunload leaves recoverable text (604ms)
  ✓  11 [chromium] › e2e\manuscript-preservation.spec.ts:461:3 › manuscript preservation frontend fixture › flushes before refine start, sends expected_revision, and blocks stale accept safely (824ms)
  ✓  12 [chromium] › e2e\manuscript-preservation.spec.ts:485:3 › manuscript preservation frontend fixture › scene trigger is accessible and merge flushes with expected_revision (846ms)
  ✓  13 [chromium] › e2e\manuscript-preservation.spec.ts:500:3 › manuscript preservation frontend fixture › shows snapshot text before explicit restore and restore uses current revision (1.0s)

  13 passed (16.6s)
```

This remains fixture-only by design. It covers localStorage quota failures, network abort paths, pagehide/beforeunload, lost-ack negative reconciliation, and additional pending replacement races.

### Backend API fixture and backup comparison

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel
backend\.venv\Scripts\python.exe scripts\preservation_backend_fixture.py --run-probes --json-report .eval_tmp\preservation-task3\backend-fixture-result.json
```

Result: exit `0`, status `passed`.

```json
{
  "work_dir": "C:\\Users\\wj941\\AppData\\Local\\Temp\\jippeel-preservation-qa-eg1zvhai",
  "database_url": "sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-preservation-qa-eg1zvhai/fixture.db",
  "final_revision": 3,
  "stub_calls": 1,
  "backup_tables": {
    "alembic_version": 1,
    "projects": 1,
    "chapters": 1,
    "chapter_snapshots": 3,
    "refine_runs": 1,
    "volume_notes": 1,
    "characters": 2,
    "relationships": 1,
    "lore_entries": 1,
    "scenes": 1,
    "foreshadows": 1
  }
}
```

The fixture compared exact full rows for `alembic_version`, `projects`, `chapters`, `chapter_snapshots`, `refine_runs`, `volume_notes`, `characters`, `relationships`, `lore_entries`, `scenes`, and `foreshadows` after SQLite `Connection.backup()`.

### Populated old-schema migration and backup comparison

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel
backend\.venv\Scripts\python.exe scripts\preservation_migration_fixture.py --json-report .eval_tmp\preservation-task3\migration-result.json
```

Result: exit `0`, status `passed`.

```json
{
  "work_dir": "C:\\Users\\wj941\\AppData\\Local\\Temp\\jippeel-preservation-migration-pta1qbmr",
  "database_url": "sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-preservation-migration-pta1qbmr/old-schema.db",
  "new_columns": {
    "chapters": [
      [
        1,
        0,
        null,
        "NULL volume old manuscript"
      ],
      [
        2,
        0,
        1,
        "volume one old manuscript"
      ]
    ],
    "refine_runs": [
      [
        1,
        null,
        "old refined result"
      ]
    ],
    "chapter_snapshots_count": 0,
    "alembic_version": "0a1b2c3d4e5f"
  },
  "relationship_rows": [
    [
      1,
      1,
      2,
      "old relationship",
      "relationship row must survive exactly"
    ]
  ],
  "chapter_rows": [
    [
      1,
      1,
      null,
      1.0,
      "권 없음 원고",
      "NULL volume old manuscript",
      "초고",
      23,
      "nullable volume chain",
      "2026-09-07 23:51:59",
      "2026-09-07 23:51:59"
    ],
    [
      2,
      1,
      1,
      2.0,
      "1권 원고",
      "volume one old manuscript",
      "수정중",
      22,
      "volume one chain",
      "2026-09-07 23:51:59",
      "2026-09-07 23:51:59"
    ]
  ],
  "backup_tables": {
    "alembic_version": 1,
    "projects": 1,
    "chapters": 2,
    "chapter_snapshots": 0,
    "refine_runs": 1,
    "volume_notes": 1,
    "characters": 2,
    "relationships": 1,
    "lore_entries": 1,
    "scenes": 1,
    "foreshadows": 1
  }
}
```

This upgraded a populated temp DB from `f9a1b2c3d4e5` to `0a1b2c3d4e5f`. Old nullable-volume chapter rows, manuscript text, refine rows, relationship rows, and creative rows matched exactly on old columns. New columns were checked: `chapters.revision = 0`, `refine_runs.base_revision = NULL`, and no historical snapshots were invented.

### Full backend suite

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\backend
set DATABASE_URL=sqlite:///C:/Users/wj941/AppData/Local/Temp/jippeel-task3-pytest-%RANDOM%.db
set JIPPEEL_ALLOW_TEMP_CREATE_ALL=1
.venv\Scripts\python.exe -m pytest -q
```

Result: exit `0`.

```text
........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 97%]
.....                                                                    [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\starlette\testclient.py:53
  C:\Users\wj941\Documents\jippeel\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
221 passed, 1 warning in 11.45s
```

### Frontend build

Command:

```cmd
cd /d C:\Users\wj941\Documents\jippeel\frontend
npm run build
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

[36mvite v5.4.21 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 229 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mindex.html                       [39m[1m[2m  0.66 kB[22m[1m[22m[2m │ gzip:   0.39 kB[22m
[2mdist/[22m[35massets/index-Ct_pw3J8.css        [39m[1m[2m 24.26 kB[22m[1m[22m[2m │ gzip:   5.66 kB[22m
[2mdist/[22m[36massets/markdown-Bx13qlMl.js      [39m[1m[2m130.22 kB[22m[1m[22m[2m │ gzip:  60.70 kB[22m
[2mdist/[22m[36massets/react-vendor-D_J2dLiK.js  [39m[1m[2m161.78 kB[22m[1m[22m[2m │ gzip:  52.80 kB[22m
[2mdist/[22m[36massets/index-LS8qaeM4.js         [39m[1m[2m203.93 kB[22m[1m[22m[2m │ gzip:  59.92 kB[22m
[2mdist/[22m[36massets/editor-dbPoz2N-.js        [39m[1m[2m475.11 kB[22m[1m[22m[2m │ gzip: 165.91 kB[22m
[32m✓ built in 3.13s[39m
```

The duplicate `build` key warning is pre-existing and was recorded in earlier environment notes.

## Limitations

- No production DB, WAL/SHM, config, secrets, service, or real endpoint was touched.
- No paid model or real external LLM call was made.
- The real browser integration covers a held/forwarded save race and a held/forwarded restore replacement race. Refine accept and scene merge late-edit replacement races remain covered by the scoped frontend fixture suite.
- No deployment or production migration was performed. The runbook documents required manual backup, copy-upgrade, coordinated deploy, and rollback steps.
