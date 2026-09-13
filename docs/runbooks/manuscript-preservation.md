# Manuscript preservation safe deployment runbook

This runbook is manual. It does not apply migrations or deploy production automatically.

## Safety rules

- Do not run tests, Alembic, or fixture scripts against `backend/jippeel.db` unless it is an explicit copied staging DB.
- Do not touch production WAL/SHM files directly while services are running.
- Do not use ports `:8000` or `:5173` for integration rehearsal unless the deployment owner explicitly assigns them.
- Do not call paid LLM endpoints during preservation deployment verification. Use deterministic stubs for technical checks.
- Backend and frontend must deploy together because manuscript writes require `expected_revision`.

## Required rehearsal commands

Run these from a normal Windows shell on a copied or temporary DB only.

```cmd
cd /d C:\Users\wj941\Documents\jippeel
backend\.venv\Scripts\python.exe scripts\preservation_migration_fixture.py
backend\.venv\Scripts\python.exe scripts\preservation_backend_fixture.py --run-probes
cd /d C:\Users\wj941\Documents\jippeel\frontend
npx playwright test --config playwright.preservation.integration.config.ts
npx playwright test --config playwright.preservation.config.ts
npm run build
```

For backend pytest, use the [supported isolated runner](isolated-backend-tests.md). It installs Windows-local TEMP DB/key/coverage paths and fake keyring before app imports. Direct pytest and inherited conflicting test variables fail closed; a DB variable alone is insufficient.

```cmd
cd /d C:\Users\wj941\Documents\jippeel\backend
.venv\Scripts\python.exe -I -S -B scripts\run_backend_pytest.py --isolation-preflight
```

Only after the preflight exits successfully:

```cmd
.venv\Scripts\python.exe -I -B scripts\run_backend_pytest.py -q
```

## Pre-deploy checks

1. Announce a write freeze window.
2. Stop or block writer traffic before copying the DB.
3. Confirm the currently deployed backend and frontend versions.
4. Confirm the target revision includes manuscript preservation backend and matching frontend save contract.
5. Confirm backup storage has enough space for the DB plus any WAL/SHM files.

## Backup

Use SQLite's online backup API to copy the DB to a **new** destination file. Do not perform a loose file copy of `*.db`, `*.db-wal`, and `*.db-shm` as the verified backup procedure.

Preconditions:

1. Stop the production backend, or otherwise prove no SQLite writer is active.
2. Pick a new backup destination path. The file must not already exist.
3. Open the source DB with SQLite URI `mode=ro`.
4. Refuse to overwrite the destination.
5. Verify the backup before any production migration.

Save this reviewed one-off script as `<safe-temp>\sqlite_backup_once.py`, then run it with the backend venv Python:

```cmd
cd /d <project>\backend
.venv\Scripts\python.exe <safe-temp>\sqlite_backup_once.py --source <production-db-path> --dest <new-backup-db-path>
```

