"""O02 — 자동 주기 백업 테스트."""

import json
import sqlite3
import time
from pathlib import Path

import pytest

from app.services import auto_backup
from app.services.auto_backup import AutoBackupConfig


def _make_jippeel_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES ('e2f3a4b5c6d7')")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    return path


def _cfg(tmp_path: Path, **env) -> AutoBackupConfig:
    return AutoBackupConfig(
        interval_minutes=env.get("interval", 60.0),
        base_dir=tmp_path / "auto",
        keep=env.get("keep", 5),
    )


class TestConfig:
    def test_disabled_by_default(self, monkeypatch, tmp_path):
        for key in ("JIPPEEL_AUTOBACKUP_INTERVAL_MIN", "JIPPEEL_AUTOBACKUP_DIR", "JIPPEEL_AUTOBACKUP_KEEP"):
            monkeypatch.delenv(key, raising=False)
        assert not AutoBackupConfig.from_env().enabled

    def test_enabled_with_interval(self, monkeypatch):
        monkeypatch.setenv("JIPPEEL_AUTOBACKUP_INTERVAL_MIN", "30")
        cfg = AutoBackupConfig.from_env()
        assert cfg.enabled
        assert cfg.interval_minutes == 30.0
        assert cfg.keep == 5

    def test_zero_interval_disables(self, monkeypatch):
        monkeypatch.setenv("JIPPEEL_AUTOBACKUP_INTERVAL_MIN", "0")
        assert not AutoBackupConfig.from_env().enabled

    def test_invalid_interval_disables(self, monkeypatch):
        monkeypatch.setenv("JIPPEEL_AUTOBACKUP_INTERVAL_MIN", "abc")
        assert not AutoBackupConfig.from_env().enabled

    def test_keep_floor(self, monkeypatch):
        monkeypatch.setenv("JIPPEEL_AUTOBACKUP_INTERVAL_MIN", "1")
        monkeypatch.setenv("JIPPEEL_AUTOBACKUP_KEEP", "0")
        assert AutoBackupConfig.from_env().keep == 1


class TestRunBackupOnce:
    def test_creates_manifest_and_db(self, tmp_path):
        src = _make_jippeel_db(tmp_path / "src.db")
        cfg = _cfg(tmp_path)
        manifest = auto_backup.run_backup_once(cfg, src)
        assert manifest.is_file()
        data = json.loads(manifest.read_text())
        assert data["alembic_head"] == "e2f3a4b5c6d7"
        assert (manifest.parent / "database.sqlite3").is_file()

    def test_timestamp_collision_suffix(self, tmp_path):
        src = _make_jippeel_db(tmp_path / "src.db")
        cfg = _cfg(tmp_path)
        stamp = auto_backup._stamp_name()
        (cfg.base_dir / stamp).mkdir(parents=True)
        manifest = auto_backup.run_backup_once(cfg, src)
        assert manifest.parent.name.startswith(stamp)

    def test_prunes_beyond_keep(self, tmp_path):
        src = _make_jippeel_db(tmp_path / "src.db")
        cfg = _cfg(tmp_path, keep=2)
        for i in range(4):
            (cfg.base_dir / f"2026010{i}-000000").mkdir(parents=True)
        (cfg.base_dir / "not-a-backup").mkdir()  # 패턴 외 — 보존
        auto_backup.run_backup_once(cfg, src)
        remaining = sorted(p.name for p in cfg.base_dir.iterdir())
        backups = [n for n in remaining if auto_backup._DIR_RE.match(n)]
        assert len(backups) == 2
        assert "not-a-backup" in remaining

    def test_source_failure_raises(self, tmp_path):
        cfg = _cfg(tmp_path)
        with pytest.raises(Exception):
            auto_backup.run_backup_once(cfg, tmp_path / "missing.db")


class TestScheduler:
    def test_ticks_and_stops(self, tmp_path):
        src = _make_jippeel_db(tmp_path / "src.db")
        cfg = AutoBackupConfig(
            interval_minutes=0.0005,  # ~30ms
            base_dir=tmp_path / "auto",
            keep=50,
        )
        stop = auto_backup.start_scheduler(cfg, src)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if any(cfg.base_dir.iterdir()) if cfg.base_dir.exists() else False:
                    break
                time.sleep(0.02)
            assert cfg.base_dir.exists()
            assert any(p.is_dir() for p in cfg.base_dir.iterdir())
        finally:
            stop()

    def test_survives_backup_failure(self, tmp_path):
        cfg = AutoBackupConfig(
            interval_minutes=0.0005,
            base_dir=tmp_path / "auto",
            keep=50,
        )
        stop = auto_backup.start_scheduler(cfg, tmp_path / "nonexistent.db")
        time.sleep(0.2)  # 여러 tick — 실패해도 스레드 생존
        stop()  # hang 없이 종료돼야 통과
