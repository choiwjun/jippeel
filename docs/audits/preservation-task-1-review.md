# Preservation Task 1 Review — backend revision/snapshot gate

## Verdicts

- **Spec verdict:** **Blocked.** The main backend contract is mostly present, and the focused/full backend tests pass. But the no-op race conflict response can report a stale `current_revision`, which violates the revision-conflict contract and the explicit no-op race clarification.
- **Code quality verdict:** **Changes requested.** The write service centralizes mutations well, but conflict-current lookup in the no-op path is not reliable under a stale identity-map session. Test coverage also misses several consequential cases the brief required.

## Verification run

Commands were run from `backend/` with native Windows Python. Each command set a fresh tempfile `DATABASE_URL` before importing pytest/app and set `JIPPEEL_ALLOW_TEMP_CREATE_ALL=1` only for temporary test initialization.

```text
.venv/Scripts/python.exe -c "import os,tempfile,pathlib,pytest,sys; d=pathlib.Path(tempfile.mkdtemp(prefix='jippeel-review-focus-')); os.environ['DATABASE_URL']='sqlite:///'+(d/'lifespan.db').as_posix(); os.environ['JIPPEEL_ALLOW_TEMP_CREATE_ALL']='1'; sys.exit(pytest.main(['tests/test_manuscript_preservation.py','tests/test_migrations.py','-q']))"
```

Result: `17 passed, 1 warning in 1.94s`.

```text
.venv/Scripts/python.exe -c "import os,tempfile,pathlib,pytest,sys; d=pathlib.Path(tempfile.mkdtemp(prefix='jippeel-review-full-')); os.environ['DATABASE_URL']='sqlite:///'+(d/'lifespan.db').as_posix(); os.environ['JIPPEEL_ALLOW_TEMP_CREATE_ALL']='1'; sys.exit(pytest.main(['-q']))"
```

Result: `215 passed, 1 warning in 11.46s`.

## Findings

### High — no-op race can return a stale `current_revision`

- **File:** `backend/app/services/manuscripts.py:57-70`
- **Issue:** In the no-op path, the service loads a `Chapter`, sees matching content/revision, then runs a conditional no-op `UPDATE`. If another session changes the chapter after this session cached the row, the no-op `UPDATE` correctly affects 0 rows. But the conflict handler reads `latest = db.get(Chapter, chapter_id)`, which can return the stale identity-map object. The raised `RevisionConflict.current_revision` can therefore be old.
- **Why this matters:** The spec requires 409 detail to include the current revision. The binding clarification also calls out no-op racing a changing write. A frontend conflict handler can rebase to the wrong revision.
- **Repro evidence:** I ran a direct service probe with two real SQLAlchemy sessions on a tempfile SQLite DB:

```text
s2 cached before 1 same
s1 committed returned 2 new
conflict current_revision 1
actual 2 new snaps [(1, 'same')]
```

The no-op conflict reported `current_revision == 1`, but the actual chapter revision was `2`.

- **Likely fix:** Do not use the identity-map cached object to populate conflicts after rowcount 0. Expire/refresh it first, or fetch the scalar revision with a query that bypasses/populates over the identity map. Apply the same helper in both rowcount-conflict paths.

### Medium — required no-op race coverage is missing

- **File:** `backend/tests/test_manuscript_preservation.py:64-103`
- **Issue:** The tests cover a serial no-op/stale-same-payload case and two concurrent changing writes. They do not cover a no-op racing a changing writer.
- **Why this matters:** The missing case is where the high-severity bug above appears. The brief explicitly required no-op racing a changing write.
- **Concrete missing coverage:** Add a deterministic service or route-level test where one session/request has a cached same-content revision, another writer advances the chapter, and the no-op returns 409 with the real latest `current_revision` and no extra snapshot.

### Medium — rollback test does not exercise a real DB snapshot failure

- **File:** `backend/tests/test_manuscript_preservation.py:246-289`
- **Issue:** The rollback test monkeypatches `db.flush` to raise `RuntimeError`. It proves caller rollback can revert the update, but it does not exercise the real DB unique/integrity path in `backend/app/services/manuscripts.py:97-103`.
- **Repro evidence:** A manual tempfile DB probe with a pre-existing `(chapter_id, revision)` snapshot showed rollback preserves the manuscript:

```text
conflict current_revision 1
actual 0 old snaps [(0, 'dupe')]
```

That confirms rollback, but it also shows this path reports `expected_revision + 1` even when the actual DB revision remains `0` after rollback. This should be locked down or handled more explicitly.
- **Concrete missing coverage:** Add a DB-backed duplicate snapshot/unique-constraint rollback test. Assert chapter content/revision and snapshots after rollback, and decide what `current_revision` should be for this integrity case.

### Medium — populated old-migration coverage is narrower than the spec

- **File:** `backend/tests/test_migrations.py:66-105`
- **Issue:** The automated populated migration test starts from `f9a1b2c3d4e5` only. The approved spec also asked for a populated older-chain upgrade that includes the nullable-volume migration.
- **Manual probe evidence:** I ran a tempfile Alembic probe from `d85fdcab0808` with one populated project/chapter through `head`; it passed and preserved data:

```text
row {'volume': 1, 'content_md': 'old', 'revision': 0} version 0a1b2c3d4e5f has_snapshots True
```

- **Concrete missing coverage:** Add this as an automated migration test so future edits cannot break populated upgrades across `b3c4d5e6f7a8_chapter_volume_nullable.py`.

### Low — schema guard helper decides temp bypass from module global URL, not the passed engine

- **File:** `backend/app/database.py:68-84`
- **Issue:** `assert_manuscript_schema_current(bind)` accepts a `bind`, but `_allow_temp_create_all()` checks the module-level `DATABASE_URL`. A custom engine can be skipped if the imported global URL is an allowed temp DB.
- **Impact:** Normal `init_db()` uses the global engine, so this is not the main startup path. But it can make helper-level probes/tests false-positive and is easy to harden by checking `str(bind.url)`.

## Coverage notes

Covered by current tests and code inspection:

- `expected_revision` is required by schemas for PUT/POST content, scene merge, restore, and refine start.
- Stale content writes return structured 409 and do not mutate current content in serial API tests.
- Refine start captures `input_content_md` and `base_revision` before pipeline execution in code, and stale known revisions skip the pipeline.
- Refine accept uses `run.base_revision`, returns `ChapterDetail`, and leaves `accepted=false` on stale accept.
- Snapshot detail/restore check same-chapter ownership. Restore creates a new snapshot for undo.
- Startup calls `init_db()` before FTS/seed in `app/main.py:20-25`, and guard tests cover missing preservation schema and valid head.

Additional consequential API coverage still worth adding:

- Missing/stale `expected_revision` on snapshot restore.
- Conflict response `current_revision` for concurrent changing writer losers.
- Snapshot `reason` values for autosave/refine/scene_merge/restore.
