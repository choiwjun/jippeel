"""V02 — 복원 검증기 + 실패 주입 테스트.

합성·임시 SQLite 경로만 사용. 운영 DB·keyring·credential 접근 없음.
"""
import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest

from app.services.restore_verify import (
    RestoreErrorCode,
    RestoreVerifyError,
    create_backup,
    verify_backup_dir,
)


@pytest.fixture
def source_db(tmp_path: Path) -> Path:
    db = tmp_path / "source.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('ae1f2b3c4d58')")
    conn.execute(
        "CREATE TABLE projects (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE chapters (id INTEGER PRIMARY KEY, project_id INTEGER "
        "REFERENCES projects(id), title TEXT, content_md TEXT, revision INTEGER)"
    )
    conn.execute("INSERT INTO projects (id, title) VALUES (1, 'p')")
    conn.execute(
        "INSERT INTO chapters (id, project_id, title, content_md, revision) "
        "VALUES (1, 1, 'c1', '본문', 3)"
    )
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return db


def _failures(report):
    return {f.code for f in report.failures}


def test_backup_and_verify_happy_path(source_db, tmp_path):
    dest = tmp_path / "backup-ok"
    manifest_path = create_backup(source_db, dest)

    manifest = json.loads(manifest_path.read_text())
    assert manifest["alembic_head"] == "ae1f2b3c4d58"
    assert manifest["format_version"] == 1
    names = {f["name"] for f in manifest["files"]}
    assert "database.sqlite3" in names

    report = verify_backup_dir(dest, expected_alembic_head="ae1f2b3c4d58")
    assert report.ok, report.failures
    assert report.failures == []

    # 복원본이 논리적으로 동일
    conn = sqlite3.connect(dest / "database.sqlite3")
    row = conn.execute(
        "SELECT title, content_md, revision FROM chapters"
    ).fetchone()
    conn.close()
    assert row == ("c1", "본문", 3)


