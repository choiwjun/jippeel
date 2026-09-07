#!/usr/bin/env python3
r"""Populated old-schema migration and backup probe for manuscript preservation.

Run with the native Windows backend venv Python, for example:

    backend\.venv\Scripts\python.exe scripts\preservation_migration_fixture.py

The script creates a temporary SQLite DB, upgrades it to the historical
pre-preservation Alembic revision, seeds synthetic manuscript/creative rows,
then upgrades to head. It compares exact row content for the pre-existing
columns before/after, checks new preservation columns, and performs a SQLite
Connection.backup() comparison on the migrated DB.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

# Import the existing strict fixture helpers instead of duplicating startup and
# backup rules.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from preservation_backend_fixture import (  # noqa: E402
    ProbeError,
    assert_native_windows_python,
    now_iso,
    project_root,
    run_cmd,
    sqlite_backup_and_compare,
    sqlite_url,
)

OLD_REVISION = "f9a1b2c3d4e5"
HEAD_REVISION = "0a1b2c3d4e5f"
COMMON_TABLES = [
    "projects",
    "chapters",
    "refine_runs",
    "volume_notes",
    "characters",
    "relationships",
    "lore_entries",
    "scenes",
    "foreshadows",
]


def build_env(db_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("JIPPEEL_ALLOW_TEMP_CREATE_ALL", None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["DATABASE_URL"] = sqlite_url(db_path)
    return env


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def seed_old_schema(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, title, genre, synopsis, platform_note, memo, style_profile) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "마이그레이션 보존 합성 작품", "QA", "old schema synopsis", "no production config", "old memo", "old style"),
        )
        conn.execute(
            "INSERT INTO chapters (id, project_id, volume, sort_order, title, content_md, status, word_count_cache, memo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 1, None, 1.0, "권 없음 원고", "NULL volume old manuscript", "초고", 23, "nullable volume chain"),
        )
        conn.execute(
            "INSERT INTO chapters (id, project_id, volume, sort_order, title, content_md, status, word_count_cache, memo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2, 1, 1, 2.0, "1권 원고", "volume one old manuscript", "수정중", 22, "volume one chain"),
        )
        conn.execute(
            "INSERT INTO refine_runs (id, chapter_id, route_hint, changed_ratio, report_json, result_text, accepted) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, 1, "light", 0.12, json.dumps({"old": True, "chapter": 1}, ensure_ascii=False), "old refined result", 0),
        )
        conn.execute(
            "INSERT INTO volume_notes (id, project_id, volume, title, overview, emotion_curve, climax_note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, 1, 1, "합성 권 개요", "old overview", "old curve", "old climax"),
        )
        conn.execute(
            "INSERT INTO characters (id, project_id, name, aliases, role, appearance, personality, speech_style, background, card_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 1, "마이그레이션 주인공", json.dumps(["old-a"], ensure_ascii=False), "주연", "old coat", "calm", "short", "old bg a", json.dumps({"slot": "a"}, ensure_ascii=False)),
        )
        conn.execute(
            "INSERT INTO characters (id, project_id, name, aliases, role, appearance, personality, speech_style, background, card_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2, 1, "마이그레이션 조력자", json.dumps(["old-b"], ensure_ascii=False), "조연", "old pen", "curious", "question", "old bg b", json.dumps({"slot": "b"}, ensure_ascii=False)),
        )
        conn.execute(
            "INSERT INTO relationships (id, from_character_id, to_character_id, label, note) VALUES (?, ?, ?, ?, ?)",
            (1, 1, 2, "old relationship", "relationship row must survive exactly"),
        )
        conn.execute(
            "INSERT INTO lore_entries (id, project_id, category, title, content, keywords) VALUES (?, ?, ?, ?, ?, ?)",
            (1, 1, "장소", "old city", "old lore content", json.dumps(["old", "city"], ensure_ascii=False)),
        )
        conn.execute(
            "INSERT INTO scenes (id, chapter_id, sort_order, title, content_md) VALUES (?, ?, ?, ?, ?)",
            (1, 1, 1.0, "old scene", "old scene body"),
        )
        conn.execute(
            "INSERT INTO foreshadows (id, project_id, title, content, keywords, status, planted_chapter_id, resolved_chapter_id, audience_knows) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 1, "old clue", "old foreshadow content", json.dumps(["old clue"], ensure_ascii=False), "설치", 1, None, 0),
        )
        conn.commit()


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def rows_for(conn: sqlite3.Connection, table: str, cols: list[str]) -> list[list[Any]]:
    order = "id" if "id" in cols else cols[0]
    sql = f'SELECT {", ".join(f"\"{c}\"" for c in cols)} FROM "{table}" ORDER BY "{order}"'
    return [[value for value in row] for row in conn.execute(sql).fetchall()]


def capture_common_rows(db_path: Path) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    with connect(db_path) as conn:
        for table in COMMON_TABLES:
            cols = columns(conn, table)
            captured[table] = {"columns": cols, "rows": rows_for(conn, table, cols)}
    return captured


def compare_common_rows(db_path: Path, before: dict[str, Any]) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    with connect(db_path) as conn:
        for table, expected in before.items():
            before_cols = expected["columns"]
            after_cols = columns(conn, table)
            missing = [col for col in before_cols if col not in after_cols]
            if missing:
                raise ProbeError(f"Migrated table {table} lost columns: {missing}")
            after_rows = rows_for(conn, table, before_cols)
            if after_rows != expected["rows"]:
                raise ProbeError(f"Migrated table {table} changed old-column row contents")
            comparison[table] = {"columns": before_cols, "row_count": len(after_rows), "rows": after_rows}

        chapter_new = conn.execute("SELECT id, revision, volume, content_md FROM chapters ORDER BY id").fetchall()
        if [[row[0], row[1]] for row in chapter_new] != [[1, 0], [2, 0]]:
            raise ProbeError(f"Unexpected migrated chapter revisions: {chapter_new}")
        if chapter_new[0][2] is not None:
            raise ProbeError("Nullable-volume chapter was not preserved as NULL")
        refine_new = conn.execute("SELECT id, base_revision, result_text FROM refine_runs ORDER BY id").fetchall()
        if [[row[0], row[1], row[2]] for row in refine_new] != [[1, None, "old refined result"]]:
            raise ProbeError(f"Unexpected migrated refine rows: {refine_new}")
        snapshots_count = conn.execute("SELECT COUNT(*) FROM chapter_snapshots").fetchone()[0]
        if snapshots_count != 0:
            raise ProbeError(f"Migration should not synthesize snapshots for old rows, got {snapshots_count}")
        head = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        if head != HEAD_REVISION:
            raise ProbeError(f"Unexpected Alembic head {head}")
        comparison["new_columns"] = {
            "chapters": [[row[0], row[1], row[2], row[3]] for row in chapter_new],
            "refine_runs": [[row[0], row[1], row[2]] for row in refine_new],
            "chapter_snapshots_count": snapshots_count,
            "alembic_version": head,
        }
    return comparison


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populated old-schema migration probe")
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--json-report", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()
    result: dict[str, Any] = {
        "started_at": now_iso(),
        "status": "started",
        "project_root": str(root),
        "python_executable": sys.executable,
        "old_revision": OLD_REVISION,
        "head_revision": HEAD_REVISION,
    }
    try:
        assert_native_windows_python(root)
        work_dir = args.work_dir or Path(tempfile.mkdtemp(prefix="jippeel-preservation-migration-"))
        work_dir.mkdir(parents=True, exist_ok=True)
        db_path = work_dir / "old-schema.db"
        backup_path = work_dir / "old-schema-backup.db"
        if db_path.exists():
            raise ProbeError(f"Refusing to reuse existing DB: {db_path}")
        env = build_env(db_path)
        result.update({"work_dir": str(work_dir), "db_path": str(db_path), "backup_path": str(backup_path), "database_url": env["DATABASE_URL"], "jippeel_allow_temp_create_all": env.get("JIPPEEL_ALLOW_TEMP_CREATE_ALL")})

        backend_dir = root / "backend"
        old_log = work_dir / "alembic-upgrade-old.json"
        head_log = work_dir / "alembic-upgrade-head.json"
        run_cmd([sys.executable, "-m", "alembic", "upgrade", OLD_REVISION], backend_dir, env, old_log, timeout=180)
        seed_old_schema(db_path)
        before = capture_common_rows(db_path)
        run_cmd([sys.executable, "-m", "alembic", "upgrade", "head"], backend_dir, env, head_log, timeout=180)
        migration_comparison = compare_common_rows(db_path, before)
        backup_comparison = sqlite_backup_and_compare(db_path, backup_path)

        result.update({
            "status": "passed",
            "finished_at": now_iso(),
            "alembic_old_log": str(old_log),
            "alembic_head_log": str(head_log),
            "migration_comparison": migration_comparison,
            "backup_comparison": backup_comparison,
            "validated": [
                "Alembic upgrade to historical pre-preservation revision on a temp SQLite DB",
                "Synthetic old-schema manuscript, nullable-volume, refine, relationship, and creative rows survived upgrade head exactly on old columns",
                "New chapters.revision defaults to 0 and refine_runs.base_revision remains NULL for historical rows",
                "No synthetic chapter_snapshots were invented for historical rows",
                "SQLite Connection.backup exact full-row comparison after migration",
            ],
        })
        report_path = work_dir / "preservation-migration-result.json"
        result["result_json"] = str(report_path)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.json_report:
            args.json_report.parent.mkdir(parents=True, exist_ok=True)
            args.json_report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI must record failures
        result.update({"status": "failed", "error": repr(exc), "finished_at": now_iso()})
        with contextlib.suppress(Exception):
            work_dir = Path(result.get("work_dir") or tempfile.gettempdir())
            fail_path = work_dir / "preservation-migration-result.failed.json"
            fail_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result["result_json"] = str(fail_path)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
