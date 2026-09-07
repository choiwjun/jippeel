# Preservation Task 1 Report — Atomic manuscript writes

## Status
Implemented backend Task 1 on branch `feat/manuscript-preservation`.

No production DB, WAL/SHM, real server, or real LLM endpoint was used.
All backend commands set `DATABASE_URL` to a fresh tempfile SQLite path before importing pytest/app.
Temporary lifespan `create_all` was explicitly marked with `JIPPEEL_ALLOW_TEMP_CREATE_ALL=1`.

## Changed backend contract
- `Chapter.revision` is returned in chapter list/detail responses. It starts at `0`.
- `PUT /api/v1/chapters/{cid}/content` and `POST /api/v1/chapters/{cid}/content` require `expected_revision`.
- Stale writes return `409` with `detail.code == "revision_conflict"` and `current_revision`.
- Successful content changes create a `ChapterSnapshot` for the pre-change manuscript.
- Same-revision same-content writes are no-op and do not create snapshots or increment revision.
- Snapshot routes were added:
  - `GET /api/v1/chapters/{cid}/snapshots`
  - `GET /api/v1/chapters/{cid}/snapshots/{sid}`
  - `POST /api/v1/chapters/{cid}/restore`
- `POST /api/v1/refine` now requires `expected_revision` and rejects stale runs before the pipeline.
- Refine runs store `base_revision`; accept uses it and returns `ChapterDetail`.
- `PUT /api/v1/chapters/{cid}/content_from_scenes` requires `expected_revision` and rejects empty merged content.

## Atomicity details
- New service: `backend/app/services/manuscripts.py`.
- Changing writes use guarded SQL update: `Chapter.id == chapter_id` and `Chapter.revision == expected_revision`.
- Snapshots and manuscript updates are in the caller transaction.
- Snapshot insert failure rolls back the manuscript update.
- No-op writes use a conditional update to validate revision at the DB write boundary.
- Snapshot unique conflicts are mapped to revision conflicts only when the snapshot constraint is involved.

## Migration and startup
- New Alembic revision: `0a1b2c3d4e5f_manuscript_preservation.py` after `f9a1b2c3d4e5`.
- Adds `chapters.revision`, `chapter_snapshots`, and `refine_runs.base_revision`.
- Populated pre-preservation migration probe keeps chapter content and sets revision to `0`.
- Startup guard checks preservation columns/table, snapshot unique/indexes, and Alembic head before seed/FTS/create_all.
- Normal empty DB startup now fails with an actionable `alembic upgrade head` instruction.
- Only explicitly marked temp test DBs may use `create_all`.

## TDD evidence
### Red
```text
.venv/Scripts/python.exe -c "import os,tempfile,pathlib,pytest,sys; d=pathlib.Path(tempfile.mkdtemp(prefix='jippeel-red-')); os.environ['DATABASE_URL']='sqlite:///'+(d/'lifespan.db').as_posix(); sys.exit(pytest.main(['tests/test_manuscript_preservation.py','-q']))"
Result: 8 failed, 1 warning. Expected failures included missing `revision`, stale content write accepted as 200/200, missing snapshot routes, empty scene merge accepted, missing `base_revision`, and refine accept returning SimpleOk instead of ChapterDetail.
```

### Green: focused preservation and migration tests
```text
.venv/Scripts/python.exe -c "import os,tempfile,pathlib,pytest,sys; d=pathlib.Path(tempfile.mkdtemp(prefix='jippeel-rel-')); os.environ['DATABASE_URL']='sqlite:///'+(d/'lifespan.db').as_posix(); os.environ['JIPPEEL_ALLOW_TEMP_CREATE_ALL']='1'; sys.exit(pytest.main(['tests/test_manuscript_preservation.py','tests/test_migrations.py','-q']))"
Result: 17 passed, 1 warning in 1.68s.
```

### Green: affected backend slice
```text
.venv/Scripts/python.exe -c "import os,tempfile,pathlib,pytest,sys; d=pathlib.Path(tempfile.mkdtemp(prefix='jippeel-aff2-')); os.environ['DATABASE_URL']='sqlite:///'+(d/'lifespan.db').as_posix(); os.environ['JIPPEEL_ALLOW_TEMP_CREATE_ALL']='1'; sys.exit(pytest.main(['tests/test_manuscript_preservation.py','tests/test_chapters_api.py','tests/test_refine_api.py','tests/test_scenes_api.py','tests/test_godohwa_v2.py','tests/test_migrations.py','-q']))"
Result: 52 passed, 1 warning in 3.70s.
```

### Green: full backend suite
```text
.venv/Scripts/python.exe -c "import os,tempfile,pathlib,pytest,sys; d=pathlib.Path(tempfile.mkdtemp(prefix='jippeel-full2-')); os.environ['DATABASE_URL']='sqlite:///'+(d/'lifespan.db').as_posix(); os.environ['JIPPEEL_ALLOW_TEMP_CREATE_ALL']='1'; sys.exit(pytest.main(['-q']))"
Result: 215 passed, 1 warning in 10.93s.
```

## Files changed
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/services/manuscripts.py`
- `backend/app/routers/projects.py`
- `backend/app/routers/refine.py`
- `backend/app/routers/scenes.py`
- `backend/app/database.py`
- `backend/alembic/versions/0a1b2c3d4e5f_manuscript_preservation.py`
- `backend/tests/test_manuscript_preservation.py`
- `backend/tests/test_migrations.py`
- Existing backend tests and `scripts/write_volume1.py` updated to send explicit revisions.

## Concerns and handoff
- Frontend callers still need Task 2 updates for `expected_revision` and structured 409 handling.
- I did not run frontend build or browser QA in this task.
- I did not push, merge, or migrate production data.