def test_verify_missing_manifest(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    (dest / "manifest.json").unlink()

    report = verify_backup_dir(dest)
    assert not report.ok
    assert _failures(report) == {RestoreErrorCode.MANIFEST_MISSING}


def test_verify_invalid_manifest(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    (dest / "manifest.json").write_text("{not json")

    report = verify_backup_dir(dest)
    assert _failures(report) == {RestoreErrorCode.MANIFEST_INVALID}

    (dest / "manifest.json").write_text(json.dumps({"format_version": 1}))
    report = verify_backup_dir(dest)
    assert RestoreErrorCode.MANIFEST_INVALID in _failures(report)


def test_verify_missing_database_file(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    (dest / "database.sqlite3").unlink()

    report = verify_backup_dir(dest)
    assert not report.ok
    assert RestoreErrorCode.FILE_MISSING in _failures(report)


def test_verify_checksum_mismatch(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    db_file = dest / "database.sqlite3"
    data = bytearray(db_file.read_bytes())
    data[-1] ^= 0xFF  # 마지막 바이트 변경 — sha 불일치
    db_file.write_bytes(bytes(data))

    report = verify_backup_dir(dest)
    assert RestoreErrorCode.CHECKSUM_MISMATCH in _failures(report)


def test_verify_not_sqlite(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    db_file = dest / "database.sqlite3"
    db_file.write_bytes(b"this is definitely not a sqlite file" + b"\x00" * 128)
    # manifest sha도 맞춰둠 — checksum은 통과하고 NOT_SQLITE만 잡혀야 한다
    manifest = json.loads((dest / "manifest.json").read_text())
    for f in manifest["files"]:
        if f["name"] == "database.sqlite3":
            f["sha256"] = hashlib.sha256(db_file.read_bytes()).hexdigest()
            f["size_bytes"] = db_file.stat().st_size
    (dest / "manifest.json").write_text(json.dumps(manifest))

    report = verify_backup_dir(dest)
    assert RestoreErrorCode.NOT_SQLITE in _failures(report)
    assert RestoreErrorCode.INTEGRITY_FAILED not in _failures(report)


def test_verify_integrity_failure(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    db_file = dest / "database.sqlite3"
    data = bytearray(db_file.read_bytes())
    # 페이지 본문 영역을 깨뜨린다(헤더는 유지 — sqlite로는 열림)
    for i in range(4096, min(8192, len(data))):
        data[i] = 0
    db_file.write_bytes(bytes(data))
    manifest = json.loads((dest / "manifest.json").read_text())
    for f in manifest["files"]:
        if f["name"] == "database.sqlite3":
            f["sha256"] = hashlib.sha256(db_file.read_bytes()).hexdigest()
            f["size_bytes"] = db_file.stat().st_size
    (dest / "manifest.json").write_text(json.dumps(manifest))

    report = verify_backup_dir(dest)
    assert not report.ok
    assert RestoreErrorCode.INTEGRITY_FAILED in _failures(report)


def test_verify_foreign_key_failure(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    db_file = dest / "database.sqlite3"
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO chapters (id, project_id, title, content_md, revision) "
        "VALUES (2, 999, 'orphan', 'x', 0)"
    )
    conn.commit()
    conn.close()
    manifest = json.loads((dest / "manifest.json").read_text())
    for f in manifest["files"]:
        if f["name"] == "database.sqlite3":
            f["sha256"] = hashlib.sha256(db_file.read_bytes()).hexdigest()
            f["size_bytes"] = db_file.stat().st_size
    (dest / "manifest.json").write_text(json.dumps(manifest))

    report = verify_backup_dir(dest)
    assert RestoreErrorCode.FOREIGN_KEY_FAILED in _failures(report)


def test_verify_schema_head_mismatch(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)

    # 복원본 alembic_version을 다른 head로 변조(manifest도 함께 갱신 → head 불일치만 남김)
    db_file = dest / "database.sqlite3"
    conn = sqlite3.connect(db_file)
    conn.execute("UPDATE alembic_version SET version_num='deadbeef0000'")
    conn.commit()
    conn.close()
    manifest = json.loads((dest / "manifest.json").read_text())
    manifest["alembic_head"] = "deadbeef0000"
    for f in manifest["files"]:
        if f["name"] == "database.sqlite3":
            f["sha256"] = hashlib.sha256(db_file.read_bytes()).hexdigest()
            f["size_bytes"] = db_file.stat().st_size
    (dest / "manifest.json").write_text(json.dumps(manifest))

    report = verify_backup_dir(dest, expected_alembic_head="ae1f2b3c4d58")
    assert RestoreErrorCode.SCHEMA_HEAD_MISMATCH in _failures(report)

    # manifest head가 복원본과도 불일치하는 경우
    manifest["alembic_head"] = "different1234"
    (dest / "manifest.json").write_text(json.dumps(manifest))
    report = verify_backup_dir(dest)
    assert RestoreErrorCode.SCHEMA_HEAD_MISMATCH in _failures(report)


def test_create_backup_write_failure(source_db, tmp_path):
    # 결정적 실패 — 대상 경로가 이미 존재하는 파일이면 mkdir이 실패한다
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    with pytest.raises(RestoreVerifyError) as excinfo:
        create_backup(source_db, blocker / "backup")
    assert excinfo.value.code == RestoreErrorCode.BACKUP_WRITE_FAILED

    # 쓰기 불가 디렉터리 — disk-full/권한 실패 근사(root/Windows에서는 무효할 수 있어 보조)
    # Windows는 chmod가 디렉터리 생성을 막지 못하므로(ACL 기반) POSIX에서만 근사 실행
    if os.name != "nt":
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)
        try:
            with pytest.raises(RestoreVerifyError) as excinfo:
                create_backup(source_db, readonly_dir / "backup")
            assert excinfo.value.code == RestoreErrorCode.BACKUP_WRITE_FAILED
        finally:
            readonly_dir.chmod(0o755)

    with pytest.raises(RestoreVerifyError) as excinfo:
        create_backup(tmp_path / "does-not-exist.db", tmp_path / "backup")
    assert excinfo.value.code == RestoreErrorCode.NOT_SQLITE


def test_create_backup_rejects_non_jippeel_source(tmp_path):
    """SQLite이지만 alembic_version이 없는 원본은 jippeel 백업 대상이 아니다."""
    non_jippeel = tmp_path / "plain.db"
    conn = sqlite3.connect(non_jippeel)
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()

    with pytest.raises(RestoreVerifyError) as excinfo:
        create_backup(non_jippeel, tmp_path / "backup")
    assert excinfo.value.code == RestoreErrorCode.NOT_SQLITE


def test_verify_malformed_manifest_variants(source_db, tmp_path):
    """손상된 manifest가 예외가 아니라 MANIFEST_INVALID를 보고한다."""
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    manifest_path = dest / "manifest.json"

    for bad in (
        "null",           # JSON 스칼라
        '{"files": null}',                     # files가 list가 아님
        '{"files": [{"sha256": "x"}]}',        # name 없는 항목
        '{"files": [{"name": 5}]}',            # name이 문자열이 아님
    ):
        manifest_path.write_text(bad)
        report = verify_backup_dir(dest)
        assert not report.ok
        assert RestoreErrorCode.MANIFEST_INVALID in _failures(report), bad

    manifest_path.write_bytes(b"\xff\xfe\x00\x01")  # UTF-8 아님
    report = verify_backup_dir(dest)
    assert RestoreErrorCode.MANIFEST_INVALID in _failures(report)


def test_verify_rejects_manifest_path_traversal(source_db, tmp_path):
    """manifest 이름으로 백업 디렉터리 밖 파일을 읽지 않는다."""
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret-adjacent")
    import hashlib as _h
    manifest = json.loads((dest / "manifest.json").read_text())
    manifest["files"] = [
        {"name": "../outside.txt", "size_bytes": 15,
         "sha256": _h.sha256(outside.read_bytes()).hexdigest()}
    ]
    (dest / "manifest.json").write_text(json.dumps(manifest))

    report = verify_backup_dir(dest)
    assert not report.ok
    assert RestoreErrorCode.MANIFEST_INVALID in _failures(report)


def test_multiple_failures_reported_together(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    # checksum 훼손 + head 변조를 동시에
    db_file = dest / "database.sqlite3"
    conn = sqlite3.connect(db_file)
    conn.execute("UPDATE alembic_version SET version_num='wrong'")
    conn.commit()
    conn.close()
    # manifest는 갱신하지 않는다 → checksum 불일치도 같이 보고돼야 한다
    report = verify_backup_dir(dest, expected_alembic_head="ae1f2b3c4d58")
    codes = _failures(report)
    assert RestoreErrorCode.CHECKSUM_MISMATCH in codes
    assert RestoreErrorCode.SCHEMA_HEAD_MISMATCH in codes


def test_verify_does_not_modify_backup(source_db, tmp_path):
    dest = tmp_path / "backup-x"
    create_backup(source_db, dest)
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in dest.iterdir() if p.is_file()
    }
    verify_backup_dir(dest)
    after = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in dest.iterdir() if p.is_file()
    }
    assert before == after
