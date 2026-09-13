"""O02 — 자동 주기 백업 스케줄러 (opt-in).

`JIPPEEL_AUTOBACKUP_INTERVAL_MIN`이 설정됐을 때만 앱 수명주기에서 daemon thread가
주기적으로 `create_backup`을 호출한다. 백업 실패는 경고 로그만 남기고 스케줄러와
앱을 죽이지 않는다(non-blocking). 기본 디렉터리 `~/.jippeel/backups/auto`,
보존 개수 `JIPPEEL_AUTOBACKUP_KEEP`(기본 5).
"""

import logging
import os
import re
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.services.restore_verify import create_backup

log = logging.getLogger(__name__)

_DIR_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
_DEFAULT_BASE = Path.home() / ".jippeel" / "backups" / "auto"


@dataclass(frozen=True)
class AutoBackupConfig:
    interval_minutes: float
    base_dir: Path
    keep: int = 5

    @property
    def enabled(self) -> bool:
        return self.interval_minutes > 0

    @classmethod
    def from_env(cls) -> "AutoBackupConfig":
        raw_interval = os.environ.get("JIPPEEL_AUTOBACKUP_INTERVAL_MIN", "")
        try:
            interval = float(raw_interval) if raw_interval else 0.0
        except ValueError:
            interval = 0.0
        raw_dir = os.environ.get("JIPPEEL_AUTOBACKUP_DIR")
        base = Path(raw_dir) if raw_dir else _DEFAULT_BASE
        try:
            keep = max(1, int(os.environ.get("JIPPEEL_AUTOBACKUP_KEEP", "5")))
        except ValueError:
            keep = 5
        return cls(interval_minutes=interval, base_dir=base, keep=keep)


def _stamp_name(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")


def prune_backups(cfg: AutoBackupConfig) -> list[Path]:
    """타임스탬프 패턴 디렉터리 중 최신 `keep`개를 제외하고 삭제한다."""
    if not cfg.base_dir.is_dir():
        return []
    backups = sorted(
        (p for p in cfg.base_dir.iterdir() if p.is_dir() and _DIR_RE.match(p.name)),
        key=lambda p: p.name,
    )
    removed: list[Path] = []
    for old in backups[: max(0, len(backups) - cfg.keep)]:
        shutil.rmtree(old)
        removed.append(old)
    return removed


def _next_dir(base: Path, now: datetime | None = None) -> Path:
    stamp = _stamp_name(now)
    candidate = base / stamp
    suffix = 0
    while candidate.exists():
        suffix += 1
        candidate = base / f"{stamp}-{suffix}"
    return candidate


def run_backup_once(
    cfg: AutoBackupConfig, source_db: Path, now: datetime | None = None
) -> Path:
    """단일 백업 + 프루닝. manifest 경로 반환. 실패는 호출자에게 전파."""
    cfg.base_dir.mkdir(parents=True, exist_ok=True)
    manifest = create_backup(source_db, _next_dir(cfg.base_dir, now))
    prune_backups(cfg)
    return manifest


def start_scheduler(cfg: AutoBackupConfig, source_db: Path) -> Callable[[], None]:
    """daemon 스레드로 주기 백업을 시작하고 stop 콜백을 반환한다."""
    stop_event = threading.Event()

    def _loop() -> None:
        interval_s = cfg.interval_minutes * 60
        while not stop_event.wait(interval_s):
            try:
                run_backup_once(cfg, source_db)
            except Exception:  # noqa: BLE001 — 백업 실패가 스케줄러·앱을 죽이지 않게 포착
                log.warning("auto-backup iteration failed", exc_info=True)

    thread = threading.Thread(target=_loop, name="jippeel-autobackup", daemon=True)
    thread.start()

    def stop() -> None:
        stop_event.set()
        thread.join(timeout=5)

    return stop