```python
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any


def ro_uri(path: Path) -> str:
    return path.resolve().as_uri() + "?mode=ro"


def user_tables(conn: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_schema "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    ]


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
    if not columns:
        raise SystemExit(f"no visible columns for table {table}")
    return columns


def table_rows(conn: sqlite3.Connection, table: str, columns: list[str]) -> list[tuple[Any, ...]]:
    col_sql = ", ".join(f'"{col}"' for col in columns)
    try:
        return conn.execute(f'SELECT {col_sql} FROM "{table}" ORDER BY rowid').fetchall()
    except sqlite3.DatabaseError:
        return conn.execute(f'SELECT {col_sql} FROM "{table}"').fetchall()


def verify_copy(source: Path, dest: Path) -> None:
    with sqlite3.connect(ro_uri(source), uri=True) as src, sqlite3.connect(ro_uri(dest), uri=True) as dst:
        for label, conn in (("source", src), ("dest", dst)):
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise SystemExit(f"{label} integrity_check failed: {integrity}")
            quick = conn.execute("PRAGMA quick_check").fetchone()[0]
            if quick != "ok":
                raise SystemExit(f"{label} quick_check failed: {quick}")

        src_tables = user_tables(src)
        dst_tables = user_tables(dst)
        if src_tables != dst_tables:
            raise SystemExit(f"table list mismatch: {src_tables} != {dst_tables}")

        for table in src_tables:
            src_columns = table_columns(src, table)
            dst_columns = table_columns(dst, table)
            if src_columns != dst_columns:
                raise SystemExit(f"column mismatch in {table}: {src_columns} != {dst_columns}")
            if table_rows(src, table, src_columns) != table_rows(dst, table, dst_columns):
                raise SystemExit(f"row mismatch in {table}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()

    source = args.source.resolve()
    dest = args.dest.resolve()
    if not source.exists():
        raise SystemExit(f"source DB does not exist: {source}")
    if dest.exists():
        raise SystemExit(f"destination already exists; refusing overwrite: {dest}")
    if not dest.parent.exists():
        raise SystemExit(f"destination directory does not exist: {dest.parent}")

    with sqlite3.connect(ro_uri(source), uri=True) as src, sqlite3.connect(str(dest)) as dst:
        src.backup(dst)

    verify_copy(source, dest)
    print(f"backup complete and verified: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Keep these records:

- source DB path
- new backup DB path
- source and destination file sizes after backup
- source and destination `PRAGMA integrity_check` results
- source and destination `PRAGMA quick_check` results
- exact table-list, column-list, and full-row comparison result
- timestamp
- operator

## Copy-upgrade rehearsal

Run the migration on a copied DB first.

```cmd
cd /d <project>\backend
set DATABASE_URL=sqlite:///<absolute-copy-db-path-with-forward-slashes>
.venv\Scripts\python.exe -m alembic upgrade head
```

Then start the backend against only the copied DB on an unused rehearsal port.

```cmd
set DATABASE_URL=sqlite:///<absolute-copy-db-path-with-forward-slashes>
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port <unused-port>
```

Verify:

- startup does not use `JIPPEEL_ALLOW_TEMP_CREATE_ALL`
- Alembic head is current
- `chapters.revision` exists and old rows default to `0`
- `chapter_snapshots` exists with `(chapter_id, revision)` unique constraint
- `refine_runs.base_revision` exists and old rows remain `NULL`
- nullable `chapters.volume` rows stay `NULL`
- old manuscript, refine, relationship, scene, lore, character, foreshadow, and volume-note rows match exactly on old columns
- stale manuscript write returns `409 revision_conflict`
- snapshot restore preserves the current pre-image
- a SQLite backup copy of the upgraded copy matches relevant full table rows

## Coordinated deploy

1. Keep writer traffic stopped.
2. Deploy the backend build that enforces the revision contract.
3. Run Alembic upgrade on the production DB only after backup and copy-upgrade checks pass.
4. Deploy the matching frontend build in the same window.
5. Start backend and frontend.
6. Run smoke checks on a synthetic or staging project, not real author manuscript content unless the owner explicitly approves.
7. Re-enable writer traffic.

## Rollback

If migration or startup fails before writer traffic resumes:

1. Stop the new backend/frontend.
2. Restore the pre-upgrade DB backup.
3. Redeploy the previous backend/frontend pair.
4. Confirm health checks.
5. Reopen writer traffic only after the previous version is healthy.

If writer traffic resumed after migration, do not blindly restore the old DB. First decide how to preserve any post-migration writes.

## Post-deploy smoke checks

- Create or select a safe synthetic chapter.
- Save with the current revision and confirm revision increments.
- Attempt a stale save and confirm `409 revision_conflict`.
- Confirm snapshots list and detail return expected pre-image content.
- Confirm restore creates a new snapshot before replacing content.
- Confirm frontend save/refine UI uses the matching backend revision contract.

## Notes

Snapshot rows are not a replacement for DB backups. They protect manuscript replacement paths inside the app. Production backup remains mandatory before migration.
