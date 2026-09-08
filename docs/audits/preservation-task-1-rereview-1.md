# Preservation Task 1 Re-review 1 — fix round 1

## Verdicts

- **Spec verdict:** **Pass / clear for Task 2 handoff.** The blocker from the first review is addressed. I found no new spec breakage in `ff7b02b..836619b`.
- **Code quality verdict:** **Pass.** The fix uses a shared fresh revision helper, covers the race and rollback cases with deterministic tests, and hardens the temp schema guard against false bypass.

## Scope reviewed

Inputs:

- Updated implementer report: `docs/audits/preservation-task-1-report.md`
- Fix diff: `docs/audits/preservation-task-1-fix-1-diff.txt` (`ff7b02b..836619b`)
- Original review: `docs/audits/preservation-task-1-review.md`

I reviewed the actual current code and tests for the fix diff only. I did not implement changes, use production DB/server/LLM, install dependencies, or spawn children.

## Native verification run

Commands were run from `backend/` with native Windows Python. Each command sets a fresh tempfile `DATABASE_URL` before importing pytest/app. `JIPPEEL_ALLOW_TEMP_CREATE_ALL=1` is set only for temporary test initialization.

```text
.venv/Scripts/python.exe -c "import os,tempfile,pathlib,pytest,sys; d=pathlib.Path(tempfile.mkdtemp(prefix='jippeel-rereview-focus-')); os.environ['DATABASE_URL']='sqlite:///'+(d/'lifespan.db').as_posix(); os.environ['JIPPEEL_ALLOW_TEMP_CREATE_ALL']='1'; sys.exit(pytest.main(['tests/test_manuscript_preservation.py','tests/test_migrations.py','-q']))"
```

Result: `23 passed, 1 warning in 1.66s`.

```text
.venv/Scripts/python.exe -c "import os,tempfile,pathlib,pytest,sys; d=pathlib.Path(tempfile.mkdtemp(prefix='jippeel-rereview-full-')); os.environ['DATABASE_URL']='sqlite:///'+(d/'lifespan.db').as_posix(); os.environ['JIPPEEL_ALLOW_TEMP_CREATE_ALL']='1'; sys.exit(pytest.main(['-q']))"
```

Result: `221 passed, 1 warning in 11.43s`.

Additional independent probes:

- Two-session service no-op race now reports `current_revision 2` when actual persisted revision is `2`.
- Duplicate snapshot unique rollback now reports `current_revision 0` and preserves `revision 0`, `content_md='old'`.
- Populated old migration from `d85fdcab0808` through head preserves a `refine_runs.chapter_id` reference, keeps `base_revision=None`, leaves `PRAGMA foreign_keys=1` on a fresh connection, and blocks an invalid FK insert with `IntegrityError`.

## Original findings status

### Addressed — High: no-op race stale `current_revision`

- **Original file:** `backend/app/services/manuscripts.py:57-70`
- **Fix evidence:** `backend/app/services/manuscripts.py:35-43` adds `_fresh_current_revision()`, which expires the identity map and reads `Chapter.revision` as a scalar query. Rowcount conflicts use it in both no-op and changing write paths at `backend/app/services/manuscripts.py:88-105`.
- **Test evidence:** `backend/tests/test_manuscript_preservation.py:308-359` deterministically caches a no-op session, advances the chapter in a second session, and asserts `RevisionConflict.current_revision == 2` plus no extra snapshot.
- **Independent repro result:** `noop race current_revision 2`.

### Addressed — Medium: required no-op race coverage missing

- **Fix evidence:** Covered by `backend/tests/test_manuscript_preservation.py:308-359`.
- **Verdict:** Addressed.

### Addressed — Medium: rollback test did not exercise real DB snapshot failure

- **Fix evidence:** `backend/tests/test_manuscript_preservation.py:362-408` creates a real pre-existing `(chapter_id, revision)` snapshot and exercises the DB unique constraint path.
- **Code evidence:** `backend/app/services/manuscripts.py:46-52` narrows unique-error mapping to SQLite snapshot revision unique errors. `backend/app/services/manuscripts.py:117-120` rolls back before reading the persisted current revision.
- **Independent repro result:** `dupe current_revision 0`; persisted row stayed `revision 0`, `content_md old`.
- **Verdict:** Addressed.

### Addressed — Medium: populated old-migration coverage too narrow

- **Fix evidence:** `backend/tests/test_migrations.py:132-188` starts at `d85fdcab0808`, inserts a populated project/chapter, a `refine_runs` row that references the chapter, `characters`, `relationships`, and `lore_entries`, upgrades through head, and asserts content/revision/reference preservation.
- **Migration fix evidence:** `backend/alembic/versions/b3c4d5e6f7a8_chapter_volume_nullable.py:22-32` disables SQLite FK checks only around the batch alteration and restores them in `finally`.
- **Independent probe result:** Old-chain upgrade preserved the referenced `refine_runs` row and a fresh connection reported `PRAGMA foreign_keys == 1`; an invalid FK insert was blocked.
- **Verdict:** Addressed.

### Addressed — Low: schema guard temp bypass used module global URL

- **Fix evidence:** `backend/app/database.py:68-84` now accepts a URL, and `assert_manuscript_schema_current(bind)` passes `str(bind.url)`. `init_db()` also passes `str(engine.url)` at `backend/app/database.py:143-145`.
- **Test evidence:** `backend/tests/test_migrations.py:191-209` verifies that an allowed global temp URL does not bypass a different passed engine URL.
- **Verdict:** Addressed.

## Previously noted coverage gaps

- **Restore missing/stale expected revision:** Addressed by `backend/tests/test_manuscript_preservation.py:411-438`.
- **Concurrent changing loser `current_revision`:** Addressed by `backend/tests/test_manuscript_preservation.py:87-105`.
- **Snapshot reason values:** Addressed by restore reason checks at `backend/tests/test_manuscript_preservation.py:411-438` and refine/scene reason checks at `backend/tests/test_manuscript_preservation.py:441-459`.

## New findings in fix diff

None found.
