"""백업 복원 검증기 — V02 failure injection.

백업·복원 설계(docs/audits/backup-restore-design-2026-09-10.md)의 restore
dry-run 절차를 코드로 고정한다. 합성·임시 경로 전용 — 운영 DB·keyring·
credential·실제 provider에 접근하지 않는다. wrong-key 복호화 검증은
G03 승인 범위로 분리한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
import sqlite3
from pathlib import Path
from typing import Any


class RestoreErrorCode(StrEnum):
    MANIFEST_MISSING = "manifest_missing"
    MANIFEST_INVALID = "manifest_invalid"
    FILE_MISSING = "file_missing"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    NOT_SQLITE = "not_sqlite"
    INTEGRITY_FAILED = "integrity_failed"
    FOREIGN_KEY_FAILED = "foreign_key_failed"
    SCHEMA_HEAD_MISMATCH = "schema_head_mismatch"
    BACKUP_WRITE_FAILED = "backup_write_failed"


class RestoreVerifyError(Exception):
    def __init__(self, code: RestoreErrorCode, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class Failure:
    code: RestoreErrorCode
    detail: str


@dataclass
class VerifyReport:
    ok: bool
    failures: list[Failure] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


_DB_FILE = "database.sqlite3"
_MANIFEST_REQUIRED = {"format_version", "created_at", "alembic_head", "files"}


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_alembic_head(conn: sqlite3.Connection) -> str | None:
    try:
        row = conn.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def create_backup(source_db: Path, dest_dir: Path) -> Path:
    """sqlite3 backup API로 일관 사본 + manifest를 만든다. manifest 경로 반환."""
    source_db = Path(source_db)
    dest_dir = Path(dest_dir)
    if not source_db.is_file():
        raise RestoreVerifyError(
            RestoreErrorCode.NOT_SQLITE, f"source not found: {source_db}"
        )
    try:
        dest_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise RestoreVerifyError(
            RestoreErrorCode.BACKUP_WRITE_FAILED, f"dest dir: {exc}"
        ) from exc

    dest_db = dest_dir / _DB_FILE
    try:
        src = sqlite3.connect(str(source_db))
        src.execute("PRAGMA query_only=ON")
    except sqlite3.Error as exc:
        raise RestoreVerifyError(
            RestoreErrorCode.NOT_SQLITE, f"source open failed: {exc}"
        ) from exc
    try:
        alembic_head = _read_alembic_head(src)
        if alembic_head is None:
            raise RestoreVerifyError(
                RestoreErrorCode.NOT_SQLITE,
                "source has no alembic_version (not a jippeel DB?)",
            )
        try:
            dst = sqlite3.connect(dest_db)
            try:
                src.backup(dst)
            finally:
                dst.close()
        except sqlite3.Error as exc:
            # 대상 쓰기 실패(disk-full·권한·열기 불가)와 원본 손상을 구분한다
            write_errs = {
                sqlite3.SQLITE_FULL,
                sqlite3.SQLITE_IOERR,
                sqlite3.SQLITE_CANTOPEN,
                sqlite3.SQLITE_READONLY,
            }
            if getattr(exc, "sqlite_errorcode", None) in write_errs:
                raise RestoreVerifyError(
                    RestoreErrorCode.BACKUP_WRITE_FAILED, f"dest write: {exc}"
                ) from exc
            raise RestoreVerifyError(
                RestoreErrorCode.NOT_SQLITE, f"backup failed: {exc}"
            ) from exc
    finally:
        src.close()

    files = []
    for path in sorted(dest_dir.iterdir()):
        if path.is_file():
            files.append(
                {
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    manifest = {
        "format_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source_db),
        "alembic_head": alembic_head,
        "files": files,
    }
    manifest_path = dest_dir / "manifest.json"
    try:
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        raise RestoreVerifyError(
            RestoreErrorCode.BACKUP_WRITE_FAILED, f"manifest write: {exc}"
        ) from exc
    return manifest_path


def verify_backup_dir(
    backup_dir: Path, *, expected_alembic_head: str | None = None
) -> VerifyReport:
    """백업 디렉터리를 검증한다. 모든 실패를 수집해 반환 — 읽기 전용."""
    backup_dir = Path(backup_dir)
    failures: list[Failure] = []
    checks: list[str] = []

    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.is_file():
        return VerifyReport(
            ok=False,
            failures=[Failure(RestoreErrorCode.MANIFEST_MISSING, str(manifest_path))],
        )
    try:
        manifest: dict[str, Any] = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return VerifyReport(
            ok=False,
            failures=[Failure(RestoreErrorCode.MANIFEST_INVALID, str(exc))],
        )
    if not isinstance(manifest, dict) or not _MANIFEST_REQUIRED <= set(manifest):
        missing = (
            _MANIFEST_REQUIRED - set(manifest)
            if isinstance(manifest, dict)
            else _MANIFEST_REQUIRED
        )
        return VerifyReport(
            ok=False,
            failures=[
                Failure(
                    RestoreErrorCode.MANIFEST_INVALID,
                    f"required keys missing: {sorted(missing)}",
                )
            ],
        )
    files_field = manifest.get("files")
    if not isinstance(files_field, list) or not all(
        isinstance(f, dict)
        and isinstance(f.get("name"), str)
        and isinstance(f.get("sha256"), str)
        for f in files_field
    ):
        return VerifyReport(
            ok=False,
            failures=[
                Failure(
                    RestoreErrorCode.MANIFEST_INVALID,
                    "files must be a list of {name, sha256, ...} objects",
                )
            ],
        )
    checks.append("manifest")

    declared = {f["name"]: f for f in files_field}
    for name, entry in declared.items():
        # manifest 선언 이름으로 백업 디렉터리 밖을 읽지 않는다
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or rel.name != name:
            failures.append(
                Failure(RestoreErrorCode.MANIFEST_INVALID, f"unsafe name: {name!r}")
            )
            continue
        path = backup_dir / name
        if not path.is_file():
            failures.append(Failure(RestoreErrorCode.FILE_MISSING, name))
            continue
        try:
            actual_sha = _sha256(path)
        except OSError as exc:
            failures.append(Failure(RestoreErrorCode.FILE_MISSING, f"{name}: {exc}"))
            continue
        if actual_sha != entry["sha256"]:
            failures.append(Failure(RestoreErrorCode.CHECKSUM_MISMATCH, name))
    checks.append("files+checksums")

    db_path = backup_dir / _DB_FILE
    db_checks_possible = db_path.is_file()
    conn: sqlite3.Connection | None = None
    integrity_rows: list[str] | None = None
    if db_checks_possible:
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA query_only=ON")
            # 비-SQLite 파일도 connect는 성공하므로 실제 읽기로 판별한다
            integrity_rows = [
                r[0] for r in conn.execute("PRAGMA integrity_check").fetchall()
            ]
        except sqlite3.Error as exc:
            if conn is not None:
                conn.close()
            if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_NOTADB:
                failures.append(Failure(RestoreErrorCode.NOT_SQLITE, str(exc)))
            else:
                # sqlite이지만 손상 — integrity 검사 자체가 실패한 것이다
                failures.append(Failure(RestoreErrorCode.INTEGRITY_FAILED, str(exc)))
            db_checks_possible = False
            conn = None
        else:
            checks.append("sqlite-open")
    if db_checks_possible and conn is not None:
        try:
            integrity = integrity_rows or ["ok"]
            if integrity != ["ok"]:
                failures.append(
                    Failure(RestoreErrorCode.INTEGRITY_FAILED, "; ".join(integrity[:5]))
                )
            else:
                checks.append("integrity_check")
            fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_rows:
                failures.append(
                    Failure(
                        RestoreErrorCode.FOREIGN_KEY_FAILED,
                        f"{len(fk_rows)} violations",
                    )
                )
            else:
                checks.append("foreign_key_check")
            actual_head = _read_alembic_head(conn)
            manifest_head = manifest.get("alembic_head")
            if actual_head != manifest_head or (
                expected_alembic_head is not None
                and actual_head != expected_alembic_head
            ):
                failures.append(
                    Failure(
                        RestoreErrorCode.SCHEMA_HEAD_MISMATCH,
                        f"db={actual_head} manifest={manifest_head} "
                        f"expected={expected_alembic_head}",
                    )
                )
            else:
                checks.append("alembic_head")
        finally:
            conn.close()

    return VerifyReport(ok=not failures, failures=failures, checks=checks)
